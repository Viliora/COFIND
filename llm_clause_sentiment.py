"""
Analisis sentimen aspek per klausa memakai LLM (lapis kedua setelah heuristik).

Kenapa ada modul ini: deteksi keluhan berbasis aturan (jendela ±N token di
app.py) rapuh untuk tiga pola yang umum di ulasan nyata —
  1. jarak kata jauh: "lambat sekali untuk semua wifi yang tersedia di sini"
  2. negasi pada kata dasar positif: "ngga nyaman" (kata "nyaman" sendiri positif)
  3. klausa tercampur: "kursinya bagus tapi ngga nyaman, wifinya bagus"
LLM membaca satu klausa utuh, jadi keputusannya berbasis makna, bukan posisi kata.

Alur: klausa dinilai satu per satu (relevan terhadap preferensi? sentimennya
apa?), lalu digabung menjadi verdict per kutipan. Klausa negatif yang TIDAK
relevan dengan preferensi user tidak lagi menjatuhkan kutipan itu.

Efisiensi: klausa dikelompokkan per batch dalam satu panggilan LLM, dan hasilnya
disimpan di vector_cache sehingga klausa yang sama tidak dinilai dua kali.

Env:
  COFIND_LLM_CLAUSE_SENTIMENT           aktifkan tahap ini (default: false)
  COFIND_CLAUSE_SENTIMENT_BATCH         klausa per panggilan LLM (default: 16)
  COFIND_CLAUSE_SENTIMENT_MAX           batas klausa per request rekomendasi (default: 96)
  COFIND_CLAUSE_SENTIMENT_POOL          jumlah kandidat toko yang diverifikasi (default: 6)
  COFIND_CLAUSE_SENTIMENT_CONCURRENCY   batch yang dikirim paralel (default: 3)
"""

from __future__ import annotations

import os
import re
import time
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from semantic_match import split_clauses
from vector_cache import PersistentCache, digest_key

_cache = PersistentCache('clause_sentiment')

_ALLOWED_SENTIMENTS = ('positif', 'negatif', 'netral')
_MIN_CLAUSE_CHARS = 3

_SYSTEM_PROMPT = (
    'Anda mesin analisis sentimen aspek untuk ulasan coffee shop Indonesia. '
    'Untuk setiap klausa, tentukan apakah klausa itu membahas aspek yang diminta user, '
    'dan bila ya, apakah nadanya positif, negatif, atau netral. '
    'Nilai hanya dari isi klausa; jangan menebak hal di luar teks. '
    'Jawab HANYA JSON array valid tanpa markdown dan tanpa penjelasan tambahan.'
)


def _env_flag(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or '').strip().lower()
    if not raw:
        return default
    return raw in ('1', 'true', 'yes', 'on')


def _env_int(name: str, default: int, *, min_value: int, max_value: int) -> int:
    raw = (os.getenv(name) or '').strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(min_value, min(max_value, value))


def clause_sentiment_enabled() -> bool:
    return _env_flag('COFIND_LLM_CLAUSE_SENTIMENT', False)


def batch_size() -> int:
    return _env_int('COFIND_CLAUSE_SENTIMENT_BATCH', 16, min_value=1, max_value=40)


def max_clauses_per_request() -> int:
    return _env_int('COFIND_CLAUSE_SENTIMENT_MAX', 96, min_value=10, max_value=1000)


def candidate_pool() -> int:
    return _env_int('COFIND_CLAUSE_SENTIMENT_POOL', 6, min_value=1, max_value=30)


def batch_concurrency() -> int:
    return _env_int('COFIND_CLAUSE_SENTIMENT_CONCURRENCY', 3, min_value=1, max_value=8)


def sentiment_config() -> Dict[str, object]:
    return {
        'enabled': clause_sentiment_enabled(),
        'batch_size': batch_size(),
        'max_clauses': max_clauses_per_request(),
        'candidate_pool': candidate_pool(),
        'concurrency': batch_concurrency(),
    }


def quote_key(text: object) -> str:
    """Kunci kutipan yang tahan beda spasi/kapitalisasi."""
    return re.sub(r'\s+', ' ', str(text or '')).strip().lower()


def _clause_cache_key(preference_line: str, clause: str) -> str:
    return digest_key('clause-sentiment-v1', preference_line.lower(), clause.lower())


def _user_prompt(preference_line: str, clauses: Sequence[str]) -> str:
    numbered = '\n'.join(f'[{idx}] "{clause}"' for idx, clause in enumerate(clauses, 1))
    return (
        f'Aspek yang dicari user: {preference_line}\n\n'
        f'Klausa ulasan:\n{numbered}\n\n'
        'Tugas: untuk setiap klausa, isi dua hal.\n'
        '- "relevan": true bila klausa membahas salah satu aspek yang dicari user '
        '(termasuk bila memakai kata lain yang bermakna sama, misalnya "koneksinya ngebut" '
        'untuk aspek wifi kencang). false bila klausa membahas hal lain.\n'
        '- "sentimen": "positif" bila klausa memuji aspek itu, "negatif" bila mengeluh '
        '(termasuk negasi seperti "ngga nyaman", "kurang oke"), "netral" bila ragu-ragu, '
        'sekadar menyebut, atau tidak relevan.\n'
        'Aturan: satu objek JSON per klausa, pakai nomor id yang sama, jangan menambah klausa baru.\n'
        'Format keluaran: [{"id":1,"relevan":true,"sentimen":"positif"}]'
    )


def _parse_batch_response(raw: object, parse_json_fn: Optional[Callable]) -> Optional[list]:
    import json

    if parse_json_fn is not None:
        try:
            parsed = parse_json_fn(raw, expected='array')
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
    text = str(raw or '').strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text).strip()
    match = re.search(r'\[[\s\S]*\]', text)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except Exception:
        return None
    return parsed if isinstance(parsed, list) else None


def _coerce_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value or '').strip().lower()
    if text in ('true', 'ya', 'yes', '1', 'relevan'):
        return True
    if text in ('false', 'tidak', 'no', '0', 'tidak relevan'):
        return False
    return default


def _coerce_sentiment(value: object) -> str:
    text = str(value or '').strip().lower()
    if text.startswith('pos'):
        return 'positif'
    if text.startswith('neg'):
        return 'negatif'
    if text in _ALLOWED_SENTIMENTS:
        return text
    return 'netral'


def _classify_clauses(
    clauses: Sequence[str],
    *,
    preference_line: str,
    chat_fn: Callable[..., str],
    parse_json_fn: Optional[Callable],
) -> Tuple[Dict[str, dict], Dict[str, object]]:
    """Verdict per klausa unik (cache dulu, sisanya batch ke LLM)."""
    telemetry: Dict[str, object] = {
        'clauses': len(clauses),
        'from_cache': 0,
        'from_llm': 0,
        'llm_calls': 0,
        'failed_batches': 0,
        'latency_ms': 0.0,
        'error': None,
    }
    verdicts: Dict[str, dict] = {}
    if not clauses:
        return verdicts, telemetry

    cache_keys = {clause: _clause_cache_key(preference_line, clause) for clause in clauses}
    cached = _cache.get_many(cache_keys.values())
    pending: List[str] = []
    for clause in clauses:
        entry = cached.get(cache_keys[clause])
        if isinstance(entry, dict) and 'sentimen' in entry:
            verdicts[clause] = {
                'relevant': bool(entry.get('relevan')),
                'sentiment': _coerce_sentiment(entry.get('sentimen')),
                'source': 'cache',
            }
            telemetry['from_cache'] = int(telemetry['from_cache']) + 1
        else:
            pending.append(clause)

    if not pending:
        return verdicts, telemetry

    started = time.perf_counter()
    size = batch_size()
    batches = [pending[offset:offset + size] for offset in range(0, len(pending), size)]
    to_store: Dict[str, dict] = {}

    def run_batch(batch: List[str]):
        """Satu panggilan LLM untuk satu batch klausa; error dikembalikan, tidak diangkat."""
        try:
            raw = chat_fn(
                messages=[
                    {'role': 'system', 'content': _SYSTEM_PROMPT},
                    {'role': 'user', 'content': _user_prompt(preference_line, batch)},
                ],
                max_tokens=min(900, 80 + 30 * len(batch)),
                temperature=0.0,
            )
            return batch, raw, None
        except Exception as err:
            return batch, None, str(err)[:160]

    workers = min(batch_concurrency(), len(batches))
    if workers > 1:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(run_batch, batches))
    else:
        results = [run_batch(batch) for batch in batches]

    for batch, raw, error in results:
        if error is not None:
            telemetry['failed_batches'] = int(telemetry['failed_batches']) + 1
            telemetry['error'] = error
            continue
        telemetry['llm_calls'] = int(telemetry['llm_calls']) + 1

        parsed = _parse_batch_response(raw, parse_json_fn)
        if not parsed:
            telemetry['failed_batches'] = int(telemetry['failed_batches']) + 1
            telemetry['error'] = telemetry['error'] or 'parse_failed'
            continue

        for item in parsed:
            if not isinstance(item, dict):
                continue
            try:
                position = int(re.sub(r'[^0-9-]', '', str(item.get('id'))) or 0)
            except (TypeError, ValueError):
                continue
            if not (1 <= position <= len(batch)):
                continue
            clause = batch[position - 1]
            if clause in verdicts:
                continue
            sentiment = _coerce_sentiment(item.get('sentimen') or item.get('sentiment'))
            relevant = _coerce_bool(item.get('relevan', item.get('relevant')), default=False)
            # Klausa tidak relevan tidak punya sentimen terhadap aspek yang dicari.
            if not relevant:
                sentiment = 'netral'
            verdicts[clause] = {'relevant': relevant, 'sentiment': sentiment, 'source': 'llm'}
            to_store[cache_keys[clause]] = {'relevan': relevant, 'sentimen': sentiment}
            telemetry['from_llm'] = int(telemetry['from_llm']) + 1

    if to_store:
        _cache.set_many(to_store)
    telemetry['latency_ms'] = round((time.perf_counter() - started) * 1000, 1)
    return verdicts, telemetry


def classify_quotes(
    quotes: Sequence[str],
    *,
    preference_line: str,
    chat_fn: Callable[..., str],
    parse_json_fn: Optional[Callable] = None,
    max_clauses: Optional[int] = None,
) -> Tuple[Dict[str, dict], Dict[str, object]]:
    """
    Verdict sentimen per kutipan terhadap preferensi user.

    Return (verdicts, telemetry) dengan verdicts[quote_key(kutipan)] = {
        'label': 'supporting' | 'caveat' | 'irrelevant',
        'sentiment': 'positif' | 'negatif' | 'netral',
        'clause': klausa yang menentukan label (selalu potongan teks asli),
        'source': 'llm' | 'cache',
    }

    Kutipan tanpa verdict (LLM gagal / klausa terlalu pendek) tidak dimasukkan,
    sehingga pemanggil otomatis kembali ke heuristik lama.
    """
    telemetry: Dict[str, object] = {'quotes': 0, 'verdicts': 0, 'skipped': None}
    if not quotes or not clause_sentiment_enabled():
        telemetry['skipped'] = 'disabled' if quotes else 'no_input'
        return {}, telemetry

    limit = max_clauses if max_clauses is not None else max_clauses_per_request()
    clause_by_quote: Dict[str, List[str]] = {}
    unique_clauses: List[str] = []
    seen_clause = set()

    for quote in quotes:
        key = quote_key(quote)
        if not key or key in clause_by_quote:
            continue
        clauses = [c for c in split_clauses(quote) if len(c) >= _MIN_CLAUSE_CHARS]
        if not clauses:
            continue
        clause_by_quote[key] = clauses
        for clause in clauses:
            marker = clause.lower()
            if marker in seen_clause:
                continue
            if limit and len(unique_clauses) >= limit:
                break
            seen_clause.add(marker)
            unique_clauses.append(clause)

    telemetry['quotes'] = len(clause_by_quote)
    if not unique_clauses:
        telemetry['skipped'] = 'no_clauses'
        return {}, telemetry

    clause_verdicts, clause_telemetry = _classify_clauses(
        unique_clauses,
        preference_line=preference_line,
        chat_fn=chat_fn,
        parse_json_fn=parse_json_fn,
    )
    telemetry.update(clause_telemetry)
    if not clause_verdicts:
        telemetry['skipped'] = 'no_verdict'
        return {}, telemetry

    quote_verdicts: Dict[str, dict] = {}
    for key, clauses in clause_by_quote.items():
        judged = [(clause, clause_verdicts[clause]) for clause in clauses if clause in clause_verdicts]
        if not judged:
            continue
        relevant = [(clause, verdict) for clause, verdict in judged if verdict.get('relevant')]
        if not relevant:
            quote_verdicts[key] = {
                'label': 'irrelevant',
                'sentiment': 'netral',
                'clause': judged[0][0],
                'source': judged[0][1].get('source', 'llm'),
            }
            continue
        # Keluhan pada aspek yang diminta selalu menang: kutipan itu jadi catatan,
        # bukan bukti kecocokan, meski ada klausa positif di kalimat yang sama.
        negative = next((pair for pair in relevant if pair[1].get('sentiment') == 'negatif'), None)
        if negative is not None:
            quote_verdicts[key] = {
                'label': 'caveat',
                'sentiment': 'negatif',
                'clause': negative[0],
                'source': negative[1].get('source', 'llm'),
            }
            continue
        positive = next((pair for pair in relevant if pair[1].get('sentiment') == 'positif'), None)
        if positive is not None:
            quote_verdicts[key] = {
                'label': 'supporting',
                'sentiment': 'positif',
                'clause': positive[0],
                'source': positive[1].get('source', 'llm'),
            }
            continue
        quote_verdicts[key] = {
            'label': 'irrelevant',
            'sentiment': 'netral',
            'clause': relevant[0][0],
            'source': relevant[0][1].get('source', 'llm'),
        }

    telemetry['verdicts'] = len(quote_verdicts)
    return quote_verdicts, telemetry


def flush_cache() -> None:
    _cache.flush()


def cache_stats() -> Dict[str, int]:
    return _cache.stats()

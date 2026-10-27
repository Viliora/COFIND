"""
Analisis sentimen aspek per klausa (ABSA lokal + triase bi/cross-encoder).

Alur: klausa → triase e5/Jina → damasukma/indobert-absa untuk yang ambigu,
lalu digabung menjadi verdict per kutipan (supporting/caveat/irrelevant).

Env:
  COFIND_ABSA_ENABLED                   aktifkan ABSA (default: true)
  COFIND_ABSA_MODEL                     default damasukma/indobert-absa
  COFIND_LLM_CLAUSE_SENTIMENT           alias legacy (jika ABSA_ENABLED tidak diset)
  COFIND_CLAUSE_SENTIMENT_MAX           batas klausa per request (default: 96)
  COFIND_CLAUSE_SENTIMENT_POOL          kandidat toko (default: 6)
  COFIND_CLAUSE_SENTIMENT_DEDUP         dedup klausa via embedding (default: true)
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
    from absa_sentiment import absa_enabled

    return absa_enabled()


def clause_dedup_enabled() -> bool:
    return _env_flag('COFIND_CLAUSE_SENTIMENT_DEDUP', True)


def clause_dedup_min_similarity() -> float:
    raw = (os.getenv('COFIND_CLAUSE_SENTIMENT_DEDUP_MIN') or '').strip()
    if not raw:
        return 0.92
    try:
        value = float(raw)
    except ValueError:
        return 0.92
    return max(0.75, min(0.99, value))


def batch_size() -> int:
    return _env_int('COFIND_CLAUSE_SENTIMENT_BATCH', 16, min_value=1, max_value=40)


def max_clauses_per_request() -> int:
    return _env_int('COFIND_CLAUSE_SENTIMENT_MAX', 96, min_value=10, max_value=1000)


def candidate_pool() -> int:
    return _env_int('COFIND_CLAUSE_SENTIMENT_POOL', 6, min_value=1, max_value=30)


def batch_concurrency() -> int:
    return _env_int('COFIND_CLAUSE_SENTIMENT_CONCURRENCY', 3, min_value=1, max_value=8)


def clause_structured_output_enabled() -> bool:
    return _env_flag('COFIND_LLM_STRUCTURED_CLAUSE', False)


def sentiment_config() -> Dict[str, object]:
    from absa_sentiment import absa_model_name

    return {
        'enabled': clause_sentiment_enabled(),
        'backend': 'absa',
        'absa_model': absa_model_name(),
        'batch_size': batch_size(),
        'max_clauses': max_clauses_per_request(),
        'candidate_pool': candidate_pool(),
        'concurrency': batch_concurrency(),
        'dedup_enabled': clause_dedup_enabled(),
        'dedup_min_similarity': clause_dedup_min_similarity(),
    }


def _dedup_clauses_by_embedding(clauses: Sequence[str]) -> Tuple[List[str], Dict[str, str]]:
    """
    Gabung klausa hampir identik makna (cosine embedding) sebelum panggilan LLM.
    Return (daftar canonical unik untuk LLM, peta alias -> canonical).
    """
    items = [str(c).strip() for c in (clauses or []) if str(c).strip()]
    identity = {c: c for c in items}
    if not clause_dedup_enabled() or len(items) < 2:
        return list(dict.fromkeys(items)), identity

    try:
        from semantic_match import embed_texts
        import numpy as np
    except Exception:
        return list(dict.fromkeys(items)), identity

    vectors = embed_texts(items)
    if not vectors:
        return list(dict.fromkeys(items)), identity

    threshold = clause_dedup_min_similarity()
    canonical: List[str] = []
    reps: List[Tuple[str, object]] = []
    alias_map: Dict[str, str] = {}

    for clause in items:
        vec = vectors.get(clause)
        if vec is None:
            if clause not in canonical:
                canonical.append(clause)
            alias_map[clause] = clause
            continue
        merged = False
        for rep_clause, rep_vec in reps:
            sim = float(np.dot(np.asarray(vec, dtype=np.float32), np.asarray(rep_vec, dtype=np.float32)))
            if sim >= threshold:
                alias_map[clause] = rep_clause
                merged = True
                break
        if not merged:
            reps.append((clause, vec))
            canonical.append(clause)
            alias_map[clause] = clause

    return canonical, alias_map


def quote_key(text: object) -> str:
    """Kunci kutipan yang tahan beda spasi/kapitalisasi."""
    return re.sub(r'\s+', ' ', str(text or '')).strip().lower()


def _clause_cache_key(preference_line: str, clause: str) -> str:
    return digest_key('clause-sentiment-v1', preference_line.lower(), clause.lower())


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
    chat_fn: Optional[Callable[..., str]] = None,
    parse_json_fn: Optional[Callable] = None,
) -> Tuple[Dict[str, dict], Dict[str, object]]:
    """Verdict per klausa unik (cache legacy + ABSA lokal)."""
    _ = chat_fn, parse_json_fn
    from absa_sentiment import classify_clauses_absa

    telemetry: Dict[str, object] = {
        'clauses': len(clauses),
        'from_cache': 0,
        'from_absa': 0,
        'absa_batches': 0,
        'llm_calls': 0,
        'latency_ms': 0.0,
        'backend': 'absa',
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

    llm_targets, alias_map = _dedup_clauses_by_embedding(pending)
    telemetry['dedup_aliases'] = max(0, len(pending) - len(llm_targets))

    absa_verdicts, absa_telemetry = classify_clauses_absa(
        llm_targets,
        preference_line=preference_line,
    )
    telemetry.update(absa_telemetry or {})
    telemetry['llm_calls'] = int(telemetry.get('absa_batches') or 0)

    to_store: Dict[str, dict] = {}
    for clause, verdict in (absa_verdicts or {}).items():
        if clause in verdicts:
            continue
        verdicts[clause] = verdict
        to_store[cache_keys[clause]] = {
            'relevan': bool(verdict.get('relevant')),
            'sentimen': verdict.get('sentiment'),
        }

    if to_store:
        _cache.set_many(to_store)

    for alias, canonical in alias_map.items():
        if alias == canonical or alias in verdicts:
            continue
        canon_verdict = verdicts.get(canonical)
        if isinstance(canon_verdict, dict):
            verdicts[alias] = dict(canon_verdict)

    return verdicts, telemetry


def classify_clauses_batch(
    clauses: Sequence[str],
    *,
    preference_line: str,
    chat_fn: Callable[..., str],
    parse_json_fn: Optional[Callable] = None,
) -> Tuple[Dict[str, dict], Dict[str, object]]:
    """API publik untuk warm cache offline (sama dengan _classify_clauses)."""
    return _classify_clauses(
        clauses,
        preference_line=preference_line,
        chat_fn=chat_fn,
        parse_json_fn=parse_json_fn,
    )


def classify_quotes(
    quotes: Sequence[str],
    *,
    preference_line: str,
    chat_fn: Optional[Callable[..., str]] = None,
    parse_json_fn: Optional[Callable] = None,
    max_clauses: Optional[int] = None,
) -> Tuple[Dict[str, dict], Dict[str, object]]:
    """
    Verdict sentimen per kutipan terhadap preferensi user.

    Return (verdicts, telemetry) dengan verdicts[quote_key(kutipan)] = {
        'label': 'supporting' | 'caveat' | 'irrelevant',
        'sentiment': 'positif' | 'negatif' | 'netral',
        'clause': klausa yang menentukan label (selalu potongan teks asli),
        'source': 'absa' | 'cache' | 'triaged_accept',
    }

    Kutipan tanpa verdict (ABSA gagal / klausa terlalu pendek) tidak dimasukkan,
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
                'source': judged[0][1].get('source', 'absa'),
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
                'source': negative[1].get('source', 'absa'),
            }
            continue
        positive = next((pair for pair in relevant if pair[1].get('sentiment') == 'positif'), None)
        if positive is not None:
            quote_verdicts[key] = {
                'label': 'supporting',
                'sentiment': 'positif',
                'clause': positive[0],
                'source': positive[1].get('source', 'absa'),
            }
            continue
        quote_verdicts[key] = {
            'label': 'irrelevant',
            'sentiment': 'netral',
            'clause': relevant[0][0],
            'source': relevant[0][1].get('source', 'absa'),
        }

    telemetry['verdicts'] = len(quote_verdicts)
    return quote_verdicts, telemetry


def flush_cache() -> None:
    _cache.flush()
    try:
        from absa_sentiment import flush_cache as flush_absa

        flush_absa()
    except Exception:
        pass


def cache_stats() -> Dict[str, int]:
    return _cache.stats()

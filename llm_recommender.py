"""
Lapisan keputusan LLM untuk rekomendasi Cofind (input tetap pill, tanpa teks bebas).

Tahap yang disediakan modul ini:
  A. Ekspansi keyword pill oleh LLM, divalidasi terhadap kosakata korpus review
     sehingga keyword yang masuk ke retrieval selalu kata yang benar-benar ada
     di review (tidak mungkin mengarang istilah).
  B. Rerank kandidat oleh LLM: LLM memberi fit score + alasan + kutipan bukti,
     lalu skor akhir = campuran fit LLM dan skor statistik (BM25 hybrid).
  C. Konteks personalisasi dari histori user (review sendiri + favorit).
  D. Grounding check: setiap kutipan yang diklaim LLM harus benar-benar ada di
     korpus review toko tersebut, kalau tidak maka klaim itu dibuang.

Env:
  COFIND_LLM_KEYWORD_EXPANSION      aktifkan tahap A (default: true)
  COFIND_LLM_RERANK                 aktifkan tahap B (default: true)
  COFIND_LLM_PERSONALIZATION        aktifkan tahap C (default: true)
  COFIND_LLM_GROUNDING_CHECK        aktifkan tahap D (default: true)
  COFIND_LLM_RERANK_CANDIDATES      jumlah kandidat yang dinilai LLM (default: 8)
  COFIND_LLM_RERANK_WEIGHT          bobot fit LLM pada skor akhir 0..1 (default: 0.6)
  COFIND_LLM_EXPANSION_MAX_TERMS    batas frasa hasil ekspansi (default: 8)
  COFIND_LLM_EXPANSION_CACHE_TTL    TTL cache ekspansi per kombinasi pill, detik (default: 3600)
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from typing import Callable, Dict, List, Optional, Sequence

try:  # opsional, sama seperti pemakaian di app.py
    import importlib

    _repair_json = importlib.import_module('json_repair').repair_json
except Exception:  # pragma: no cover
    _repair_json = None


# --------------------------------------------------------------------------
# Konfigurasi
# --------------------------------------------------------------------------

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


def _env_float(name: str, default: float, *, min_value: float, max_value: float) -> float:
    raw = (os.getenv(name) or '').strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(min_value, min(max_value, value))


def keyword_expansion_enabled() -> bool:
    return _env_flag('COFIND_LLM_KEYWORD_EXPANSION', True)


def rerank_enabled() -> bool:
    return _env_flag('COFIND_LLM_RERANK', True)


def personalization_enabled() -> bool:
    return _env_flag('COFIND_LLM_PERSONALIZATION', True)


def grounding_check_enabled() -> bool:
    return _env_flag('COFIND_LLM_GROUNDING_CHECK', True)


def rerank_candidate_pool() -> int:
    return _env_int('COFIND_LLM_RERANK_CANDIDATES', 8, min_value=2, max_value=20)


def rerank_weight() -> float:
    return _env_float('COFIND_LLM_RERANK_WEIGHT', 0.6, min_value=0.0, max_value=1.0)


def expansion_max_terms() -> int:
    return _env_int('COFIND_LLM_EXPANSION_MAX_TERMS', 8, min_value=1, max_value=20)


def expansion_cache_ttl_seconds() -> int:
    return _env_int('COFIND_LLM_EXPANSION_CACHE_TTL', 3600, min_value=0, max_value=86400)


def pipeline_config() -> Dict[str, object]:
    """Ringkasan flag pipeline untuk telemetry / endpoint status."""
    return {
        'keyword_expansion': keyword_expansion_enabled(),
        'rerank': rerank_enabled(),
        'personalization': personalization_enabled(),
        'grounding_check': grounding_check_enabled(),
        'rerank_candidate_pool': rerank_candidate_pool(),
        'rerank_weight': rerank_weight(),
        'expansion_max_terms': expansion_max_terms(),
    }


# --------------------------------------------------------------------------
# Tahap D: grounding — semua klaim tekstual harus bisa dilacak ke review asli
# --------------------------------------------------------------------------

_PUNCT_RE = re.compile(r'[^0-9a-z\u00c0-\u024f\s]')
_ELLIPSIS_RE = re.compile(r'\.\.\.|\u2026')
_QUOTED_SPAN_RE = re.compile(r'"([^"\n]{8,})"|\u201c([^\u201d\n]{8,})\u201d')
_MIN_FRAGMENT_TOKENS = 3


def normalize_for_grounding(text: object) -> str:
    """Lowercase + buang tanda baca supaya perbandingan kutipan tahan beda format."""
    lowered = str(text or '').lower().replace('-', ' ')
    cleaned = _PUNCT_RE.sub(' ', lowered)
    return re.sub(r'\s+', ' ', cleaned).strip()


def shop_corpus_text(reviews: Sequence[dict]) -> str:
    """Gabungan teks review satu toko sebagai basis pengecekan grounding."""
    parts = []
    for review in reviews or []:
        if isinstance(review, dict):
            text = str(review.get('text') or review.get('review_text') or '').strip()
        else:
            text = str(review or '').strip()
        if text:
            parts.append(text)
    return ' '.join(parts)


def text_is_grounded(candidate: object, corpus_text: object, *, min_overlap_ratio: float = 0.7) -> bool:
    """
    True bila `candidate` benar-benar berasal dari `corpus_text`.
    Kutipan yang dipotong ellipsis diperiksa per fragmen; fragmen terlalu pendek
    jatuh ke pengecekan rasio token supaya tidak menolak kutipan pendek yang sah.
    """
    raw = str(candidate or '').strip()
    corpus = normalize_for_grounding(corpus_text)
    if not raw or not corpus:
        return False

    checked = 0
    for fragment in _ELLIPSIS_RE.split(raw):
        normalized = normalize_for_grounding(fragment)
        if len(normalized.split()) < _MIN_FRAGMENT_TOKENS:
            continue
        checked += 1
        if normalized not in corpus:
            return False
    if checked:
        return True

    candidate_tokens = [t for t in normalize_for_grounding(raw).split() if len(t) > 1]
    if not candidate_tokens:
        return False
    corpus_tokens = set(corpus.split())
    hits = sum(1 for token in candidate_tokens if token in corpus_tokens)
    return (hits / len(candidate_tokens)) >= min_overlap_ratio


def extract_quoted_spans(text: object) -> List[str]:
    """Semua potongan di dalam tanda kutip (lurus maupun typografis)."""
    spans = []
    for straight, curly in _QUOTED_SPAN_RE.findall(str(text or '')):
        span = (straight or curly or '').strip()
        if span:
            spans.append(span)
    return spans


def ungrounded_quotes(text: object, corpus_text: object) -> List[str]:
    """Kutipan pada `text` yang tidak bisa ditemukan di korpus review."""
    corpus = normalize_for_grounding(corpus_text)
    if not corpus:
        return extract_quoted_spans(text)
    return [span for span in extract_quoted_spans(text) if not text_is_grounded(span, corpus)]


# --------------------------------------------------------------------------
# Parsing JSON output LLM
# --------------------------------------------------------------------------

def _extract_json_fragment(raw_text: object, *, expected: str) -> str:
    text = str(raw_text or '').strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text).strip()
    pattern = r'\[[\s\S]*\]' if expected == 'array' else r'\{[\s\S]*\}'
    match = re.search(pattern, text)
    return match.group(0).strip() if match else text


def _loads_json(raw_text: object, *, expected: str):
    """Parse JSON output LLM tanpa panggilan LLM tambahan."""
    fragment = _extract_json_fragment(raw_text, expected=expected)
    if not fragment:
        return None
    try:
        return json.loads(fragment)
    except Exception:
        pass
    if _repair_json is not None:
        try:
            return json.loads(str(_repair_json(fragment, skip_json_loads=True)))
        except Exception:
            return None
    return None


def _parse_json_array(raw_text: object, parse_json_fn: Optional[Callable]) -> Optional[list]:
    if parse_json_fn is not None:
        try:
            parsed = parse_json_fn(raw_text, expected='array')
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                for key in ('recommendations', 'keywords', 'results', 'items'):
                    if isinstance(parsed.get(key), list):
                        return parsed[key]
        except Exception:
            pass
    parsed = _loads_json(raw_text, expected='array')
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for key in ('recommendations', 'keywords', 'results', 'items'):
            if isinstance(parsed.get(key), list):
                return parsed[key]
    return None


# --------------------------------------------------------------------------
# Tahap A: ekspansi keyword pill oleh LLM (kosakata tertutup + tervalidasi korpus)
# --------------------------------------------------------------------------

_EXPANSION_SYSTEM_PROMPT = (
    'Anda mesin ekspansi kata kunci pencarian untuk aplikasi rekomendasi coffee shop Indonesia. '
    'Anda hanya boleh mengeluarkan frasa bahasa Indonesia sehari-hari yang wajar ditulis pengunjung '
    'di ulasan coffee shop. Jawab HANYA JSON array of string, tanpa markdown dan tanpa penjelasan.'
)


def _expansion_user_prompt(pill_labels_line: str, lexicon_line: str, max_terms: int) -> str:
    return (
        f'Konteks aktivitas yang dipilih user: {pill_labels_line}\n'
        f'Kata kunci yang sudah dipakai sistem (jangan diulang atau diubah bentuknya): {lexicon_line}\n\n'
        f'Tugas: tambahkan maksimal {max_terms} frasa pencarian baru yang membantu menemukan '
        'ulasan pengunjung tentang konteks aktivitas di atas.\n'
        'Aturan ketat:\n'
        '- 1 sampai 3 kata per frasa, huruf kecil semua.\n'
        '- Harus frasa yang realistis muncul di ulasan coffee shop Indonesia (boleh bahasa gaul umum).\n'
        '- Nada netral atau positif. Jangan keluarkan frasa keluhan, larangan, atau kata negatif.\n'
        '- Jangan menyebut nama coffee shop, nama kota, merek, atau angka.\n'
        '- Jangan mengarang fasilitas yang tidak lazim ada di coffee shop.\n'
        '- Tanpa duplikat dan tanpa sinonim dari daftar kata kunci yang sudah dipakai sistem.\n'
        'Format keluaran: ["frasa satu", "frasa dua"]'
    )


_expansion_cache: Dict[str, tuple] = {}
_expansion_cache_lock = threading.Lock()


def _expansion_cache_key(pills: Sequence[str], max_terms: int) -> str:
    normalized = sorted(str(p or '').strip().lower() for p in pills or [] if str(p or '').strip())
    return '+'.join(normalized) + f'::{max_terms}'


def _expansion_cache_get(key: str) -> Optional[List[str]]:
    ttl = expansion_cache_ttl_seconds()
    if ttl <= 0:
        return None
    with _expansion_cache_lock:
        entry = _expansion_cache.get(key)
    if not entry:
        return None
    stored_at, terms = entry
    if (time.time() - stored_at) > ttl:
        with _expansion_cache_lock:
            _expansion_cache.pop(key, None)
        return None
    return list(terms)


def _expansion_cache_put(key: str, terms: Sequence[str]) -> None:
    if expansion_cache_ttl_seconds() <= 0:
        return
    with _expansion_cache_lock:
        _expansion_cache[key] = (time.time(), list(terms))


def _terms_grounded_in_vocabulary(terms: Sequence[str], vocabulary: Optional[set]) -> tuple:
    """Pisahkan frasa yang semua tokennya ada di kosakata korpus review."""
    if not vocabulary:
        return list(terms), []
    kept, rejected = [], []
    for term in terms:
        tokens = [t for t in str(term or '').split() if len(t) > 1]
        if tokens and all(token in vocabulary for token in tokens):
            kept.append(term)
        else:
            rejected.append(term)
    return kept, rejected


def expand_pill_keywords(
    pills: Sequence[str],
    *,
    pill_labels: Dict[str, str],
    pill_lexicon: Sequence[str],
    chat_fn: Callable[..., str],
    sanitize_keywords: Callable[[Sequence[str]], List[str]],
    corpus_vocabulary: Optional[set] = None,
    parse_json_fn: Optional[Callable] = None,
    max_terms: Optional[int] = None,
    use_cache: bool = True,
) -> Dict[str, object]:
    """
    Tahap A. LLM mengusulkan frasa pencarian tambahan untuk kombinasi pill,
    lalu setiap frasa harus lolos tiga saringan sebelum dipakai retrieval:
      1. sanitizer aplikasi (buang frasa negatif / bentuk tidak valid)
      2. bukan pengulangan leksikon pill yang sudah dipakai
      3. semua tokennya ada di kosakata korpus review (kalau korpus tersedia)
    """
    result: Dict[str, object] = {
        'keywords': [],
        'source': 'disabled',
        'raw_count': 0,
        'rejected_lexicon': 0,
        'rejected_vocabulary': 0,
        'rejected_vocabulary_sample': [],
        'latency_ms': 0.0,
        'error': None,
    }
    if not pills or not keyword_expansion_enabled():
        return result

    limit = max_terms if max_terms is not None else expansion_max_terms()
    cache_key = _expansion_cache_key(pills, limit)
    raw_terms: Optional[List[str]] = _expansion_cache_get(cache_key) if use_cache else None
    started = time.perf_counter()

    if raw_terms is None:
        labels_line = ', '.join(str(pill_labels.get(p, p)) for p in pills) or '-'
        lexicon_sample = list(dict.fromkeys(str(k or '').strip() for k in pill_lexicon or [] if str(k or '').strip()))
        lexicon_line = ', '.join(lexicon_sample[:60]) or '-'
        try:
            raw = chat_fn(
                messages=[
                    {'role': 'system', 'content': _EXPANSION_SYSTEM_PROMPT},
                    {'role': 'user', 'content': _expansion_user_prompt(labels_line, lexicon_line, limit)},
                ],
                max_tokens=220,
                temperature=0.2,
            )
        except Exception as err:
            result['source'] = 'error'
            result['error'] = str(err)[:200]
            result['latency_ms'] = round((time.perf_counter() - started) * 1000, 1)
            return result

        parsed = _parse_json_array(raw, parse_json_fn)
        if parsed is None:
            result['source'] = 'error'
            result['error'] = 'parse_failed'
            result['latency_ms'] = round((time.perf_counter() - started) * 1000, 1)
            return result

        raw_terms = []
        for item in parsed:
            if isinstance(item, str):
                raw_terms.append(item)
            elif isinstance(item, dict):
                value = item.get('keyword') or item.get('term') or item.get('phrase')
                if isinstance(value, str):
                    raw_terms.append(value)
        _expansion_cache_put(cache_key, raw_terms)
        result['source'] = 'llm'
    else:
        result['source'] = 'cache'

    result['raw_count'] = len(raw_terms)
    sanitized = sanitize_keywords(raw_terms) or []

    lexicon_norm = {str(k or '').strip().lower() for k in pill_lexicon or []}
    deduped, rejected_lexicon = [], 0
    for term in sanitized:
        if str(term).strip().lower() in lexicon_norm:
            rejected_lexicon += 1
            continue
        deduped.append(term)

    grounded, rejected_vocabulary = _terms_grounded_in_vocabulary(deduped, corpus_vocabulary)

    result['keywords'] = list(dict.fromkeys(grounded))[:limit]
    result['rejected_lexicon'] = rejected_lexicon
    result['rejected_vocabulary'] = len(rejected_vocabulary)
    result['rejected_vocabulary_sample'] = rejected_vocabulary[:5]
    result['latency_ms'] = round((time.perf_counter() - started) * 1000, 1)
    return result


def corpus_vocabulary_from_tokens(tokenized_corpus: Sequence[Sequence[str]]) -> set:
    """Kosakata gabungan korpus BM25 untuk validasi keyword hasil LLM."""
    vocabulary = set()
    for document in tokenized_corpus or []:
        for token in document or []:
            if token and token != '__empty__':
                vocabulary.add(token)
    return vocabulary


# --------------------------------------------------------------------------
# Tahap C: konteks personalisasi dari histori user
# --------------------------------------------------------------------------

def build_user_taste_profile(user_id: object, *, max_reviews: int = 6, max_favorites: int = 6) -> Dict[str, object]:
    """
    Ringkasan selera user dari data yang sudah dimiliki aplikasi:
    review yang pernah ia tulis dan coffee shop favoritnya.
    Dipakai hanya sebagai konteks preferensi, bukan sumber fakta tentang kandidat.
    """
    profile: Dict[str, object] = {
        'enabled': personalization_enabled(),
        'has_history': False,
        'avg_rating_given': None,
        'review_lines': [],
        'favorite_names': [],
    }
    if not profile['enabled']:
        return profile
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return profile

    try:
        from db_backend import get_connection

        conn = get_connection()
        try:
            cursor = conn.cursor()
            review_rows = cursor.execute(
                'SELECT r.rating, r.review_text, c.name '
                'FROM reviews r LEFT JOIN coffee_shops c ON r.place_id = c.place_id '
                'WHERE r.user_id = ? ORDER BY r.created_at DESC LIMIT ?',
                (uid, int(max_reviews)),
            ).fetchall()
            favorite_rows = cursor.execute(
                'SELECT c.name FROM favorites f '
                'LEFT JOIN coffee_shops c ON f.place_id = c.place_id '
                'WHERE f.user_id = ? ORDER BY f.added_at DESC LIMIT ?',
                (uid, int(max_favorites)),
            ).fetchall()
        finally:
            conn.close()
    except Exception as err:
        profile['error'] = str(err)[:200]
        return profile

    ratings = []
    review_lines = []
    for row in review_rows or []:
        rating, review_text, shop_name = (list(row) + [None, None, None])[:3]
        try:
            if rating is not None:
                ratings.append(float(rating))
        except (TypeError, ValueError):
            pass
        text = re.sub(r'\s+', ' ', str(review_text or '')).strip()
        if not text:
            continue
        if len(text) > 160:
            text = text[:157].rstrip() + '...'
        rating_label = f'{rating}\u2b50' if rating is not None else 'tanpa rating'
        shop_label = str(shop_name or 'coffee shop lain').strip()
        review_lines.append(f'({rating_label} di {shop_label}) "{text}"')

    favorite_names = []
    for row in favorite_rows or []:
        name = str((list(row) + [None])[0] or '').strip()
        if name and name not in favorite_names:
            favorite_names.append(name)

    profile['avg_rating_given'] = round(sum(ratings) / len(ratings), 2) if ratings else None
    profile['review_lines'] = review_lines
    profile['favorite_names'] = favorite_names
    profile['has_history'] = bool(review_lines or favorite_names)
    return profile


def format_user_taste_prompt_block(taste_profile: Optional[Dict[str, object]]) -> str:
    """Blok prompt personalisasi; string kosong bila user belum punya histori."""
    profile = taste_profile or {}
    if not profile.get('enabled') or not profile.get('has_history'):
        return ''

    lines = [
        'Konteks selera user (hanya untuk memahami preferensi; JANGAN dipakai sebagai fakta tentang kandidat):',
    ]
    if profile.get('avg_rating_given') is not None:
        lines.append(f"- Rata-rata rating yang biasa user berikan: {profile['avg_rating_given']}/5")
    for line in (profile.get('review_lines') or [])[:4]:
        lines.append(f'- Ulasan user sebelumnya: {line}')
    favorites = profile.get('favorite_names') or []
    if favorites:
        lines.append(f"- Coffee shop favorit user: {', '.join(favorites[:5])}")
    return '\n'.join(lines)


# --------------------------------------------------------------------------
# Tahap B: rerank kandidat oleh LLM
# --------------------------------------------------------------------------

_RERANK_SYSTEM_PROMPT = (
    'Anda mesin pemeringkat rekomendasi coffee shop Cofind. '
    'Anda memilih dan mengurutkan kandidat HANYA berdasarkan data dan kutipan review yang diberikan. '
    'Jangan menambah kandidat, jangan mengarang fasilitas, jangan mengarang kutipan. '
    'Jawab HANYA JSON array valid tanpa markdown dan tanpa penjelasan di luar JSON.'
)

_UNGROUNDED_FIT_PENALTY = 1.5
_MAX_REASON_CHARS = 240
_BANNED_REASON_FRAGMENTS = ('place_id', '```', 'json', '{', '}', '[fasilitas]', '[review]')
# Alasan tanpa detail konkret tidak membantu user dan tidak bisa diverifikasi.
_GENERIC_REASON_RE = re.compile(
    r'(banyak|beberapa|satu|dua|tiga|sejumlah)\s+(review|ulasan)|'
    r'(review|ulasan)\s+menyebut(kan)?\s+(tempat|coffee shop)\s+ini\s+cocok',
    re.IGNORECASE,
)


def _quote_candidates_for_prompt(evidence: Dict[str, object], *, limit: int, quote_chars: int) -> List[Dict[str, object]]:
    """Kutipan review untuk satu kandidat, diprioritaskan dari bukti yang paling relevan."""
    ordered_keys = (
        'search_keyword_matches',
        'llm_keyword_matches',
        'review_quotes',
        'positive_review_quotes',
        'negative_review_quotes',
    )
    quotes: List[Dict[str, object]] = []
    seen = set()
    for key in ordered_keys:
        for row in (evidence or {}).get(key) or []:
            if len(quotes) >= limit:
                return quotes
            if not isinstance(row, dict):
                continue
            text = re.sub(r'\s+', ' ', str(row.get('quote') or row.get('text') or '')).strip()
            if len(text) < 12:
                continue
            dedupe_key = text.lower()[:120]
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            if len(text) > quote_chars:
                text = text[: quote_chars - 3].rstrip() + '...'
            quotes.append({'text': text, 'rating': row.get('rating')})
    return quotes


def _candidate_block(index: int, candidate: Dict[str, object], quotes: Sequence[Dict[str, object]]) -> str:
    """
    Blok bukti satu kandidat. Tiga hal yang disengaja di sini:
    skor statistik sistem tidak dibocorkan (kalau ditampilkan, LLM cenderung menyalin
    urutan statistik alih-alih menilai bukti); kandidat dirujuk dengan id angka, bukan
    place_id panjang yang mudah salah tulis dan memakan token output; dan kutipan diberi
    nomor supaya LLM menyitir lewat nomor, bukan menulis ulang teksnya.
    """
    evidence = candidate.get('evidence') or {}
    pill_stats = evidence.get('pill_stats') or []
    category_ratings = evidence.get('category_ratings') or {}

    stat_lines = []
    for stat in pill_stats[:4]:
        if not isinstance(stat, dict):
            continue
        label = str(stat.get('pill_label') or stat.get('pill') or 'konteks')
        line = f"    - {label}: {stat.get('keyword_review_hits', 0)} review menyebut kata terkait"
        if stat.get('category_field') and stat.get('category_avg') is not None:
            line += f", {stat['category_field']} rata-rata {stat['category_avg']}"
        stat_lines.append(line)
    if not stat_lines:
        stat_lines = ['    - (tidak ada sinyal pill yang cocok)']

    category_line = ', '.join(
        f'{key}={value}' for key, value in category_ratings.items() if value is not None
    ) or 'tidak ada'

    quote_lines = []
    for position, quote in enumerate(quotes or [], 1):
        rating = quote.get('rating')
        rating_label = str(rating) if rating not in (None, '') else '?'
        quote_lines.append(f'    [{position}] (rating {rating_label}) "{quote.get("text")}"')
    if not quote_lines:
        quote_lines = ['    (tidak ada kutipan review)']

    return (
        f"id={index} | {candidate.get('name') or '-'}\n"
        f"  jumlah review: {evidence.get('review_count', 0)}, rata-rata rating user: {evidence.get('avg_user_rating')}\n"
        f"  rating kategori: {category_line}\n"
        f"  sinyal per konteks:\n" + '\n'.join(stat_lines) + '\n'
        f"  kutipan review bernomor (satu-satunya sumber bukti kandidat ini):\n" + '\n'.join(quote_lines)
    )


def _clean_reason(raw_reason: object) -> str:
    reason = re.sub(r'\s+', ' ', str(raw_reason or '')).strip()
    reason = re.sub(r'[*#`]+', '', reason).strip()
    if not reason:
        return ''
    lowered = reason.lower()
    if any(fragment in lowered for fragment in _BANNED_REASON_FRAGMENTS):
        return ''
    if _GENERIC_REASON_RE.search(reason):
        return ''
    if len(reason) > _MAX_REASON_CHARS:
        reason = reason[: _MAX_REASON_CHARS - 3].rstrip() + '...'
    return reason


def _matched_pills_from_stats(candidate: Dict[str, object], valid_pills: set) -> List[str]:
    """Pill yang punya bukti keyword di review kandidat (berdasarkan pill_stats)."""
    matched = []
    for stat in ((candidate.get('evidence') or {}).get('pill_stats') or []):
        if not isinstance(stat, dict):
            continue
        pill = str(stat.get('pill') or '').strip().lower()
        if pill in valid_pills and pill not in matched and (stat.get('keyword_review_hits') or 0) > 0:
            matched.append(pill)
    return matched


def _quote_index_value(raw_value: object) -> Optional[int]:
    """Nomor kutipan dari output LLM (menerima angka maupun string seperti "[2]")."""
    if isinstance(raw_value, bool) or raw_value is None:
        return None
    if isinstance(raw_value, (int, float)):
        return int(raw_value)
    match = re.search(r'\d+', str(raw_value))
    return int(match.group(0)) if match else None


def _clamp_fit_score(raw_value: object) -> float:
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(10.0, value))


def llm_rerank_candidates(
    candidates: Sequence[Dict[str, object]],
    pills: Sequence[str],
    *,
    pill_labels: Dict[str, str],
    chat_fn: Callable[..., str],
    parse_json_fn: Optional[Callable] = None,
    user_taste_block: str = '',
    keyword_line: str = '',
    max_candidates: Optional[int] = None,
    quotes_per_candidate: int = 4,
    quote_chars: int = 220,
    grounding: Optional[bool] = None,
) -> Optional[Dict[str, object]]:
    """
    Tahap B. LLM menilai setiap kandidat (fit 0-10 + alasan + kutipan bukti),
    lalu skor akhir dicampur dengan skor statistik agar keputusan LLM tetap
    berlabuh pada sinyal review yang terukur.

    Return None bila rerank tidak bisa dipakai (nonaktif / LLM gagal / output tidak valid),
    sehingga pemanggil memakai urutan statistik seperti sebelumnya.
    """
    if not candidates or not rerank_enabled():
        return None

    pool_size = max_candidates if max_candidates is not None else rerank_candidate_pool()
    pool = list(candidates)[:pool_size]
    if not pool:
        return None

    grounding_active = grounding_check_enabled() if grounding is None else bool(grounding)
    labels_line = ', '.join(str(pill_labels.get(p, p)) for p in pills or []) or 'preferensi umum'
    # Urutan prompt distabilkan oleh place_id, bukan skor, supaya posisi kandidat
    # tidak memberi petunjuk peringkat statistik kepada LLM.
    prompt_order = sorted(pool, key=lambda c: str(c.get('place_id') or ''))
    quotes_by_place: Dict[str, List[Dict[str, object]]] = {}
    blocks = []
    for idx, candidate in enumerate(prompt_order, 1):
        quotes = _quote_candidates_for_prompt(
            candidate.get('evidence') or {},
            limit=quotes_per_candidate,
            quote_chars=quote_chars,
        )
        quotes_by_place[str(candidate.get('place_id'))] = quotes
        blocks.append(_candidate_block(idx, candidate, quotes))

    prompt_parts = [
        f'Preferensi aktivitas user: {labels_line}',
        f'Kata kunci pencarian yang dipakai sistem: {keyword_line or "tidak ada"}',
    ]
    if user_taste_block:
        prompt_parts.append(user_taste_block)
    prompt_parts.append('Kandidat coffee shop dan buktinya:\n\n' + '\n\n'.join(blocks))
    prompt_parts.append(
        'Tugas: nilai seberapa cocok setiap kandidat dengan preferensi user, lalu urutkan dari paling cocok.\n'
        'Aturan ketat:\n'
        '- Urutan kandidat di atas acak dan TIDAK mencerminkan kualitas. Nilai murni dari bukti review.\n'
        f'- Wajib menilai SEMUA {len(pool)} kandidat, satu objek JSON per kandidat, tanpa kandidat baru.\n'
        '- id adalah angka kandidat (id=...) yang tertulis di atas.\n'
        '- fit_score bilangan 0 sampai 10. Bukti lemah untuk preferensi user berarti fit_score rendah.\n'
        '- Jika kutipan menunjukkan hambatan untuk aktivitas yang diminta user (misalnya berisik saat '
        'user ingin kerja), turunkan fit_score kandidat itu meskipun review lain positif.\n'
        '- evidence_index wajib berupa nomor kutipan milik kandidat itu sendiri (angka dalam kurung siku). '
        'Jangan menulis ulang isi kutipan.\n'
        '- reason maksimal 18 kata bahasa Indonesia dan wajib menyebut detail konkret dari kutipan '
        'kandidat itu, misalnya "ruangan AC di lantai 2" atau "colokan di tiap meja". '
        'Dilarang menulis kalimat umum seperti "banyak review menyebut cocok untuk kerja".\n'
        '- reason setiap kandidat harus berbeda.\n'
        'Format keluaran, satu objek per kandidat: '
        '[{"id":1,"fit_score":8.5,"reason":"...","evidence_index":2}]'
    )

    started = time.perf_counter()
    try:
        raw = chat_fn(
            messages=[
                {'role': 'system', 'content': _RERANK_SYSTEM_PROMPT},
                {'role': 'user', 'content': '\n\n'.join(prompt_parts)},
            ],
            # Output tumbuh linear terhadap jumlah kandidat yang harus dinilai.
            # Catatan: llm_backend memotong nilai ini ke HF_LLM_MAX_CHAT_TOKENS_CAP.
            max_tokens=min(1000, 140 + 70 * len(pool)),
            temperature=0.1,
        )
    except Exception as err:
        return {
            'ranked': None,
            'telemetry': {
                'backend': 'llm_failed',
                'error': str(err)[:200],
                'latency_ms': round((time.perf_counter() - started) * 1000, 1),
            },
        }

    parsed = _parse_json_array(raw, parse_json_fn)
    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    if not isinstance(parsed, list) or not parsed:
        return {
            'ranked': None,
            'telemetry': {'backend': 'llm_invalid', 'error': 'parse_failed', 'latency_ms': latency_ms},
        }

    candidate_by_place_id = {str(c.get('place_id')): c for c in pool if c.get('place_id')}
    candidate_by_prompt_id = {idx: c for idx, c in enumerate(prompt_order, 1)}
    valid_pills = {str(p or '').strip().lower() for p in pills or []}
    corpus_cache: Dict[str, str] = {}

    fits: Dict[str, Dict[str, object]] = {}
    unknown_place_ids = 0
    ungrounded_quotes_count = 0
    dropped_reasons = 0
    seen_reasons = set()

    for item in parsed:
        if not isinstance(item, dict):
            continue
        prompt_id = _quote_index_value(item.get('id'))
        candidate = candidate_by_prompt_id.get(prompt_id) if prompt_id is not None else None
        if candidate is None:
            candidate = candidate_by_place_id.get(str(item.get('place_id') or '').strip())
        if candidate is None:
            unknown_place_ids += 1
            continue
        place_id = str(candidate.get('place_id'))
        if place_id in fits:
            continue

        fit_score = _clamp_fit_score(item.get('fit_score', item.get('score')))
        reason = _clean_reason(item.get('reason') or item.get('alasan'))
        # Alasan identik untuk dua kandidat berarti LLM tidak benar-benar membedakan bukti.
        reason_key = normalize_for_grounding(reason)
        if reason and reason_key in seen_reasons:
            reason = ''
        elif reason:
            seen_reasons.add(reason_key)
        if not reason:
            dropped_reasons += 1

        # Bukti disitir lewat nomor kutipan; teksnya diambil dari data kami sendiri
        # sehingga tidak mungkin dikarang. Kutipan verbatim hanya jalur cadangan.
        available_quotes = quotes_by_place.get(place_id) or []
        quote = ''
        quote_grounded = True
        quote_index = _quote_index_value(item.get('evidence_index'))
        if quote_index is not None and 1 <= quote_index <= len(available_quotes):
            quote = str(available_quotes[quote_index - 1].get('text') or '')
        else:
            verbatim = re.sub(r'\s+', ' ', str(item.get('evidence_quote') or item.get('quote') or '')).strip()
            if verbatim:
                if place_id not in corpus_cache:
                    corpus_cache[place_id] = shop_corpus_text((candidate.get('profile') or {}).get('reviews') or [])
                if not grounding_active or text_is_grounded(verbatim, corpus_cache[place_id]):
                    quote = verbatim
        if not quote and available_quotes:
            quote_grounded = False
            ungrounded_quotes_count += 1
            fit_score = max(0.0, fit_score - _UNGROUNDED_FIT_PENALTY)

        matched = []
        raw_matched = item.get('matched_pills') or item.get('pills') or []
        if isinstance(raw_matched, str):
            raw_matched = [raw_matched]
        for pill in raw_matched:
            key = str(pill or '').strip().lower()
            if key in valid_pills and key not in matched:
                matched.append(key)
        if not matched:
            # Skema prompt tidak lagi meminta matched_pills (hemat token output),
            # jadi ambil dari statistik keyword yang sudah terukur.
            matched = _matched_pills_from_stats(candidate, valid_pills)

        fits[place_id] = {
            'fit_score': round(fit_score, 2),
            'reason': reason,
            'evidence_quote': quote,
            'evidence_grounded': quote_grounded,
            'matched_pills': matched,
        }

    if not fits:
        return {
            'ranked': None,
            'telemetry': {
                'backend': 'llm_invalid',
                'error': 'no_valid_item',
                'unknown_place_ids': unknown_place_ids,
                'latency_ms': latency_ms,
            },
        }

    weight = rerank_weight()
    ranked: List[Dict[str, object]] = []
    for position, candidate in enumerate(pool):
        place_id = str(candidate.get('place_id'))
        hybrid_score = float(candidate.get('score') or 0.0)
        fit = fits.get(place_id)
        entry = dict(candidate)
        if fit is None:
            # Kandidat yang tidak dinilai LLM tetap dipertahankan pada skor statistiknya.
            entry['final_score'] = round(hybrid_score, 4)
            entry['llm_fit'] = None
        else:
            blended = weight * (fit['fit_score'] / 10.0) + (1.0 - weight) * hybrid_score
            entry['final_score'] = round(blended, 4)
            entry['llm_fit'] = dict(fit, hybrid_score=round(hybrid_score, 4))
        entry['hybrid_rank'] = position + 1
        ranked.append(entry)

    ranked.sort(key=lambda item: (-(item.get('final_score') or 0.0), item.get('hybrid_rank') or 0))
    for position, entry in enumerate(ranked, 1):
        entry['llm_rank'] = position
        if isinstance(entry.get('llm_fit'), dict):
            entry['llm_fit']['rank'] = position
            entry['llm_fit']['hybrid_rank'] = entry['hybrid_rank']

    order_changed = any(entry['llm_rank'] != entry['hybrid_rank'] for entry in ranked)
    return {
        'ranked': ranked,
        'telemetry': {
            'backend': 'llm',
            'candidates': len(pool),
            'scored_by_llm': len(fits),
            'unknown_place_ids': unknown_place_ids,
            'ungrounded_quotes': ungrounded_quotes_count,
            'dropped_reasons': dropped_reasons,
            'weight': weight,
            'order_changed': order_changed,
            'grounding_check': grounding_active,
            'latency_ms': latency_ms,
        },
    }

"""
Penanganan kata kunci free text yang tidak standar (negatif, presuposis palsu, di luar domain).

Dipakai setelah extract_search_intent: menggabungkan label dari LLM dengan heuristik
deterministik supaya pipeline tetap punya jalur fallback bila LLM off/gagal.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence

from hybrid_retrieval import review_text

QUERY_CLASS_STANDARD = 'standard'
QUERY_CLASS_NEGATIVE = 'negative_sentiment'
QUERY_CLASS_FALSE_PRESUP = 'false_presupposition'
QUERY_CLASS_OFF_DOMAIN = 'off_domain'

_VALID_QUERY_CLASSES = frozenset({
    QUERY_CLASS_STANDARD,
    QUERY_CLASS_NEGATIVE,
    QUERY_CLASS_FALSE_PRESUP,
    QUERY_CLASS_OFF_DOMAIN,
})

_TOKEN_RE = re.compile(r'[a-z0-9]+', re.IGNORECASE)

_FILLER_TOKENS = frozenset({
    'cari', 'coffee', 'shop', 'coffeeshop', 'kafe', 'cafe', 'tempat', 'yang', 'ada',
    'di', 'untuk', 'dan', 'atau', 'dengan', 'paling', 'banget', 'sih', 'dong', 'deh',
    'tolong', 'mau', 'pengen', 'pingin', 'butuh', 'cariin', 'carikan',
})

_DOMAIN_HINTS = frozenset({
    'kopi', 'coffee', 'cafe', 'kafe', 'espresso', 'latte', 'wifi', 'wfc', 'colokan',
    'stopkontak', 'tenang', 'ramai', 'kerja', 'belajar', 'nugas', 'meeting', 'rapat',
    'parkir', 'musholla', 'toilet', 'ac', 'instagram', 'estetik', 'suasana', 'rating',
    'ulasan', 'review', 'jelek', 'buruk', 'bagus', 'enak', 'murah', 'mahal', 'hidden',
    'gem', 'nongkrong', 'nongki', 'keluarga', 'anak', 'game', 'gaming', 'roasting',
})

_NEGATIVE_SUPERLATIVE_RE = re.compile(
    r'\b(?:paling|ter(?:buruk|jelek|parah|mengecewakan|jeleknya)|'
    r'worst|jelek(?:nya| banget)?|buruk(?:nya| banget)?|'
    r'paling\s+(?:buruk|jelek|parah|mengecewakan)|'
    r'kurang\s+(?:bagus|enak|recommended|direkomendasikan))\b',
    re.IGNORECASE,
)

_GIBBERISH_RE = re.compile(r'^[a-z0-9\s]{1,50}$', re.IGNORECASE)


def _normalize_class(raw: object) -> str:
    value = str(raw or '').strip().lower()
    if value in _VALID_QUERY_CLASSES:
        return value
    aliases = {
        'negative': QUERY_CLASS_NEGATIVE,
        'negative_ranking': QUERY_CLASS_NEGATIVE,
        'impossible': QUERY_CLASS_FALSE_PRESUP,
        'false_presupposition': QUERY_CLASS_FALSE_PRESUP,
        'off_domain': QUERY_CLASS_OFF_DOMAIN,
        'nonsense': QUERY_CLASS_OFF_DOMAIN,
        'unanswerable': QUERY_CLASS_OFF_DOMAIN,
    }
    return aliases.get(value, QUERY_CLASS_STANDARD)


def _content_tokens(text: str) -> List[str]:
    tokens = [t.lower() for t in _TOKEN_RE.findall(str(text or '')) if len(t) > 1]
    return [t for t in tokens if t not in _FILLER_TOKENS]


def classify_query_heuristic(raw: str) -> str:
    """Klasifikasi cepat tanpa LLM — dipakai sebagai fallback dan untuk negatif."""
    text = str(raw or '').strip()
    if not text or not _GIBBERISH_RE.match(text):
        return QUERY_CLASS_OFF_DOMAIN
    if _NEGATIVE_SUPERLATIVE_RE.search(text):
        return QUERY_CLASS_NEGATIVE
    tokens = _content_tokens(text)
    if not tokens:
        return QUERY_CLASS_OFF_DOMAIN
    if any(t in _DOMAIN_HINTS for t in tokens):
        return QUERY_CLASS_STANDARD
    if len(tokens) == 1 and len(tokens[0]) >= 4:
        vowels = sum(1 for c in tokens[0] if c in 'aiueo')
        if vowels == 0:
            return QUERY_CLASS_OFF_DOMAIN
    if len(' '.join(tokens)) <= 3 and not any(t in _DOMAIN_HINTS for t in tokens):
        return QUERY_CLASS_OFF_DOMAIN
    return QUERY_CLASS_STANDARD


def _clean_keyword_list(items: object, *, limit: int = 8) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items or []:
        token = str(item or '').strip()
        if not token:
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(token)
        if len(out) >= limit:
            break
    return out


def merge_query_classification(
    raw: str,
    *,
    llm_query_class: object = None,
    impossible_detail: object = None,
    alternative_keywords: object = None,
) -> Dict[str, object]:
    """
    Gabungkan label LLM + heuristik menjadi keputusan routing pipeline.

    Return keys:
      query_class, impossible_detail, alternative_keywords,
      summary_framing, response_message (opsional, untuk client)
    """
    raw = str(raw or '').strip()
    heuristic = classify_query_heuristic(raw)
    llm_class = _normalize_class(llm_query_class) if llm_query_class else QUERY_CLASS_STANDARD
    detail = str(impossible_detail or '').strip()
    alts = _clean_keyword_list(alternative_keywords)

    if llm_class == QUERY_CLASS_OFF_DOMAIN and heuristic == QUERY_CLASS_NEGATIVE:
        query_class = QUERY_CLASS_NEGATIVE
    elif llm_class == QUERY_CLASS_STANDARD and heuristic == QUERY_CLASS_OFF_DOMAIN:
        query_class = QUERY_CLASS_OFF_DOMAIN
    elif llm_class in (QUERY_CLASS_FALSE_PRESUP, QUERY_CLASS_OFF_DOMAIN):
        query_class = llm_class
    elif heuristic == QUERY_CLASS_NEGATIVE:
        query_class = QUERY_CLASS_NEGATIVE
    else:
        query_class = llm_class if llm_class != QUERY_CLASS_STANDARD else heuristic

    result: Dict[str, object] = {
        'query_class': query_class,
        'impossible_detail': detail or None,
        'alternative_keywords': alts,
        'summary_framing': None,
        'response_message': None,
        'early_exit': False,
    }

    if query_class == QUERY_CLASS_OFF_DOMAIN:
        result['early_exit'] = True
        result['response_message'] = (
            'Maaf, permintaan itu di luar konteks pencarian coffee shop di Cofind. '
            'Coba kata kunci singkat seperti "wifi kencang", "tenang buat kerja", '
            '"colokan banyak", atau pilih pill preferensi di atas.'
        )
        return result

    if query_class == QUERY_CLASS_NEGATIVE:
        result['summary_framing'] = (
            'User mencari tempat dengan rating/ulasan terendah atau keluhan paling banyak '
            '(bukan rekomendasi positif). Jawab jujur berdasarkan rating dan ulasan yang ada — '
            'bukan klaim objektif "paling jelek di dunia". Sorot keluhan/kutipan negatif yang '
            'tergrounding; bisa framing konstruktif: tempat yang sering dikeluhkan supaya bisa dihindari.'
        )
        result['response_message'] = (
            'Berdasarkan rating dan ulasan pengguna yang ada (bukan penilaian objektif absolut), '
            'berikut tempat yang paling sering mendapat keluhan atau rating lebih rendah:'
        )
        return result

    if query_class == QUERY_CLASS_FALSE_PRESUP:
        constraint = detail or raw
        result['summary_framing'] = (
            f'User meminta fitur/konsep yang tidak ada bukti di data ("{constraint}"). '
            'Jangan mengarang bahwa toko punya fitur itu. Jelaskan jujur bahwa aspek tersebut '
            'belum terbukti di ulasan, lalu sorot kelebihan tematik/konsep terdekat yang memang '
            'muncul di kutipan.'
        )
        if alts:
            alt_phrase = ', '.join(alts[:4])
            result['response_message'] = (
                f'Tidak ada coffee shop dengan "{constraint}" di ulasan data kami. '
                f'Berikut alternatif terdekat ({alt_phrase}) yang bisa kamu pertimbangkan:'
            )
        else:
            result['response_message'] = (
                f'Tidak ada coffee shop dengan "{constraint}" di ulasan data kami. '
                'Berikut pilihan tematik/konsep terdekat yang tersedia:'
            )
        return result

    return result


def off_domain_response_message() -> str:
    return str(merge_query_classification('', llm_query_class=QUERY_CLASS_OFF_DOMAIN)['response_message'])


def apply_false_presupposition_retrieval(
    *,
    raw_query: str,
    keywords: Sequence[str],
    dense_query: str,
    alternative_keywords: Sequence[str],
) -> Dict[str, str]:
    """Ganti token retrieval bila ada alternatif dari LLM; otherwise pertahankan intent."""
    alts = _clean_keyword_list(alternative_keywords)
    if alts:
        dense = 'coffee shop ' + ', '.join(alts[:6])
        return {'keywords': alts, 'dense_query': dense}
    kw = [str(k).strip() for k in (keywords or []) if str(k or '').strip()]
    dense = str(dense_query or '').strip() or raw_query
    return {'keywords': kw, 'dense_query': dense}


def weakness_hit_count(profile: dict) -> int:
    """Perkiraan jumlah review dengan nada keluhan umum."""
    from review_weakness import REVIEW_WEAKNESS_FRAGMENTS

    hits = 0
    for review in (profile or {}).get('reviews') or []:
        text = review_text(review).lower()
        if not text:
            continue
        if any(frag in text for frag in REVIEW_WEAKNESS_FRAGMENTS):
            hits += 1
    return hits


def sort_profiles_for_negative_query(profiles: Sequence[dict]) -> List[dict]:
    """Urutkan profil: rating rata-rata terendah dulu, lalu lebih banyak keluhan."""

    def sort_key(profile: dict):
        avg = (profile or {}).get('avg_user_rating')
        try:
            rating = float(avg) if avg is not None else 3.5
        except (TypeError, ValueError):
            rating = 3.5
        weakness = weakness_hit_count(profile)
        rc = int((profile or {}).get('review_count') or 0)
        return (rating, -weakness, -rc)

    return sorted(list(profiles or []), key=sort_key)

"""
Penanganan kata kunci free text yang tidak standar (negatif, presuposis palsu, di luar domain).

Dipakai setelah extract_search_intent: kelas query dari LLM bila intent sukses;
heuristik deterministik hanya fallback bila LLM off/gagal/tidak dipanggil.

Presupposition Verification & Query Relaxation (PVQR):
  1. Verifikasi presuposis implisit query (domain, constraint fitur, grounding superlatif).
  2. Bila gagal: abstention atau relaksasi query (reformulasi domain / drop constraint).
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

_GIBBERISH_RE = re.compile(r'^[a-z0-9, ]{1,100}$', re.IGNORECASE)

# Contoh reformulasi in-domain (Query Relaxation) bila verifikasi domain gagal.
_DEFAULT_DOMAIN_RELAXED_SUGGESTIONS: List[str] = [
    'wifi kencang buat kerja',
    'tenang buat belajar',
    'colokan banyak',
]

# Reformulasi preferensi positif bila abstention ranking negatif.
_DEFAULT_POSITIVE_RELAXED_SUGGESTIONS: List[str] = [
    'wifi kencang',
    'tenang buat kerja',
    'estetik buat foto',
]

PVQR_STRATEGY_DOMAIN_REFORMULATION = 'domain_reformulation'
PVQR_STRATEGY_CONSTRAINT_DROPPING = 'constraint_dropping'
PVQR_STRATEGY_ABSTENTION_REFORMULATION = 'abstention_with_reformulation'


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


def query_handling_for_api(handling: Dict[str, object]) -> Dict[str, object]:
    """Envelope API: kelas + metadata PVQR untuk client/telemetri."""
    payload: Dict[str, object] = {
        'class': handling.get('query_class'),
        'source': handling.get('query_class_source'),
    }
    if handling.get('impossible_detail'):
        payload['impossible_detail'] = handling.get('impossible_detail')
    pv = handling.get('presupposition_verification')
    if pv:
        payload['presupposition_verification'] = pv
    qr = handling.get('query_relaxation')
    if qr:
        payload['query_relaxation'] = qr
    return payload


def merge_query_classification(
    raw: str,
    *,
    llm_query_class: object = None,
    llm_classification_trusted: bool = False,
    impossible_detail: object = None,
    alternative_keywords: object = None,
) -> Dict[str, object]:
    """
    Tentukan kelas routing: LLM (jika trusted), else heuristik.

    Return keys:
      query_class, query_class_source ('llm' | 'heuristic'),
      impossible_detail, alternative_keywords,
      presupposition_verification, query_relaxation,
      summary_framing, response_message (opsional, untuk client)
    """
    raw = str(raw or '').strip()
    detail = str(impossible_detail or '').strip()
    alts = _clean_keyword_list(alternative_keywords)

    if llm_classification_trusted:
        query_class = _normalize_class(llm_query_class)
        class_source = 'llm'
    else:
        query_class = classify_query_heuristic(raw)
        class_source = 'heuristic'

    result: Dict[str, object] = {
        'query_class': query_class,
        'query_class_source': class_source,
        'impossible_detail': detail or None,
        'alternative_keywords': alts,
        'presupposition_verification': None,
        'query_relaxation': None,
        'summary_framing': None,
        'response_message': None,
        'early_exit': False,
    }

    if query_class == QUERY_CLASS_OFF_DOMAIN:
        relaxed = list(_DEFAULT_DOMAIN_RELAXED_SUGGESTIONS)
        result['early_exit'] = True
        result['presupposition_verification'] = {
            'verified': False,
            'failed_presuppositions': ['domain:coffee_shop_recommendation_from_reviews'],
            'rationale': (
                'Query tidak memenuhi presuposis domain: niat pencarian coffee shop '
                'yang dapat dipetakan ke preferensi/ulasan pada corpus Cofind.'
            ),
        }
        result['query_relaxation'] = {
            'strategy': PVQR_STRATEGY_DOMAIN_REFORMULATION,
            'relaxed_query_suggestions': relaxed,
            'applied': False,
        }
        examples = ', '.join(f'"{s}"' for s in relaxed[:3])
        result['response_message'] = (
            'Presuposis domain tidak terverifikasi — permintaan di luar konteks pencarian '
            'coffee shop berbasis ulasan Cofind. '
            f'Relaksasi query: coba reformulasi in-domain, misalnya {examples}, '
            'atau pilih pill preferensi di atas.'
        )
        return result

    if query_class == QUERY_CLASS_NEGATIVE:
        relaxed = list(_DEFAULT_POSITIVE_RELAXED_SUGGESTIONS)
        result['early_exit'] = True
        result['presupposition_verification'] = {
            'verified': False,
            'failed_presuppositions': ['grounded_comparative_superlative_ranking'],
            'rationale': (
                'Superlatif komparatif negatif (mis. «paling jelek») mengasumsikan ranking '
                'objektif yang dapat di-grounding penuh pada corpus ulasan terbatas; '
                'asumsi ini tidak terverifikasi dan rentan bias seleksi/sampel.'
            ),
        }
        result['query_relaxation'] = {
            'strategy': PVQR_STRATEGY_ABSTENTION_REFORMULATION,
            'relaxed_query_suggestions': relaxed,
            'applied': False,
        }
        examples = ', '.join(f'"{s}"' for s in relaxed[:3])
        result['response_message'] = (
            'Abstention: permintaan ranking negatif tidak dijawab karena tidak ada bukti '
            'grounded untuk superlatif komparatif pada dataset ulasan. '
            f'Reformulasi (query relaxation) ke preferensi positif, misalnya {examples}, '
            'atau gunakan pill preferensi.'
        )
        return result

    if query_class == QUERY_CLASS_FALSE_PRESUP:
        constraint = detail or raw
        result['presupposition_verification'] = {
            'verified': False,
            'failed_presuppositions': [constraint],
            'rationale': (
                f'Presuposis «{constraint}» gagal verifikasi: tidak ada bukti fitur/konsep '
                'tersebut pada ulasan atau metadata toko di corpus.'
            ),
        }
        result['query_relaxation'] = {
            'strategy': PVQR_STRATEGY_CONSTRAINT_DROPPING,
            'relaxed_keywords': alts,
            'applied': bool(alts),
        }
        result['summary_framing'] = (
            f'PVQR: presuposis «{constraint}» tidak terverifikasi. Jangan mengarang match literal. '
            'Jelaskan hasil verifikasi, sorot rekomendasi dari query ter-relaksasi (constraint '
            'dihapus) yang tetap tergrounding pada kutipan ulasan.'
        )
        if alts:
            alt_phrase = ', '.join(alts[:4])
            result['response_message'] = (
                f'Verifikasi presuposis: asumsi «{constraint}» tidak ditemukan pada data ulasan. '
                f'Relaksasi query (constraint dropping) → pencarian dialihkan ke: {alt_phrase}. '
                'Berikut rekomendasi dari query ter-relaksasi:'
            )
        else:
            result['response_message'] = (
                f'Verifikasi presuposis: asumsi «{constraint}» tidak ditemukan pada data ulasan. '
                'Relaksasi query terbatas; berikut pilihan tematik terdekat yang tersedia:'
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
    """Query Relaxation: ganti token retrieval ke relaxed_keywords bila tersedia."""
    alts = _clean_keyword_list(alternative_keywords)
    if alts:
        dense = 'coffee shop ' + ', '.join(alts[:6])
        return {'keywords': alts, 'dense_query': dense}
    kw = [str(k).strip() for k in (keywords or []) if str(k or '').strip()]
    dense = str(dense_query or '').strip() or raw_query
    return {'keywords': kw, 'dense_query': dense}


def weakness_hit_count(profile: dict) -> int:
    """Perkiraan jumlah review dengan nada keluhan umum.

    Hanya dipakai jalur ``negative_sentiment`` (free text), bukan penalti pill/ranking.
    """
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

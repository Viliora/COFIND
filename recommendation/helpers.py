"""Helper internal pipeline rekomendasi (diekstrak dari app.py)."""
from __future__ import annotations

import contextvars
import hashlib
import json
import os
import re
import time

try:
    import importlib
    repair_json = importlib.import_module("json_repair").repair_json
except Exception:
    repair_json = None

from llm_backend import (
    GEMINI_SUMMARY_MAX_TOKENS,
    HF_MODEL,
    LLM_BACKEND,
    begin_llm_run_route,
    get_last_llm_finish_reason,
    get_last_llm_provider,
    get_llm_run_route,
    llm_chat_completions_create,
    llm_chat_completions_create_with_usage,
    llm_is_available,
    probe_llm_for_recommendation_run,
    reset_llm_run_route,
)
from review_utils import get_reviews_for_recommendation_batch
from vote_utils import get_vote_summaries_batch
from recommendation_feedback_utils import preferences_key_from_pills
from pipeline_telemetry import (
    build_degradation_snapshot,
    full_pipeline_config,
    log_recommendation_run_json,
    new_pipeline_run_id,
    record_pipeline_run,
    summarize_llm_usage,
    begin_llm_usage_collection,
    reset_llm_usage_collection,
)
from slang_normalize import normalize_text_with_slang, tokenize_normalized
from hybrid_retrieval import (
    retrieve_top_k,
    retrieve_top_k_by_text,
    retrieve_top_k_by_negative_sentiment,
    retrieval_top_k,
    rank_reviews_for_query,
    build_sparse_query_tokens,
    text_matches_tokens,
    text_has_activity_signal,
    extract_activity_support_text,
    text_rejects_requested_activity,
    compile_activity_matcher,
    compute_pill_coverage,
    min_fit_score,
    shop_has_activity_signal,
    review_text,
)
from free_text_intent import MAX_FREE_TEXT_CHARS as FREE_TEXT_MAX_CHARS, extract_search_intent
from free_text_query_handling import (
    QUERY_CLASS_FALSE_PRESUP,
    QUERY_CLASS_NEGATIVE,
    apply_false_presupposition_retrieval,
    merge_query_classification,
)
from recommendation_coverage import merge_pill_coverage, supplemental_coverage_lines
from pill_aspect_sentiment import aggregate_reviews_sentiment
from review_weakness import review_has_weakness_near_preference_keywords as _weakness_near_keywords
from llm_recommender import (
    build_user_taste_profile,
    format_activity_context_block,
    format_user_taste_prompt_block,
    grounding_check_enabled as llm_grounding_check_enabled,
    llm_rerank_candidates,
    rerank_candidate_pool as llm_rerank_pool,
    rerank_enabled as llm_rerank_enabled,
    shop_corpus_text,
    ungrounded_quotes,
)
from metadata_prior import _NEGATION_PREFIXES, _phrase_unnegated
from semantic_match import (
    begin_encode_budget as begin_semantic_encode_budget,
    encode_budget_state as semantic_encode_budget_state,
    flush_cache as flush_semantic_cache,
    gate_config as semantic_gate_config,
    match_reviews as semantic_match_reviews,
    model_available as semantic_model_available,
    reset_encode_budget as reset_semantic_encode_budget,
    semantic_gate_enabled,
    semantic_score_cap,
)
from llm_clause_sentiment import (
    candidate_pool as clause_sentiment_pool,
    classify_quotes as classify_clause_quotes,
    clause_sentiment_enabled,
    flush_cache as flush_clause_sentiment_cache,
    quote_key as clause_quote_key,
    sentiment_config as clause_sentiment_config,
)
from pros_cons_utils import get_top_voted_pros_batch
from db_backend import dict_from_row, get_connection
from facilities_store import load_facilities_index
from logging_config import get_logger
from cache_paths import CACHE_DIR, RERANK_CACHE_EXPIRY_DAYS
from pill_config import FACILITY_ATTRIBUTE_PILLS, PILL_LABELS, PILL_MAPPING

LOG_RECOMMEND = get_logger("recommend")
LOG_METRIC = get_logger("metric")
LOG_CACHE = get_logger("cache")

COFIND_DEV_LLM_STRICT = os.getenv("COFIND_DEV_LLM_STRICT", "false").strip().lower() in (
    "1", "true", "yes", "on",
)
COFIND_MODAL_QUOTE_LLM = os.getenv("COFIND_MODAL_QUOTE_LLM", "false").strip().lower() in (
    "1", "true", "yes", "on",
)
COFIND_SUMMARY_MIN_CHARS = max(40, int(os.getenv("COFIND_SUMMARY_MIN_CHARS", "120") or "120"))
COFIND_SUMMARY_MIN_SENTENCES = 2
COFIND_SUMMARY_GEMINI_RETRY = os.getenv("COFIND_SUMMARY_GEMINI_RETRY", "true").strip().lower() in (
    "1", "true", "yes", "on",
)
COFIND_SUMMARY_GEMINI_SINGLE_SHOT = os.getenv(
    "COFIND_SUMMARY_GEMINI_SINGLE_SHOT", "false",
).strip().lower() in ("1", "true", "yes", "on")
COFIND_SUMMARY_DEBUG_LOG = os.getenv("COFIND_SUMMARY_DEBUG_LOG", "true").strip().lower() in (
    "1", "true", "yes", "on",
)
COFIND_SUMMARY_MAX_TOKENS = max(
    256, int(os.getenv("COFIND_SUMMARY_MAX_TOKENS", "480") or "480"),
)
COFIND_SUMMARY_GEMINI_MAX_TOKENS = max(
    COFIND_SUMMARY_MAX_TOKENS,
    int(os.getenv("GEMINI_SUMMARY_MAX_TOKENS", str(GEMINI_SUMMARY_MAX_TOKENS)) or GEMINI_SUMMARY_MAX_TOKENS),
)
COFIND_RECOMMEND_VERBOSE = os.getenv("COFIND_RECOMMEND_VERBOSE", "false").strip().lower() in (
    "1", "true", "yes", "on",
)

_MANUAL_UNCLEAR_MESSAGE = (
    "Belum ada rekomendasi yang cukup jelas dari ulasan untuk preferensi ini. "
    "Coba pill lain atau perjelas kata kunci pencarian."
)

_FACILITY_POPULAR_FOR_LABELS = {
    "breakfast": "sarapan",
    "lunch": "makan siang",
    "dinner": "makan malam",
    "brunch": "brunch",
    "solo_dining": "makan sendiri",
    "good_for_working_on_laptop": "wfc / kerja laptop",
    "good_for_kids": "ramah anak",
    "good_for_groups": "berkelompok",
}
_FACILITY_HIGHLIGHT_LABELS = {
    "good_coffee": "kopi enak",
    "good_desserts": "dessert enak",
    "good_tea_selection": "pilihan teh beragam",
    "sports": "cocok nonton olahraga",
    "live_music": "live music",
    "fast_service": "layanan cepat",
    "great_cocktails": "cocktail recommended",
}
_FACILITY_POPULAR_FOR_ORDER = [
    "breakfast", "brunch", "lunch", "dinner",
    "solo_dining", "good_for_working_on_laptop", "good_for_groups", "good_for_kids",
]
_FACILITY_HIGHLIGHT_ORDER = [
    "good_coffee", "good_desserts", "good_tea_selection", "live_music", "sports",
]

RERANK_CACHE_PATH = os.path.join(CACHE_DIR, "rerank_cache.json")
RERANK_CACHE_VERSION = "v3-pill-set"

PILL_TO_REVIEW_CATEGORY = {
    'belajar': 'rating_suasana',
    'kerja': 'rating_suasana',
    'bermain game': 'rating_suasana',
    'meeting_sosialisasi': 'rating_suasana',
    'keluarga': 'rating_suasana',
    'instagrammable': 'rating_suasana',
}
REVIEW_BASED_MIN_REVIEWS = 1

_ID_AFFIX_SUFFIXES = ('nya', 'lah', 'kah', 'pun', 'ku', 'mu', 'kan', 'an', 'i')
_ID_AFFIX_PREFIXES = ('ber', 'me', 'di', 'ter', 'se', 'pe', 'per', 'ke', 'nge', 'ng')
_TEXT_OVERLAP_STOP = frozenset({
    'dan', 'atau', 'yang', 'dengan', 'untuk', 'di', 'ke', 'dari', 'pada', 'ini', 'itu',
    'ada', 'tidak', 'juga', 'lebih', 'sangat', 'banget', 'saja', 'akan', 'sudah', 'bisa', 'agar',
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'to', 'of', 'in', 'on', 'for', 'and', 'or', 'with', 'as', 'by',
})
_PROMPT_EVIDENCE_CHAR_LIMIT = 600
_NEGATIVE_KEYWORD_FRAGMENTS = frozenset({
    'buruk', 'jelek', 'kotor', 'jorok', 'berisik', 'bising', 'mahal',
    'pelit', 'lambat', 'lemot', 'kecewa', 'zonk', 'parah', 'sampah',
    'ga enak', 'nggak enak', 'tidak enak', 'gak enak', 'bau', 'sumpek',
})
_REVIEW_WEAKNESS_FRAGMENTS = _NEGATIVE_KEYWORD_FRAGMENTS | frozenset({
    'kurang', 'ramai', 'penuh', 'sempit', 'panas', 'gelap', 'lama',
    'antri', 'antre', 'noise', 'ribut', 'crowded', 'overpriced',
    'wifi lelet', 'wifi lemot', 'colokan kurang', 'parkir susah',
    'susah', 'sulit', 'ribet', 'minim', 'kekurangan',
    'kurang disarankan', 'kurang cocok', 'kurang direkomendasikan',
    'tidak disarankan', 'tidak cocok', 'tidak direkomendasikan',
    'ga cocok', 'gak cocok', 'nggak cocok', 'enggak cocok',
    'tidak recommended', 'kurang recommended',
})
_UNSUITABILITY_PHRASES = (
    'kurang disarankan', 'kurang direkomendasikan', 'kurang recommended', 'kurang cocok',
    'tidak disarankan', 'tidak direkomendasikan', 'tidak recommended', 'tidak cocok',
    'ga cocok', 'gak cocok', 'nggak cocok', 'enggak cocok',
    'bukan tempat yang cocok', 'bukan untuk',
)
_MIN_QUOTE_CHARS = 6
_MEETING_OVERBROAD_TERMS = frozenset({
    'kumpul', 'ngumpul', 'berkumpul', 'grup', 'group', 'acara', 'komunitas',
    'nongkrong', 'nongki', 'hangout',
})
_MEETING_OVERBROAD_KEEP_TOKENS = frozenset({
    'kerja', 'kantor', 'rapat', 'meeting', 'bisnis', 'tim', 'klien', 'client',
    'diskusi', 'profesional',
})
_PREFERENCE_WEAKNESS_TOKEN_WINDOW = 6
_REVIEW_WEAKNESS_FRAGMENTS_SORTED = tuple(
    sorted(_REVIEW_WEAKNESS_FRAGMENTS, key=len, reverse=True),
)
_clause_verdicts_var: contextvars.ContextVar = contextvars.ContextVar(
    'cofind_clause_verdicts', default=None,
)
_GENERIC_SHORT_SUMMARY_RE = re.compile(
    r'^.+\s+(dinilai cocok|menjadi salah|sangat cocok|kurang cocok)\.?\s*$',
    re.I | re.S,
)
_GENERIC_PRAISE_MARKERS = (
    'kopi enak', 'kopinya enak', 'makanan enak', 'makanannya enak',
    'pelayanan ramah', 'pelayanannya ramah', 'recommended', 'worth it',
    'tempatnya nyaman', 'tempat nyaman', 'enak banget', 'recommended banget',
    'rasanya enak', 'menu enak',
)
_FREE_TEXT_GENERIC_STOP = frozenset({
    'coffee', 'shop', 'kafe', 'cafe', 'tempat', 'kedai',
})
_SENTIMENT_QUOTES_PER_CANDIDATE = 6

def _ordered_true_facility_keys(source_obj, preferred_order=None):
    if not isinstance(source_obj, dict):
        return []
    preferred_order = preferred_order or []
    keys = [k for k, v in source_obj.items() if v is True]
    if not keys:
        return []
    order_idx = {k: i for i, k in enumerate(preferred_order)}
    return sorted(keys, key=lambda k: (order_idx.get(k, len(preferred_order)), k))
def _format_facilities_tab_signals(shop_facilities):
    """
    Format subset facilities yang dipakai FacilitiesTab:
    - popular_for
    - highlights
    - atmosphere
    """
    facilities = (shop_facilities or {}).get('facilities') or {}
    popular_keys = _ordered_true_facility_keys(
        facilities.get('popular_for'),
        _FACILITY_POPULAR_FOR_ORDER,
    )
    highlight_keys = _ordered_true_facility_keys(
        facilities.get('highlights'),
        _FACILITY_HIGHLIGHT_ORDER,
    )
    atmosphere_items = [
        str(item).strip().replace('_', ' ')
        for item in (facilities.get('atmosphere') or [])
        if str(item).strip()
    ]

    popular_labels = [_FACILITY_POPULAR_FOR_LABELS.get(k, k.replace('_', ' ')) for k in popular_keys]
    highlight_labels = [_FACILITY_HIGHLIGHT_LABELS.get(k, k.replace('_', ' ')) for k in highlight_keys]

    parts = []
    if popular_labels:
        parts.append(f"Populer untuk: {', '.join(popular_labels)}.")
    if highlight_labels:
        parts.append(f"Keunggulan: {', '.join(highlight_labels)}.")
    if atmosphere_items:
        parts.append(f"Suasana: {', '.join(atmosphere_items)}.")

    return {
        'popular_for': popular_labels,
        'highlights': highlight_labels,
        'atmosphere': atmosphere_items,
        'text': " ".join(parts).strip(),
    }
def _normalize_whitespace(text):
    return re.sub(r'\s+', ' ', str(text or '')).strip()


def _truncate_evidence_text(text, limit=180):
    cleaned = _normalize_whitespace(text)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + '...'


def _build_empty_supporting_evidence():
    return {
        'facilities': [],
        'facilities_tab': {'popular_for': [], 'highlights': [], 'atmosphere': []},
        'facilities_tab_intent': {'popular_for': [], 'highlights': [], 'atmosphere': []},
        'facilities_intent_aligned': False,
        'facilities_evidence_summary': '',
        'metadata_gate': {},
        'matched_facility_pills': [],
        'matched_facility_labels': [],
        'metadata_support': [],
        'metadata_contradiction_quotes': [],
        'review_quotes': [],
        'positive_review_quotes': [],
        'negative_review_quotes': [],
        'search_keywords': [],
        'search_keyword_matches': [],
        'pill_stats': [],
        'category_ratings': {'makanan': None, 'layanan': None, 'suasana': None},
        'avg_user_rating': None,
        'review_count': 0,
        'is_low_confidence': False,
        'modal_display_quotes': [],
        'modal_caveat_quotes': [],
        'modal_quote_summary': '',
    }


def _extract_json_candidate(raw_text, expected='any'):
    """
    Ekstrak kandidat JSON dari output LLM (hapus markdown/fence + ambil blok utama).
    expected: 'array' | 'object' | 'any'
    """
    text = str(raw_text or '').strip()
    if not text:
        return ''
    # Hapus code fence pembungkus jika ada.
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()

    if expected in ('array', 'any'):
        m = re.search(r'\[[\s\S]*\]', text)
        if m:
            return m.group(0).strip()
    if expected in ('object', 'any'):
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            return m.group(0).strip()
    return text
def _parse_llm_json_with_repair(
    raw_text,
    *,
    expected='any',
    model=None,
    max_llm_passes=2,
    usage_stage='json_repair',
):
    """
    Parse JSON output LLM, lalu repair pass LLM jika parse gagal.
    expected: 'array' | 'object' | 'any'
    """
    def _validate_shape(obj):
        if expected == 'array' and not isinstance(obj, list):
            raise ValueError("expected array")
        if expected == 'object' and not isinstance(obj, dict):
            raise ValueError("expected object")
        return obj

    candidate = _extract_json_candidate(raw_text, expected=expected)
    if candidate:
        try:
            return _validate_shape(json.loads(candidate))
        except Exception:
            pass
        if repair_json is not None:
            try:
                fixed = repair_json(candidate, skip_json_loads=True)
                return _validate_shape(json.loads(str(fixed)))
            except Exception:
                pass

    if not llm_is_available():
        raise ValueError("LLM unavailable for JSON repair")

    shape_hint = "JSON array" if expected == 'array' else ("JSON object" if expected == 'object' else "valid JSON")
    repair_messages = [
        {
            'role': 'system',
            'content': (
                f'You are a precise JSON fixer. Output ONLY {shape_hint} valid, '
                'without markdown, code fences, or any explanation.'
            ),
        },
        {
            'role': 'user',
            'content': f'Fix this into {shape_hint}:\n{str(raw_text or "")[:3200]}',
        },
    ]
    repaired_text = str(raw_text or "")
    passes = max(1, min(int(max_llm_passes or 2), 2))
    for _ in range(passes):
        repaired = llm_chat_completions_create(
            model=model,
            messages=repair_messages[:-1] + [{'role': 'user', 'content': f'Fix this into {shape_hint}:\n{repaired_text[:3200]}'}],
            max_tokens=320,
            temperature=0.0,
            top_p=0.9,
            usage_stage=usage_stage,
        )
        repaired_candidate = _extract_json_candidate(repaired, expected=expected)
        try:
            return _validate_shape(json.loads(repaired_candidate))
        except Exception:
            if repair_json is not None:
                try:
                    fixed = repair_json(repaired_candidate, skip_json_loads=True)
                    return _validate_shape(json.loads(str(fixed)))
                except Exception:
                    pass
            repaired_text = repaired
    raise ValueError("JSON repair failed after max iterations")
def _llm_model_id():
    return (HF_MODEL or "meta-llama/Meta-Llama-3-8B").strip()
def _llm_chat_for_pipeline(*, messages, max_tokens, temperature, usage_stage=None, **kwargs):
    """Adapter chat completion untuk tahap keputusan LLM di llm_recommender."""
    route = get_llm_run_route()
    use_gemini = route is not None and route.mode == 'gemini'
    return llm_chat_completions_create(
        model=None if use_gemini else _llm_model_id(),
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        usage_stage=usage_stage or 'pipeline',
        prefer_provider='gemini' if use_gemini else None,
        response_format=kwargs.get('response_format'),
    )
def _compact_prompt_block(text, max_chars=0):
    """
    Sama seperti _compact_prompt_text tetapi struktur baris dipertahankan.
    Dipakai untuk blok data prompt (daftar kutipan, statistik) yang jadi sulit
    dibaca model kalau newline-nya ikut diratakan menjadi spasi.
    """
    lines = []
    for raw_line in str(text or '').splitlines():
        cleaned_line = re.sub(r'[ \t]+', ' ', raw_line).rstrip()
        if not cleaned_line.strip() and (not lines or not lines[-1].strip()):
            continue
        lines.append(cleaned_line)
    result = '\n'.join(lines).strip()
    if max_chars > 0 and len(result) > max_chars:
        result = result[:max_chars].rstrip() + '\n  ...(data dipotong)'
    return result
def _normalize_match_text(value):
    return str(value or '').strip().lower()
def _collect_intent_strings_for_facilities(pills, search_keywords):
    """Teks gabungan preferensi (pill + keyword review + search_keywords) untuk cocokkan ke label fasilitas."""
    parts = []
    for p in pills or []:
        parts.append(str(PILL_LABELS.get(p, p) or ''))
        mapping = PILL_MAPPING.get(p, {}) or {}
        for kw in mapping.get('review_keywords', []) or []:
            parts.append(str(kw))
    for kw in search_keywords or []:
        parts.append(str(kw))
    return ' '.join(x for x in parts if x).lower()
def _avg_or_none(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return round(sum(float(v) for v in vals) / len(vals), 2)
def _profile_from_shop_and_reviews(shop_data, reviews, facilities_index=None):
    """Bangun satu profil rekomendasi dari baris coffee_shops + list review lean."""
    place_id = shop_data.get('place_id')
    if not place_id:
        return None
    if facilities_index is None:
        facilities_index = {}
    facility_entry = facilities_index.get(place_id) or {}
    facilities_tab = _format_facilities_tab_signals(facility_entry)

    user_ratings = []
    makanan_ratings = []
    layanan_ratings = []
    suasana_ratings = []
    for r in reviews or []:
        if r.get('rating') is not None:
            user_ratings.append(float(r['rating']))
        if r.get('rating_makanan') is not None:
            makanan_ratings.append(float(r['rating_makanan']))
        if r.get('rating_layanan') is not None:
            layanan_ratings.append(float(r['rating_layanan']))
        if r.get('rating_suasana') is not None:
            suasana_ratings.append(float(r['rating_suasana']))

    return {
        'place_id': place_id,
        'name': shop_data.get('name') or '',
        'reviews': reviews or [],
        'review_count': len(reviews or []),
        'avg_user_rating': (round(sum(user_ratings) / len(user_ratings), 2) if user_ratings else None),
        'avg_category_ratings': {
            'makanan': _avg_or_none(makanan_ratings),
            'layanan': _avg_or_none(layanan_ratings),
            'suasana': _avg_or_none(suasana_ratings),
        },
        'facilities_tab': facilities_tab,
        'facilities_tab_text': facilities_tab.get('text') or '',
        'facilities_raw': facility_entry.get('facilities') or {},
        'google_rating': float(shop_data.get('rating') or 0),
        'google_total_reviews': int(shop_data.get('total_reviews') or 0),
        'opening_hours_display': str(shop_data.get('opening_hours_display') or '').strip(),
    }
def _build_profiles_for_recommendation(place_ids, facilities_index=None, excluded_place_ids=None):
    """
    Batch-load profil rekomendasi:
      1 query coffee_shops + 1 query reviews lean (tanpa foto/like).
    Return: (profiles, shops_without_reviews)

    `excluded_place_ids` opsional (hook generik). Pipeline rekomendasi tidak
    mengisi daftar ini dari vote not_helpful; toko tetap masuk korpus Fase 1.
    """
    excluded = set(excluded_place_ids or set())
    target_ids = [pid for pid in (place_ids or []) if pid and pid not in excluded]
    if not target_ids:
        return [], []

    if facilities_index is None:
        facilities_index = load_facilities_index()

    shops_by_id = {}
    conn = get_connection()
    try:
        cur = conn.cursor()
        placeholders = ','.join('?' * len(target_ids))
        rows = cur.execute(
            f"SELECT place_id, name, rating, total_reviews, opening_hours_display "
            f"FROM coffee_shops WHERE place_id IN ({placeholders})",
            target_ids,
        ).fetchall()
        for row in rows:
            shop = dict_from_row(cur, row)
            if shop and shop.get('place_id'):
                shops_by_id[shop['place_id']] = shop
    finally:
        conn.close()

    reviews_result = get_reviews_for_recommendation_batch(list(shops_by_id.keys()))
    reviews_by_place = reviews_result.get('by_place') or {}
    if not reviews_result.get('success'):
        LOG_RECOMMEND.warning(
            f"Batch reviews gagal: {reviews_result.get('error')}; "
            "fallback per-shop get_reviews_for_recommendation_batch")
        reviews_by_place = {}
        for pid in shops_by_id:
            one = get_reviews_for_recommendation_batch([pid])
            reviews_by_place[pid] = (one.get('by_place') or {}).get(pid) or []

    profiles = []
    shops_without_reviews = []
    for pid in target_ids:
        shop_data = shops_by_id.get(pid)
        if not shop_data:
            continue
        reviews = reviews_by_place.get(pid) or []
        profile = _profile_from_shop_and_reviews(shop_data, reviews, facilities_index=facilities_index)
        if not profile:
            continue
        if profile['review_count'] < REVIEW_BASED_MIN_REVIEWS:
            shops_without_reviews.append(pid)
            continue
        profiles.append(profile)

    if profiles:
        community_ids = [p.get('place_id') for p in profiles if p.get('place_id')]
        vote_by_place = get_vote_summaries_batch(community_ids, include_review_stars=False)
        pros_by_place = get_top_voted_pros_batch(community_ids, limit=3)
        for profile in profiles:
            pid = profile.get('place_id')
            vote = vote_by_place.get(pid) or {}
            profile['community_signals'] = {
                'vote': {
                    'total_votes': vote.get('total_votes') or 0,
                    'rating_counts': vote.get('rating_counts') or {},
                    'slider_averages': vote.get('slider_averages') or {},
                },
                'top_pros': pros_by_place.get(pid) or [],
            }
    return profiles, shops_without_reviews
def _load_all_place_ids():
    """Return list of all place_ids dari database (tabel coffee_shops)."""
    place_ids = []
    try:
        conn = get_connection()
        rows = conn.execute("SELECT place_id FROM coffee_shops").fetchall()
        conn.close()
        place_ids = [r[0] for r in rows if r[0]]
    except Exception as err:
        # Daftar kosong membuat pipeline berhenti tanpa kandidat, jadi kegagalan
        # di sini harus terlihat di log.
        LOG_RECOMMEND.error(f"Gagal memuat place_id dari database: {err}")
    return place_ids
def _has_semantic_family_signal(review_text):
    """
    Detect family-friendly intent from natural phrasing, not just exact keywords.
    Example: 'berkumpul bersama orang sayang' should count as family/family-friendly.
    """
    normalized = _normalize_match_text(review_text)
    if not normalized:
        return False, None

    direct_patterns = [
        'orang sayang',
        'orang tersayang',
        'family friendly',
        'ramah keluarga',
        'cocok keluarga',
        'bawa anak',
        'anak-anak',
        'quality time',
    ]
    for pattern in direct_patterns:
        if _matches_keyword_phrase(normalized, pattern):
            return True, pattern

    together_patterns = ['berkumpul', 'kumpul', 'kebersamaan', 'quality time', 'bersama']
    close_people_patterns = ['orang sayang', 'orang tersayang', 'keluarga', 'family', 'anak', 'pasangan']

    if any(_matches_keyword_phrase(normalized, a) for a in together_patterns) and any(
        _matches_keyword_phrase(normalized, b) for b in close_people_patterns
    ):
        return True, 'kebersamaan dengan orang terdekat'

    return False, None
def _normalize_keyword_phrase(value):
    """Normalisasi + slang map (bgt→banget, jgn→jangan, dll.) untuk matching."""
    return normalize_text_with_slang(value)
def _strip_match_token(token):
    return re.sub(r'^[^\w]+|[^\w]+$', '', str(token or '').lower(), flags=re.UNICODE)
def _token_matches_keyword_token(token, keyword):
    """True jika token adalah kata kunci utuh, plus imbuhan wajar — bukan potongan di tengah kata lain."""
    tok = _strip_match_token(token)
    kw = str(keyword or '').strip().lower()
    if not tok or not kw:
        return False
    if '-' in tok:
        return any(_token_matches_keyword_token(part, kw) for part in tok.split('-') if part)
    if tok == kw:
        return True
    if len(kw) <= 3:
        return False
    for suf in _ID_AFFIX_SUFFIXES:
        if tok == kw + suf:
            return True
    for pre in _ID_AFFIX_PREFIXES:
        if tok == pre + kw:
            return True
        for suf in _ID_AFFIX_SUFFIXES:
            if tok == pre + kw + suf:
                return True
    return False
def _find_keyword_token_spans(tokens, keyword_variant):
    """Span indeks token inklusif tempat frasa kunci cocok sebagai kata, bukan substring."""
    found = set()
    kw_tokens = [t for t in str(keyword_variant or '').split() if t]
    if not tokens or not kw_tokens:
        return found
    n = len(kw_tokens)
    for i in range(0, len(tokens) - n + 1):
        if all(_token_matches_keyword_token(tokens[i + j], kw_tokens[j]) for j in range(n)):
            found.add((i, i + n - 1))
    return found
def _matches_keyword_phrase(text, keyword):
    """
    Cocokkan keyword sebagai kata/frasa bermakna, bukan substring di dalam kata lain.
    Contoh: 'anak' cocok di 'bawa anak', tidak cocok di 'Pontianak'.
    Imbuhan wajar (anaknya, ngegame) tetap lolos lewat _token_matches_keyword_token.
    """
    normalized_text = _normalize_keyword_phrase(text)
    variant = _normalize_keyword_phrase(keyword)
    if not normalized_text or not variant:
        return False
    return bool(_find_keyword_token_spans(normalized_text.split(), variant))
def _split_tokens_with_spans(line):
    """Token whitespace + span karakter inklusif [start, end) di line."""
    if not line:
        return [], []
    tokens = []
    spans = []
    offset = 0
    for chunk in line.split(' '):
        if not chunk:
            continue
        idx = line.find(chunk, offset)
        if idx < 0:
            idx = line.index(chunk)
        tokens.append(chunk)
        spans.append((idx, idx + len(chunk)))
        offset = idx + len(chunk) + 1
    return tokens, spans
def _collect_preference_anchor_spans_for_line(tokens, spans, line, preference_keywords):
    """Span token tempat keyword preferensi muncul di baris yang sudah dinormalisasi."""
    found = set()
    if not line or not tokens or not preference_keywords:
        return found

    for kw in preference_keywords:
        variant = _normalize_keyword_phrase(kw)
        if variant:
            found.update(_find_keyword_token_spans(tokens, variant))
    return found
def _collect_weakness_token_spans(tokens, spans, line):
    """Span token inklusif tempat fragmen kelemahan muncul di line ter-normalisasi.

    Fragmen yang dinegasi ("tidak berisik", "ga mahal", "wifi nggak lemot")
    tidak dihitung sebagai kelemahan.
    """
    found = set()
    if not line or not tokens:
        return found
    for frag in _REVIEW_WEAKNESS_FRAGMENTS_SORTED:
        for span in _find_keyword_token_spans(tokens, frag):
            start = span[0]
            prev = tokens[start - 1] if start > 0 else ''
            if prev in _NEGATION_PREFIXES:
                continue
            found.add(span)
    return found
def _weakness_overlaps_anchor_window(weak_span, anchor_span, n_tokens, window):
    if n_tokens <= 0:
        return False
    a0, a1 = anchor_span
    w0, w1 = weak_span
    zone_lo = max(0, a0 - window)
    zone_hi = min(n_tokens - 1, a1 + window)
    return not (w1 < zone_lo or w0 > zone_hi)
def _line_has_weakness_near_anchors(tokens, spans, line, preference_keywords, window):
    """True jika ada fragmen kelemahan dalam ±window token dari blok keyword preferensi."""
    if not preference_keywords:
        return False
    anchors = _collect_preference_anchor_spans_for_line(tokens, spans, line, preference_keywords)
    weak = _collect_weakness_token_spans(tokens, spans, line)
    n = len(tokens)
    for anchor in anchors:
        for wsp in weak:
            if _weakness_overlaps_anchor_window(wsp, anchor, n, window):
                return True
    return False
def _review_has_weakness_near_preference_keywords(text, preference_keywords, window=None):
    """
    Kelemahan terhadap preferensi: fragmen lemah dalam jendela keyword pill.
    Implementasi utama ada di review_weakness (satu sumber untuk badge/metadata).
    """
    return _weakness_near_keywords(text, preference_keywords, window=window)
def _expand_pill_to_keywords(pill):
    """Gabungan keyword dari PILL_MAPPING + pill itu sendiri (lowercase)."""
    mapping = PILL_MAPPING.get(pill, {}) or {}
    out = [pill.lower()]
    out.extend([kw.lower() for kw in mapping.get('review_keywords', [])])
    return list(dict.fromkeys(out))


def _seed_search_keywords(pills):
    """Keyword retrieval awal dari daftar pill (smoke / tooling)."""
    expanded = []
    for pill in pills or []:
        expanded.extend(_expand_pill_to_keywords(pill))
    return _light_keyword_phrase_list(expanded)


def _light_keyword_phrase_list(keywords):
    """Normalisasi ringan untuk daftar frasa (tanpa banned_tokens ketat)."""
    cleaned = []
    seen = set()
    if isinstance(keywords, (list, tuple, set)):
        iterable = keywords
    else:
        iterable = re.split(r'[,;\n]+', str(keywords or ''))
    for k in iterable:
        n = _normalize_keyword_phrase(str(k or '').strip())
        if not n or len(n) < 2 or len(n) > 40:
            continue
        tokens = n.split()
        if len(tokens) > 4:
            continue
        if n in _TEXT_OVERLAP_STOP:
            continue
        if n in seen:
            continue
        seen.add(n)
        cleaned.append(n)
    return cleaned
def _is_overbroad_meeting_keyword(keyword):
    """True jika frasa terlalu umum untuk bukti meeting (mis. 'kumpul' saja)."""
    tokens = _normalize_keyword_phrase(keyword).split()
    if not tokens:
        return False
    if len(tokens) == 1:
        return tokens[0] in _MEETING_OVERBROAD_TERMS
    if tokens[0] not in _MEETING_OVERBROAD_TERMS:
        return False
    return not any(token in _MEETING_OVERBROAD_KEEP_TOKENS for token in tokens[1:])
def _filter_overbroad_meeting_keywords(keywords, pills):
    """Buang kata longgar meeting kecuali pill keluarga membutuhkannya."""
    pill_set = {str(p).strip().lower() for p in (pills or []) if str(p).strip()}
    cleaned = list(keywords or [])
    if 'meeting_sosialisasi' not in pill_set:
        return cleaned
    if pill_set & {'keluarga'}:
        return cleaned
    return [kw for kw in cleaned if not _is_overbroad_meeting_keyword(kw)]
def _review_has_weakness_signal(text):
    normalized = _normalize_keyword_phrase(text)
    if not normalized:
        return False
    return any(
        _phrase_unnegated(normalized, fragment)
        for fragment in _REVIEW_WEAKNESS_FRAGMENTS
    )
def _review_rating_value(review):
    try:
        return float((review or {}).get('rating') or 0)
    except (TypeError, ValueError):
        return 0.0
def _review_quote_detail_fields(review):
    """Metadata rating + foto per review untuk tampilan modal (tanpa blob foto)."""
    if not isinstance(review, dict):
        return {}
    photos = review.get('photos') or []
    has_photos = bool(photos) if isinstance(photos, list) else False
    return {
        'review_id': review.get('id'),
        'rating_makanan': review.get('rating_makanan'),
        'rating_layanan': review.get('rating_layanan'),
        'rating_suasana': review.get('rating_suasana'),
        'has_photos': has_photos,
    }
def _sort_quotes_for_modal_display(quotes):
    """Urut: rating keseluruhan tertinggi dulu, lalu kutipan paling lengkap."""
    def key(item):
        try:
            r = float(item.get('rating'))
        except (TypeError, ValueError):
            r = -1.0
        return (r, _quote_completeness_score(item))

    return sorted(quotes, key=key, reverse=True)
def _preference_keywords_for_evidence(pills, search_keywords=None):
    """Keyword preferensi (leksikon pill + search_keywords) untuk mendeteksi keluhan pada kutipan."""
    out = []
    for pill in pills or []:
        out.extend(_expand_pill_to_keywords(pill))
    out.extend(_light_keyword_phrase_list(search_keywords or []))
    return _filter_overbroad_meeting_keywords(list(dict.fromkeys(out)), pills)
def _set_clause_verdicts(verdicts):
    """Pasang verdict LLM untuk request ini; return token untuk reset."""
    return _clause_verdicts_var.set(dict(verdicts or {}))
def _reset_clause_verdicts(token):
    if token is not None:
        try:
            _clause_verdicts_var.reset(token)
        except ValueError:
            _clause_verdicts_var.set(None)
def _merge_caveat_quote_rows(*groups, limit=2):
    """Gabung kutipan caveat; kontradiksi metadata didahulukan."""
    seen = set()
    out = []
    for group in groups:
        for row in group or []:
            if not isinstance(row, dict):
                continue
            quote = str(row.get('quote') or '').strip()
            if len(quote) < _MIN_QUOTE_CHARS:
                continue
            marker = _quote_marker_key(quote)
            if not marker or marker in seen:
                continue
            seen.add(marker)
            item = dict(row)
            item['quote'] = quote
            item['sentiment'] = item.get('sentiment') or 'caveat'
            out.append(item)
            if len(out) >= limit:
                return out
    return out
def _facility_pill_review_sentiment(reviews, pill, *, score_detail=None):
    """
    Sentimen ulasan terhadap pill fasilitas — delegasi ke pill_aspect_sentiment.
    """
    extra = []
    detail = score_detail if isinstance(score_detail, dict) else {}
    stats = (detail.get('per_pill_stats') or {}).get(pill) or {}
    for row in stats.get('sample_quotes') or []:
        if isinstance(row, dict) and row.get('quote'):
            extra.append(str(row.get('quote')))
    return aggregate_reviews_sentiment(
        reviews,
        pill,
        PILL_MAPPING,
        extra_texts=extra,
    )
def _pill_eligible_for_facility_badge(
    pill,
    gate,
    score_detail,
    reviews,
    *,
    attribute_selected=None,
):
    if pill not in FACILITY_ATTRIBUTE_PILLS:
        return False
    gate = gate if isinstance(gate, dict) else {}
    score_detail = score_detail if isinstance(score_detail, dict) else {}
    selected = set(attribute_selected or [])
    if selected and pill not in selected:
        return False

    contradicted = set(
        gate.get('contradicted_pills')
        or score_detail.get('metadata_contradicted_pills')
        or []
    )
    if pill in contradicted:
        return False

    sentiment = _facility_pill_review_sentiment(reviews, pill, score_detail=score_detail)
    if sentiment == 'negative':
        return False

    metadata_matched = pill in (gate.get('matched_attribute_pills') or []) or pill in (
        score_detail.get('metadata_matched_attribute_pills') or []
    )
    claimed = pill in (gate.get('claimed_pills') or []) or pill in (
        score_detail.get('metadata_claimed_pills') or []
    )
    covered = pill in (score_detail.get('covered_pills') or [])

    if sentiment == 'positive':
        return metadata_matched or claimed or covered
    # neutral: hanya klaim profil/jam buka — bukan hit keyword tanpa sentimen positif
    return metadata_matched or claimed
def _matched_facility_from_gate(gate, score_detail=None, reviews=None):
    """
    Fasilitas tambahan (lapis 2) untuk badge di modal rekomendasi.

    Badge wajib selaras intent user dengan sentimen positif (ulasan mendukung
    atau belum ada mention), bukan keluhan atau kontradiksi metadata.
    """
    gate = gate if isinstance(gate, dict) else {}
    score_detail = score_detail if isinstance(score_detail, dict) else {}
    attribute_selected = [
        p for p in (score_detail.get('attribute_pills') or [])
        if p in FACILITY_ATTRIBUTE_PILLS
    ]

    candidates = []
    seen = set()
    for source in (
        gate.get('matched_attribute_pills') or score_detail.get('metadata_matched_attribute_pills') or [],
        gate.get('claimed_pills') or score_detail.get('metadata_claimed_pills') or [],
        score_detail.get('covered_pills') or [],
    ):
        for pill in source:
            pill = str(pill)
            if pill in seen:
                continue
            seen.add(pill)
            candidates.append(pill)

    pills = [
        p for p in candidates
        if _pill_eligible_for_facility_badge(
            p,
            gate,
            score_detail,
            reviews,
            attribute_selected=attribute_selected,
        )
    ]
    labels = [PILL_LABELS.get(p, p) for p in pills]
    return pills, labels
def _shop_reviews_for_facility_badge(shop):
    if not isinstance(shop, dict):
        return []
    profile = shop.get('profile') if isinstance(shop.get('profile'), dict) else shop
    return list(profile.get('reviews') or [])
def _safe_float(value):
    try:
        if value is None or value == '':
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
def _overall_experience_score_from_signals(signals):
    """
    Skor 0..1 dari Overall Experience pengunjung:
    rata-rata slider pelayanan, kebersihan, kenyamanan, harga (skala 1..5 → 0..1).
    None jika belum ada data slider sama sekali.
    """
    vote = ((signals or {}).get('vote') or {})
    sliders = vote.get('slider_averages') or {}
    slider_vals = []
    for field in ('pelayanan', 'kebersihan', 'kenyamanan', 'harga'):
        val = sliders.get(field)
        if val is None:
            continue
        try:
            slider_vals.append(max(0.0, min(1.0, (float(val) - 1.0) / 4.0)))
        except (TypeError, ValueError):
            continue
    if not slider_vals:
        return None
    return round(sum(slider_vals) / len(slider_vals), 4)
def _coffee_shop_rating_score(profile):
    """
    Skor 0..1 dari rating coffee shop (kolom coffee_shops.rating / Google).
    Fallback ke rata-rata rating review Cofind bila rating toko kosong.
    Normalisasi: 3.0 → 0, 5.0 → 1 (di bawah 3 dianggap 0).
    """
    raw = None
    google = profile.get('google_rating')
    try:
        if google is not None and float(google) > 0:
            raw = float(google)
    except (TypeError, ValueError):
        raw = None
    if raw is None:
        avg_user = profile.get('avg_user_rating')
        try:
            if avg_user is not None:
                raw = float(avg_user)
        except (TypeError, ValueError):
            raw = None
    if raw is None:
        return None
    return max(0.0, min(1.0, (raw - 3.0) / 2.0))
def _quality_score_for_profile(profile):
    """Gabungan Overall Experience dan rating toko (0..1). None jika keduanya kosong."""
    experience = _overall_experience_score_from_signals((profile or {}).get('community_signals'))
    rating = _coffee_shop_rating_score(profile)
    if experience is None and rating is None:
        return None
    if experience is None:
        return rating
    if rating is None:
        return experience
    return round(0.5 * experience + 0.5 * rating, 4)
def _community_score_from_signals(signals, pills):
    """Skor 0..1 dari agregat vote/overall/best-for/pros. None jika tidak ada data.
    Dipakai untuk konteks prompt/evidence, bukan bobot hybrid ranking utama.
    """
    data = signals or {}
    vote = data.get('vote') or {}
    rating_counts = vote.get('rating_counts') or {}
    parts = []
    weights = []

    weighted = 0.0
    total_rating = 0
    for label, weight in RATING_VOTE_WEIGHTS.items():
        count = int(rating_counts.get(label) or 0)
        weighted += weight * count
        total_rating += count
    if total_rating > 0:
        parts.append(weighted / total_rating)
        weights.append(0.40)

    experience = _overall_experience_score_from_signals(signals)
    if experience is not None:
        parts.append(experience)
        weights.append(0.25)

    pros = data.get('top_pros') or []
    if pros:
        nets = [max(0, int(item.get('net') or 0)) for item in pros]
        avg_net = sum(nets) / max(1, len(nets))
        parts.append(min(1.0, avg_net / 8.0))
        weights.append(0.35)

    if not parts:
        return None
    return round(sum(score * weight for score, weight in zip(parts, weights)) / sum(weights), 4)
def _community_prompt_lines(signals, pills=None, indent='  - '):
    """Baris fakta komunitas yang ringkas untuk prompt, tanpa mengubah gaya output."""
    data = signals or {}
    vote = data.get('vote') or {}
    lines = []

    rating_counts = vote.get('rating_counts') or {}
    total_rating = sum(int(rating_counts.get(k) or 0) for k in RATING_VOTE_WEIGHTS)
    if total_rating > 0:
        bits = []
        for key, label in (('love', 'sangat suka'), ('like', 'suka'), ('ok', 'biasa'), ('dislike', 'kurang suka'), ('hate', 'tidak suka')):
            count = int(rating_counts.get(key) or 0)
            if count:
                bits.append(f'{label} {count}')
        if bits:
            lines.append(f'{indent}Penilaian pengunjung: {", ".join(bits[:4])} (dari {total_rating} penilaian)')

    slider_bits = []
    sliders = vote.get('slider_averages') or {}
    for field, label in (('pelayanan', 'pelayanan'), ('kebersihan', 'kebersihan'), ('kenyamanan', 'kenyamanan'), ('harga', 'harga')):
        val = sliders.get(field)
        if val is not None:
            slider_bits.append(f'{label} {float(val):.1f}/5')
    if slider_bits:
        lines.append(f'{indent}Pengalaman pengunjung: {", ".join(slider_bits)}')

    pros = data.get('top_pros') or []
    pro_texts = [str(item.get('text') or '').strip() for item in pros if str(item.get('text') or '').strip()]
    if pro_texts:
        lines.append(f'{indent}Keunggulan yang disetujui pengunjung: {"; ".join(pro_texts[:3])}')
    return lines
def _shop_profile_lines_for_prompt(profile, evidence, pills=None):
    """Konteks profil toko dari database (rating pengguna, rating Google, rating kategori, sinyal komunitas)."""
    prof = profile or {}
    ev = evidence or {}
    lines = []

    review_count = _safe_float(ev.get('review_count')) or _safe_float(prof.get('review_count')) or 0
    avg_user = ev.get('avg_user_rating')
    if avg_user is None:
        avg_user = prof.get('avg_user_rating')
    if avg_user is not None:
        lines.append(
            f'  - Rating pengguna Cofind: {float(avg_user):.1f}/5 dari {int(review_count)} ulasan'
        )
    else:
        lines.append(f'  - Jumlah ulasan pengguna Cofind: {int(review_count)}')

    google_rating = _safe_float(prof.get('google_rating') or ev.get('google_rating'))
    google_total = _safe_float(
        prof.get('google_total_reviews') or ev.get('google_total_reviews')
    ) or 0
    if google_rating:
        lines.append(
            f'  - Rating Google: {google_rating:.1f}/5 dari {int(google_total)} ulasan'
        )

    category_ratings = ev.get('category_ratings') or prof.get('avg_category_ratings') or {}
    category_bits = [
        f'{label} {float(category_ratings[key]):.1f}/5'
        for key, label in (('suasana', 'suasana'), ('layanan', 'layanan'), ('makanan', 'makanan'))
        if category_ratings.get(key) is not None
    ]
    if category_bits:
        lines.append('  - Rating kategori dari pengguna: ' + ', '.join(category_bits))

    community = ev.get('community_signals') or prof.get('community_signals') or {}
    lines.extend(_community_prompt_lines(community, pills=pills, indent='  - '))
    return lines
def _pick_sentiment_review_quotes(reviews, pills=None, search_keywords=None, *, positive_limit=3, negative_limit=2):
    """
    Pilih kutipan positif dan catatan kurang positif dari review asli.
    Positive selalu diprioritaskan; negative hanya dipakai sebagai catatan jujur bila ada.
    Sinyal kelemahan: jika ada keyword preferensi (pill + review_keywords + search_keywords),
    hanya fragmen negatif dalam jendela ±_PREFERENCE_WEAKNESS_TOKEN_WINDOW token dari
    blok frasa keyword; tanpa keyword preferensi, fallback ke cek global di teks.
    """
    if not reviews:
        return [], []

    preference_keywords = []
    for pill in pills or []:
        preference_keywords.extend(_expand_pill_to_keywords(pill))
    preference_keywords.extend(_light_keyword_phrase_list(search_keywords or []))
    preference_keywords = list(dict.fromkeys(preference_keywords))

    positive = []
    negative = []
    seen = set()
    for review in reviews:
        if not isinstance(review, dict):
            continue
        text = _normalize_whitespace(review.get('text') or '')
        if len(text) < 15:
            continue
        key = text.lower()[:160]
        if key in seen:
            continue
        seen.add(key)

        rating = _review_rating_value(review)
        has_weakness = _quote_is_caveat(text, preference_keywords)
        matched_terms = [kw for kw in preference_keywords if _matches_keyword_phrase(text, kw)][:6]
        quote = {
            'quote': _truncate_evidence_text(text, _PROMPT_EVIDENCE_CHAR_LIMIT),
            'rating': review.get('rating'),
            'username': review.get('username') or review.get('full_name'),
            'matched_terms': matched_terms,
            **_review_quote_detail_fields(review),
        }
        relevance_bonus = 2.0 if matched_terms else 0.0
        length_bonus = min(1.0, len(text) / 300.0)

        if rating >= 4 and not has_weakness:
            quote['score'] = relevance_bonus + rating + length_bonus
            positive.append(quote)
        elif rating <= 3 or has_weakness:
            quote['score'] = relevance_bonus + (5 - rating if rating else 1.0) + length_bonus
            negative.append(quote)
        elif rating >= 4:
            quote['score'] = relevance_bonus + rating + length_bonus - 0.5
            positive.append(quote)

    positive.sort(key=lambda item: item.get('score', 0), reverse=True)
    negative.sort(key=lambda item: item.get('score', 0), reverse=True)

    def _strip_score(items):
        cleaned = []
        for item in items:
            next_item = dict(item)
            next_item.pop('score', None)
            cleaned.append(next_item)
        return cleaned

    return _strip_score(positive[:positive_limit]), _strip_score(negative[:negative_limit])
def _pick_keyword_matched_reviews(reviews, search_keywords, limit=3):
    """Pilih review paling kuat berdasarkan search_keywords."""
    keywords = _light_keyword_phrase_list(search_keywords or [])
    if not reviews or not keywords:
        return []

    scored_reviews = []
    seen_quotes = set()
    for review in reviews:
        text = (review.get('text') or '').strip() if isinstance(review, dict) else str(review or '').strip()
        if len(text) < 15:
            continue
        matched_terms = [kw for kw in keywords if _matches_keyword_phrase(text, kw)]
        if not matched_terms:
            continue
        quote_key = _normalize_whitespace(text).lower()
        if quote_key in seen_quotes:
            continue
        seen_quotes.add(quote_key)
        try:
            rating_value = float((review or {}).get('rating') or 0) if isinstance(review, dict) else 0.0
        except (TypeError, ValueError):
            rating_value = 0.0
        row = {
            'quote': _truncate_evidence_text(text, _PROMPT_EVIDENCE_CHAR_LIMIT),
            'rating': (review or {}).get('rating') if isinstance(review, dict) else None,
            'username': (review or {}).get('username') or (review or {}).get('full_name') if isinstance(review, dict) else None,
            'matched_terms': matched_terms[:6],
            'score': len(matched_terms) * 3.0 + min(1.5, len(text) / 240.0) + (max(0.0, rating_value) / 5.0),
        }
        if isinstance(review, dict):
            row.update(_review_quote_detail_fields(review))
        scored_reviews.append(row)

    scored_reviews.sort(key=lambda item: -item['score'])
    return scored_reviews[:limit]
def _semantic_reference_terms(pills, search_keywords=None, limit=24):
    """
    Frasa acuan untuk gerbang makna: label pill + keyword pill + search_keywords.
    Underscore diubah jadi spasi supaya frasa acuan tetap kalimat wajar saat di-encode.
    """
    terms = []
    seen = set()

    def push(value):
        # Underscore dan garis miring diubah jadi spasi ("Kerja/WFC",
        # "Area outdoor/smoking") supaya frasa acuan tetap kalimat wajar saat di-encode.
        text = re.sub(r'[_/]+', ' ', str(value or '')).strip().lower()
        text = re.sub(r'\s+', ' ', text)
        if len(text) < 3 or text in seen:
            return
        seen.add(text)
        terms.append(text)

    for pill in pills or []:
        push(PILL_LABELS.get(pill, pill))
        for keyword in (PILL_MAPPING.get(pill, {}) or {}).get('review_keywords', [])[:8]:
            push(keyword)
    for keyword in _light_keyword_phrase_list(search_keywords or [])[:12]:
        push(keyword)
    return terms[:limit]
def _semantic_term_owner_pills(pills):
    """
    Peta frasa acuan -> pill pemiliknya, memakai normalisasi yang sama seperti
    _semantic_reference_terms. Dipakai agar kecocokan makna bisa dihitung sebagai
    cakupan pill tertentu, bukan sekadar "ada bukti".
    """
    owners = {}

    def norm(value):
        text = re.sub(r'[_/]+', ' ', str(value or '')).strip().lower()
        return re.sub(r'\s+', ' ', text)

    for pill in pills or []:
        # Sengaja memakai leksikon PENUH, bukan 8 teratas seperti
        # _semantic_reference_terms: frasa acuan juga bisa datang dari
        # search_keywords, dan semuanya harus bisa dilacak balik ke pill-nya.
        for value in [PILL_LABELS.get(pill, pill)] + list(_expand_pill_to_keywords(pill)):
            # Daftarkan bentuk asli DAN bentuk ternormalisasi slang, karena
            # search_keywords sudah lewat normalisasi (mis. "sholat" -> "salat").
            for key in {norm(value), norm(_normalize_keyword_phrase(value))}:
                if len(key) >= 3:
                    owners.setdefault(key, pill)
    return owners
def _pick_semantic_matched_reviews(reviews, reference_terms, limit=3):
    """
    Jaring kedua setelah pencocokan kata: review yang maknanya dekat dengan
    frasa acuan pill walau tidak memuat katanya (mis. "koneksinya ngebut").

    Return (rows, telemetry). Rows berformat sama seperti _pick_keyword_matched_reviews
    supaya bisa langsung dipakai sebagai evidence.
    """
    if not reviews or not reference_terms or not semantic_gate_enabled():
        return [], {'skipped': 'disabled_or_empty'}

    matches, telemetry = semantic_match_reviews(reviews, reference_terms)
    rows = []
    for idx, info in matches.items():
        try:
            review = reviews[idx]
        except (IndexError, TypeError):
            continue
        text = _normalize_whitespace((review.get('text') or '') if isinstance(review, dict) else str(review or ''))
        if len(text) < 15:
            continue
        row = {
            'quote': _truncate_evidence_text(text, _PROMPT_EVIDENCE_CHAR_LIMIT),
            'rating': review.get('rating') if isinstance(review, dict) else None,
            'username': (review.get('username') or review.get('full_name')) if isinstance(review, dict) else None,
            # Frasa acuan yang paling dekat maknanya dipakai sebagai "alasan" kutipan,
            # jadi UI tetap menampilkan konteks yang dicari user.
            'matched_terms': [info.get('term')] if info.get('term') else [],
            'match_source': 'semantic',
            'semantic_score': info.get('score'),
            'semantic_clause': info.get('clause'),
            'score': float(info.get('score') or 0.0) * 3.0,
        }
        if isinstance(review, dict):
            row.update(_review_quote_detail_fields(review))
        rows.append(row)

    rows.sort(key=lambda item: -item.get('score', 0.0))
    return rows[:limit], telemetry
def _review_rating_category_scores(reviews, pills):
    """
    Sinyal kategori rating (makanan/layanan/suasana) per pill.
    Return: (avg_score_0to1, per_pill_detail).
    Hanya pill yang punya mapping kategori yang dihitung; kalau tidak ada data
    kategori sama sekali, return (0.0, {}).
    """
    per_pill = {}
    contributing = []
    for pill in pills:
        field = PILL_TO_REVIEW_CATEGORY.get(pill)
        if not field:
            continue
        vals = [r.get(field) for r in reviews if r.get(field) is not None]
        if not vals:
            continue
        avg = sum(float(v) for v in vals) / len(vals)
        norm = max(0.0, min(1.0, (avg - 3.0) / 2.0))  # map 3.0..5.0 -> 0..1
        per_pill[pill] = {
            'field': field,
            'avg': round(avg, 2),
            'sample_size': len(vals),
            'score': round(norm, 4),
        }
        contributing.append(norm)
    if not contributing:
        return 0.0, per_pill
    return sum(contributing) / len(contributing), per_pill
def _score_shop_by_user_reviews(
    profile,
    pills,
    search_keywords=None,
    bm25_norm=None,
    bm25_raw=None,
):
    """
    Scoring hybrid rekomendasi:
        70% BM25 relevansi query vs korpus review toko
        20% Overall Experience (pelayanan, kebersihan, kenyamanan, harga)
        10% rating coffee shop (coffee_shops.rating; fallback rata-rata review Cofind)

    Jika Overall Experience atau rating toko belum ada, bobot yang tersedia
    dinormalisasi ulang agar total tetap 1.0 (toko tanpa vote tidak dihukum 0).

    Keyword match per-pill tetap dihitung untuk evidence/UI (sample quotes),
    tetapi bobot utama ranking memakai skor BM25 yang dinormalisasi (0..1).
    """
    reviews = profile.get('reviews') or []
    review_count = len(reviews)
    search_keywords = _filter_overbroad_meeting_keywords(
        _light_keyword_phrase_list(search_keywords or []),
        pills,
    )
    if review_count == 0 or not pills:
        return {
            'total_score': 0.0,
            'keyword_score': 0.0,
            'bm25_score': 0.0,
            'bm25_raw': 0.0,
            'expanded_keyword_score': 0.0,
            'semantic_score': 0.0,
            'semantic_hits': 0,
            'semantic_matches': [],
            'semantic_telemetry': {},
            'covered_pills': [],
            'uncovered_pills': list(pills or []),
            'activity_pills': [p for p in (pills or []) if p not in FACILITY_ATTRIBUTE_PILLS],
            'attribute_pills': [p for p in (pills or []) if p in FACILITY_ATTRIBUTE_PILLS],
            'activity_coverage': 0.0,
            'attribute_coverage': 0.0,
            'coverage_ratio': 0.0,
            'coverage_multiplier': 1.0,
            'category_score': 0.0,
            'rating_score': 0.0,
            'overall_experience_score': None,
            'per_pill_stats': {},
            'expanded_keyword_matches': [],
            'search_keywords': search_keywords,
            'category_detail': {},
            'review_count': review_count,
            'avg_user_rating': profile.get('avg_user_rating'),
            'has_quote_evidence': False,
            'community_score': None,
            'score_weights': {'bm25': 0.70, 'overall_experience': 0.20, 'shop_rating': 0.10},
        }

    avg_user_rating = profile.get('avg_user_rating')
    rating_score = _coffee_shop_rating_score(profile)
    overall_experience_score = _overall_experience_score_from_signals(
        profile.get('community_signals'),
    )

    per_pill_stats = {}
    keyword_scores = []
    # Index review yang sudah cocok secara leksikal. Dipakai gerbang makna agar
    # hanya review yang GAGAL pencocokan kata yang perlu di-encode.
    lexical_matched_ids = set()

    for pill in pills:
        keywords = _expand_pill_to_keywords(pill)
        keyword_review_hits = 0
        sample_quotes = []

        for review_idx, review in enumerate(reviews):
            text = (review.get('text') or '').strip()
            matched_terms = []

            if text:
                matched_terms = [kw for kw in keywords if _matches_keyword_phrase(text, kw)]
                if pill == 'keluarga' and not matched_terms:
                    has_family_signal, _ = _has_semantic_family_signal(text)
                    if has_family_signal:
                        matched_terms = ['kebersamaan keluarga']
                if matched_terms:
                    keyword_review_hits += 1
                    lexical_matched_ids.add(review_idx)

            if matched_terms:
                if text and len(text) >= 15 and len(sample_quotes) < 3:
                    sample_quotes.append({
                        'quote': _truncate_evidence_text(text, _PROMPT_EVIDENCE_CHAR_LIMIT),
                        'rating': review.get('rating'),
                        'username': review.get('username') or review.get('full_name'),
                        'matched_terms': matched_terms,
                        **_review_quote_detail_fields(review),
                    })

        kw_norm = min(1.0, keyword_review_hits / max(1, min(review_count, 5)))

        per_pill_stats[pill] = {
            'pill': pill,
            'pill_label': PILL_LABELS.get(pill, pill),
            'keyword_review_hits': keyword_review_hits,
            'review_count': review_count,
            'keyword_score': round(kw_norm, 4),
            'sample_quotes': sample_quotes,
        }
        keyword_scores.append(kw_norm)

    keyword_score_avg = sum(keyword_scores) / len(keyword_scores) if keyword_scores else 0.0
    # Tetap dihitung untuk evidence/UI; tidak masuk bobot hybrid ranking.
    category_score_avg, category_detail = _review_rating_category_scores(reviews, pills)

    expanded_keyword_matches = _pick_keyword_matched_reviews(reviews, search_keywords, limit=3)

    expanded_keyword_hits = 0
    if search_keywords:
        for review_idx, review in enumerate(reviews):
            text = (review.get('text') or '').strip()
            if text and any(_matches_keyword_phrase(text, kw) for kw in search_keywords):
                expanded_keyword_hits += 1
                lexical_matched_ids.add(review_idx)
        expanded_keyword_score = min(1.0, expanded_keyword_hits / max(1, min(review_count, 5)))
    else:
        expanded_keyword_score = 0.0

    # Gerbang makna: hanya review yang GAGAL pencocokan kata di atas yang di-encode,
    # sehingga biaya embedding kecil dan tidak menduplikasi kerja keyword match.
    semantic_matches = []
    semantic_telemetry = {}
    semantic_hits = 0
    if semantic_gate_enabled():
        unmatched_reviews = [
            review for idx, review in enumerate(reviews)
            if idx not in lexical_matched_ids and (review.get('text') or '').strip()
        ]
        if unmatched_reviews:
            semantic_matches, semantic_telemetry = _pick_semantic_matched_reviews(
                unmatched_reviews,
                _semantic_reference_terms(pills, search_keywords),
                limit=3,
            )
            semantic_hits = int((semantic_telemetry or {}).get('matched_reviews') or 0)
    # Cakupan (berapa banyak review yang cocok maknanya) dikalikan tingkat keyakinan
    # (rata-rata cosine similarity), jadi satu kecocokan tipis tidak menaikkan skor toko
    # sekuat beberapa kecocokan yang meyakinkan.
    semantic_coverage = min(1.0, semantic_hits / max(1, min(review_count, 5)))
    semantic_confidence = float((semantic_telemetry or {}).get('mean_score') or 0.0)
    semantic_score = semantic_coverage * semantic_confidence

    # BM25 sebagai sinyal utama relevansi teks (fallback ke keyword hit jika BM25 belum dihitung)
    try:
        bm25_norm_val = float(bm25_norm) if bm25_norm is not None else None
    except (TypeError, ValueError):
        bm25_norm_val = None
    try:
        bm25_raw_val = float(bm25_raw) if bm25_raw is not None else 0.0
    except (TypeError, ValueError):
        bm25_raw_val = 0.0

    if bm25_norm_val is None:
        # Fallback lokal (tanpa indeks korpus): rata keyword pill + search_keywords
        text_relevance = keyword_score_avg
        if search_keywords:
            text_relevance = (keyword_score_avg + expanded_keyword_score) / 2.0
        bm25_norm_val = text_relevance
        bm25_raw_val = text_relevance
    else:
        bm25_norm_val = max(0.0, min(1.0, bm25_norm_val))

    # Relevansi teks = maksimum antara sinyal leksikal (BM25) dan sinyal makna.
    # Sinyal makna dibatasi score_cap agar bukti kata eksplisit tetap lebih kuat
    # daripada bukti yang hanya "mirip maknanya".
    semantic_contribution = semantic_score * semantic_score_cap()
    if semantic_contribution > bm25_norm_val:
        bm25_norm_val = semantic_contribution

    # Hybrid: 70% BM25 + 20% Overall Experience + 10% rating coffee shop.
    # Komponen yang None tidak dihukum 0; bobot dinormalisasi ke bagian yang ada.
    W_BM25, W_EXPERIENCE, W_RATING = 0.70, 0.20, 0.10
    weighted_sum = bm25_norm_val * W_BM25
    weight_total = W_BM25
    if overall_experience_score is not None:
        weighted_sum += overall_experience_score * W_EXPERIENCE
        weight_total += W_EXPERIENCE
    if rating_score is not None:
        weighted_sum += rating_score * W_RATING
        weight_total += W_RATING
    total = weighted_sum / weight_total if weight_total > 0 else 0.0

    community_score = _community_score_from_signals(profile.get('community_signals'), pills)

    # Wajib ada bukti kutipan PENDUKUNG (keyword match TANPA keluhan pada aspek
    # preferensi). Kutipan yang hanya mengeluh soal konteks yang sama tidak cukup
    # untuk merekomendasikan toko.
    pref_kws = _preference_keywords_for_evidence(pills, search_keywords)

    def _is_supporting_quote(row):
        text = str((row or {}).get('quote') or '')
        return len(text.strip()) >= 10 and not _quote_is_caveat(text, pref_kws)

    # Cakupan per pill: pill dianggap terpenuhi bila ada kutipan PENDUKUNG dari
    # pencocokan kata, atau kecocokan makna yang frasa acuannya milik pill itu.
    semantic_owners = _semantic_term_owner_pills(pills)
    covered_pills = set()
    for pill in pills:
        quotes = (per_pill_stats.get(pill) or {}).get('sample_quotes') or []
        if any(_is_supporting_quote(sq) for sq in quotes):
            covered_pills.add(pill)
    semantic_min = coverage_semantic_min()
    for match in semantic_matches:
        if not _is_supporting_quote(match):
            continue
        try:
            match_confidence = float(match.get('semantic_score') or 0.0)
        except (TypeError, ValueError):
            match_confidence = 0.0
        if match_confidence < semantic_min:
            continue
        for term in match.get('matched_terms') or []:
            owner = semantic_owners.get(str(term or '').strip().lower())
            if owner:
                covered_pills.add(owner)

    activity_pills = [p for p in pills if p not in FACILITY_ATTRIBUTE_PILLS]
    attribute_pills = [p for p in pills if p in FACILITY_ATTRIBUTE_PILLS]

    def _layer_ratio(layer):
        if not layer:
            return 1.0
        return sum(1 for p in layer if p in covered_pills) / len(layer)

    activity_coverage = _layer_ratio(activity_pills)
    attribute_coverage = _layer_ratio(attribute_pills)
    # Aktivitas menentukan, fasilitas menyempurnakan. Aktivitas tetap jadi
    # gerbang (tanpa buktinya cakupan nol berapa pun fasilitas yang terbukti),
    # tapi begitu terbukti toko langsung dapat `share` dan fasilitas mengisi
    # sisanya. Perkalian polos dulu menghukum "aktivitas ✓ fasilitas ✗" sama
    # berat dengan "aktivitas ✗ fasilitas ✓", padahal niat utama user ada di
    # lapis aktivitas.
    share = activity_coverage_share()
    coverage_ratio = activity_coverage * (share + (1.0 - share) * attribute_coverage)
    bonus = coverage_bonus()
    # Skor tetap di rentang 0..1: cakupan penuh tidak mengubah skor, cakupan
    # rendah menekan skor sebanyak `bonus`.
    coverage_multiplier = 1.0 - bonus + bonus * coverage_ratio
    total *= coverage_multiplier

    has_quote_evidence = (
        any(
            _is_supporting_quote(sq)
            for p in pills
            for sq in ((per_pill_stats.get(p) or {}).get('sample_quotes') or [])
        )
        or any(_is_supporting_quote(m) for m in expanded_keyword_matches)
        or any(_is_supporting_quote(m) for m in semantic_matches)
    )
    if not has_quote_evidence:
        total = 0.0

    return {
        'total_score': round(total, 4),
        'keyword_score': round(keyword_score_avg, 4),
        'bm25_score': round(bm25_norm_val, 4),
        'bm25_raw': round(bm25_raw_val, 4),
        'expanded_keyword_score': round(expanded_keyword_score, 4),
        'covered_pills': sorted(covered_pills),
        'uncovered_pills': [p for p in pills if p not in covered_pills],
        'activity_pills': activity_pills,
        'attribute_pills': attribute_pills,
        'activity_coverage': round(activity_coverage, 4),
        'attribute_coverage': round(attribute_coverage, 4),
        'coverage_ratio': round(coverage_ratio, 4),
        'coverage_multiplier': round(coverage_multiplier, 4),
        'activity_coverage_share': round(share, 4),
        'semantic_score': round(semantic_score, 4),
        'semantic_coverage': round(semantic_coverage, 4),
        'semantic_confidence': round(semantic_confidence, 4),
        'semantic_hits': semantic_hits,
        'semantic_matches': semantic_matches,
        'semantic_telemetry': semantic_telemetry,
        'category_score': round(category_score_avg, 4),
        'rating_score': round(rating_score, 4) if rating_score is not None else None,
        'overall_experience_score': overall_experience_score,
        'per_pill_stats': per_pill_stats,
        'expanded_keyword_matches': expanded_keyword_matches,
        'search_keywords': search_keywords,
        'category_detail': category_detail,
        'review_count': review_count,
        'avg_user_rating': avg_user_rating,
        'has_quote_evidence': has_quote_evidence,
        'community_score': community_score,
        'score_weights': {
            'bm25': W_BM25,
            'overall_experience': W_EXPERIENCE,
            'shop_rating': W_RATING,
        },
    }
def _build_review_based_evidence(profile, score_detail, pills, search_keywords=None):
    """
    Bangun supporting_evidence hanya dari review user.
    Key utama: review_quotes, pill_stats, category_ratings,
    avg_user_rating, review_count.
    """
    per_pill_stats = (score_detail or {}).get('per_pill_stats') or {}
    category_detail = (score_detail or {}).get('category_detail') or {}
    expanded_keyword_matches = (score_detail or {}).get('expanded_keyword_matches') or []
    search_keywords = _light_keyword_phrase_list(
        search_keywords or (score_detail or {}).get('search_keywords') or [],
    )

    pill_stats_out = []
    review_quotes_out = []
    seen_quote_keys = set()

    for pill in pills:
        stats = per_pill_stats.get(pill)
        if not stats:
            continue
        pill_label = stats['pill_label']
        keyword_hits = stats['keyword_review_hits']
        total_reviews = stats['review_count']

        pill_stats_out.append({
            'pill': pill,
            'pill_label': pill_label,
            'keyword_review_hits': keyword_hits,
            'review_count': total_reviews,
            'keyword_ratio': round(keyword_hits / total_reviews, 3) if total_reviews else 0,
            'category_avg': (category_detail.get(pill) or {}).get('avg'),
            'category_field': (category_detail.get(pill) or {}).get('field'),
            'sample_quote': (stats.get('sample_quotes') or [{}])[0].get('quote') if stats.get('sample_quotes') else None,
        })

        for sq in stats.get('sample_quotes') or []:
            quote_text = sq.get('quote')
            if not quote_text:
                continue
            key = _normalize_whitespace(quote_text).lower()[:120]
            if key in seen_quote_keys:
                continue
            seen_quote_keys.add(key)
            if sq.get('matched_terms'):
                reason = ", ".join(str(t).strip() for t in sq['matched_terms'][:3] if str(t).strip())
            else:
                reason = f"terkait {pill_label.lower()}"
            review_quotes_out.append({
                'pill': pill,
                'pill_label': pill_label,
                'quote': quote_text,
                'reason': reason,
                'rating': sq.get('rating'),
                'username': sq.get('username'),
                **_quote_ui_extras(sq),
            })

    search_keyword_matches_out = []
    for match in expanded_keyword_matches[:3]:
        quote_text = match.get('quote')
        matched_terms = [str(t).strip() for t in (match.get('matched_terms') or []) if str(t).strip()]
        if not quote_text or not matched_terms:
            continue
        key = _normalize_whitespace(quote_text).lower()[:120]
        if key not in seen_quote_keys:
            seen_quote_keys.add(key)
            review_quotes_out.append({
                'pill': 'search_keywords',
                'pill_label': 'kata kunci target',
                'quote': quote_text,
                'reason': ', '.join(matched_terms[:3]),
                'rating': match.get('rating'),
                'username': match.get('username'),
                **_quote_ui_extras(match),
            })
        search_keyword_matches_out.append({
            'matched_terms': matched_terms[:6],
            'quote': quote_text,
            'rating': match.get('rating'),
            'username': match.get('username'),
            **_quote_ui_extras(match),
        })

    # Kutipan hasil gerbang makna: tidak memuat kata kunci persis, tapi maknanya
    # dekat dengan preferensi. Ditandai supaya bisa dibedakan di UI/telemetry.
    semantic_matches_out = []
    for match in ((score_detail or {}).get('semantic_matches') or [])[:3]:
        quote_text = match.get('quote')
        matched_terms = [str(t).strip() for t in (match.get('matched_terms') or []) if str(t).strip()]
        if not quote_text or not matched_terms:
            continue
        key = _normalize_whitespace(quote_text).lower()[:120]
        if key not in seen_quote_keys:
            seen_quote_keys.add(key)
            review_quotes_out.append({
                'pill': 'semantic_match',
                'pill_label': 'Makna serupa',
                'quote': quote_text,
                'reason': f"mirip makna: {matched_terms[0]}",
                'rating': match.get('rating'),
                'username': match.get('username'),
                'match_source': 'semantic',
                'semantic_score': match.get('semantic_score'),
                **_quote_ui_extras(match),
            })
        semantic_matches_out.append({
            'matched_terms': matched_terms[:4],
            'quote': quote_text,
            'rating': match.get('rating'),
            'username': match.get('username'),
            'semantic_score': match.get('semantic_score'),
            'semantic_clause': match.get('semantic_clause'),
            **_quote_ui_extras(match),
        })

    facilities_tab_full = profile.get('facilities_tab') or {
        'popular_for': [], 'highlights': [], 'atmosphere': []
    }
    intent_blob = _collect_intent_strings_for_facilities(pills, search_keywords)
    facilities_tab_display, facilities_intent_aligned = _facilities_tab_display_for_intent(
        facilities_tab_full, intent_blob
    )
    facilities_evidence_summary = _build_facilities_evidence_summary(
        facilities_tab_display, facilities_intent_aligned
    )
    positive_quotes, negative_quotes = _pick_sentiment_review_quotes(
        profile.get('reviews') or [],
        pills,
        search_keywords=search_keywords,
        positive_limit=3,
        negative_limit=2,
    )

    return {
        'facilities': [],  # tidak dipakai: ranking hanya dari review user
        'facilities_tab': facilities_tab_full,
        'facilities_tab_intent': facilities_tab_display,
        'facilities_intent_aligned': facilities_intent_aligned,
        'facilities_evidence_summary': facilities_evidence_summary,
        'review_quotes': review_quotes_out[:12],
        'positive_review_quotes': positive_quotes,
        'negative_review_quotes': negative_quotes,
        'search_keywords': search_keywords,
        'search_keyword_matches': search_keyword_matches_out,
        'semantic_matches': semantic_matches_out,
        'semantic_score': (score_detail or {}).get('semantic_score', 0.0),
        'pill_stats': pill_stats_out,
        'category_ratings': profile.get('avg_category_ratings') or {
            'makanan': None, 'layanan': None, 'suasana': None
        },
        'avg_user_rating': profile.get('avg_user_rating'),
        'review_count': profile.get('review_count', 0),
        'google_rating': profile.get('google_rating'),
        'google_total_reviews': profile.get('google_total_reviews'),
        'community_signals': profile.get('community_signals') or {},
        'is_low_confidence': False,
    }
def _join_indonesian_topics(labels):
    """Gabung label topik untuk satu frasa (sudah huruf kecil / siap pakai)."""
    labels = [l for l in labels if l]
    if not labels:
        return ''
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f'{labels[0]} dan {labels[1]}'
    return ', '.join(labels[:-1]) + f', dan {labels[-1]}'
def _pills_matching_review_text(text, pills):
    """Pill dari daftar pills yang punya minimal satu keyword cocok dengan teks review."""
    if not text or not pills:
        return set()
    matched = set()
    for pill in pills:
        keywords = _expand_pill_to_keywords(pill)
        if any(_matches_keyword_phrase(text, kw) for kw in keywords):
            matched.add(pill)
    return matched
def _topic_labels_for_shop_summary(pills, pill_stats, quote_text=None):
    """
    Label topik (huruf kecil) untuk kalimat ringkasan: gabungan statistik per pill
    dan bukti langsung di kutipan — agar satu review yang menyebut musholla + wifi
    tetap menonjolkan ruang ibadah dan wifi bila keduanya dipilih user.
    """
    pill_list = pills or []
    pill_set = set(pill_list)
    from_stats = {
        s['pill'] for s in (pill_stats or [])
        if s.get('keyword_review_hits', 0) > 0 and s.get('pill') in pill_set
    }
    from_quote = _pills_matching_review_text(quote_text or '', pill_list)
    combined = (from_stats | from_quote) & pill_set
    ordered_pills = [p for p in pill_list if p in combined]
    # Awalan label UI dibuang ("Ada musholla" → "musholla") supaya frasa tetap wajar
    # saat disisipkan ke kalimat "cocok untuk ...".
    return [_plain_pill_label(PILL_LABELS.get(p, p)) for p in ordered_pills]
def _strip_structured_summary_labels(text):
    """
    Hapus label struktur (Kesimpulan/Kelebihan/Catatan) dari ringkasan rekomendasi
    supaya tampil sebagai satu paragraf naratif.
    """
    cleaned = _normalize_whitespace(text)
    if not cleaned:
        return ''
    label_patterns = (
        r'Kesimpulan\s*:\s*',
        r'Kelebihannya\s*,?\s*',
        r'Kelebihan\s*:\s*',
        r'Catatan kecilnya\s*,?\s*',
        r'Catatan\s*:\s*',
        r'Kekurangannya\s*,?\s*',
        r'Kekurangan\s*:\s*',
    )
    for pattern in label_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    return _normalize_whitespace(cleaned)
def _join_narrative_summary_parts(*parts):
    """Gabung potongan ringkasan menjadi satu paragraf tanpa label struktur."""
    sentences = []
    for part in parts:
        chunk = _strip_structured_summary_labels(str(part or ''))
        if not chunk:
            continue
        if chunk[-1] not in '.!?':
            chunk += '.'
        sentences.append(chunk)
    return _normalize_whitespace(' '.join(sentences))
def _third_person_review_snippet(quote, *, limit=140):
    """Parafrase ringan: buang kata orang pertama, potong agar tidak menyalin ulasan utuh."""
    snippet = _normalize_whitespace(quote or '')
    if not snippet:
        return ''
    snippet = re.sub(
        r'\b(saya|aku|kami|gue|gw)\b',
        'pengunjung',
        snippet,
        flags=re.I,
    )
    if len(snippet) > limit:
        snippet = snippet[: limit - 1].rstrip() + '…'
    return snippet
def _build_review_summary_deterministic(shop, pills, search_keywords=None, user_intent_line=None):
    """Fallback summary (tanpa LLM) — paragraf naratif berbasis review."""
    # Kalimat pembuka hanya menyebut pill yang punya bukti di kutipan.
    detail = shop.get('score_detail') or {}
    covered_pills = detail.get('covered_pills')
    topic_pills = (
        [p for p in pills if p in covered_pills]
        if covered_pills is not None else list(pills or [])
    )
    pill_labels = [_plain_pill_label(PILL_LABELS.get(p, p)) for p in topic_pills]
    evidence = shop.get('evidence') or {}
    review_count = evidence.get('review_count') or shop.get('profile', {}).get('review_count', 0)
    pill_stats = evidence.get('pill_stats') or []
    review_quotes = evidence.get('review_quotes') or []
    positive_quotes = evidence.get('positive_review_quotes') or []
    avg = evidence.get('avg_user_rating')
    supporting_quotes, _caveat_quotes = _collect_modal_quote_groups(
        evidence,
        pills,
        search_keywords=evidence.get('search_keywords'),
    )

    top_signal = None
    if any(s.get('keyword_review_hits') for s in pill_stats):
        top_signal = max(pill_stats, key=lambda s: s.get('keyword_review_hits', 0))

    first_quote = (
        (supporting_quotes[0] if supporting_quotes else None)
        or (positive_quotes[0] if positive_quotes else None)
        or (review_quotes[0] if review_quotes else None)
    )
    quote_blob_for_topics = ' '.join(
        (q.get('quote') or '').strip()
        for q in (review_quotes or [])[:3]
        if (q.get('quote') or '').strip()
    )
    topics_phrase = _join_indonesian_topics(
        _topic_labels_for_shop_summary(topic_pills, pill_stats, quote_blob_for_topics)
    )
    if not topics_phrase and top_signal and top_signal['pill_label'].lower() in pill_labels:
        topics_phrase = top_signal['pill_label'].lower()
    if not topics_phrase and pill_labels:
        topics_phrase = _join_indonesian_topics(pill_labels)

    need_lines = _user_need_coverage_prompt_lines(shop, pills, search_keywords)
    uncovered_fragments = []
    proven_fragments = []
    for line in need_lines:
        fragment = line.split(':', 1)[-1].strip()
        if 'BELUM terbukti' in line:
            uncovered_fragments.append(fragment)
        elif 'TERBUKTI' in line:
            proven_fragments.append(fragment)
    intro_uses_proven = False
    if not topics_phrase and not pills and proven_fragments:
        topics_phrase = ', '.join(proven_fragments)
        intro_uses_proven = True

    shop_name = shop.get('name') or 'Coffee shop ini'
    if topics_phrase:
        intro = (
            f"{shop_name} menurut ulasan pengunjung relevan untuk {topics_phrase}"
        )
    else:
        intro = f"{shop_name} dibahas pengunjung dalam ulasan yang ada"
    if avg is not None:
        intro += f", dengan rata-rata rating {avg:.1f}/5"
    elif review_count:
        intro += f" dari {review_count} ulasan pengguna"
    intro += '.'

    snippet = _third_person_review_snippet(
        (first_quote or {}).get('quote') if first_quote else '',
    )
    if snippet:
        strength = (
            f'Pengunjung menyoroti detail konkret, antara lain {snippet}.'
        )
    elif top_signal:
        strength = (
            f'Ulasan cukup sering menyinggung aspek '
            f'{top_signal["pill_label"].lower()}.'
        )
    else:
        strength = (
            'Detail fasilitas atau suasana yang spesifik masih terbatas di ulasan.'
        )

    parts = [intro, strength]
    if proven_fragments and not intro_uses_proven:
        parts.append(
            f'Beberapa ulasan juga menyinggung soal {", ".join(proven_fragments)}.'
        )
    if uncovered_fragments:
        joined = ', '.join(uncovered_fragments)
        parts.append(
            f'Sayangnya belum ada ulasan yang menyebut soal {joined}, jadi belum bisa '
            'dipastikan ada atau tidak.'
        )

    return _join_narrative_summary_parts(*parts)
def _summary_mentions_other_shop(summary, shop, all_shops):
    """
    Nama kandidat lain yang bocor ke ringkasan toko ini, atau None kalau bersih.

    Semua kandidat dikirim dalam satu prompt, dan model kecil kadang mencampur
    nama antar blok (paragraf untuk toko A dibuka dengan nama toko B). Kutipan
    sudah diverifikasi terpisah, tapi nama tidak — ini penutup celah itu.
    """
    text = str(summary or '').lower()
    if not text:
        return None
    own = str(shop.get('name') or '').strip().lower()
    for other in all_shops or []:
        name = str(other.get('name') or '').strip().lower()
        if not name or name == own:
            continue
        # Nama yang bertumpang dengan nama toko ini sendiri bukan bukti tertukar
        # (mis. "Aming Coffee" di dalam "Aming Coffee Ilham").
        if name in own or own in name:
            continue
        if name in text:
            return other.get('name')
    return None
def _plain_pill_label(label):
    """Buang awalan label UI ("Ada musholla") agar enak dibaca dalam kalimat."""
    text = str(label or '').strip().lower()
    for prefix in ('ada ', 'banyak '):
        if text.startswith(prefix):
            return text[len(prefix):]
    return text
def _build_summary_output_entry(shop, summary, pills, search_keywords):
    """Bangun entri output rekomendasi yang seragam untuk semua jalur (cache/LLM/fallback)."""
    summary = _strip_structured_summary_labels(summary or '')
    if summary and summary[-1] not in '.!?':
        summary += '.'
    evidence_out = _attach_modal_evidence_to_supporting(
        shop.get('evidence') or _build_empty_supporting_evidence(),
        shop.get('name') or '',
        pills,
        search_keywords=search_keywords,
    )
    # Shop tanpa kutipan relevan tidak boleh masuk respons.
    if not (evidence_out.get('modal_display_quotes') or []):
        return None
    llm_fit = shop.get('llm_fit') if isinstance(shop.get('llm_fit'), dict) else None
    detail = shop.get('score_detail') or {}
    matched_pills, matched_labels = _matched_facility_from_gate(
        evidence_out.get('metadata_gate'),
        detail,
        reviews=_shop_reviews_for_facility_badge(shop),
    )
    return {
        'place_id': shop['place_id'],
        'name': shop['name'],
        'score': shop.get('score', 0),
        'final_score': shop.get('final_score', shop.get('score', 0)),
        'ranking_source': 'llm' if llm_fit else 'hybrid',
        'llm_fit': llm_fit,
        'explanation': summary,
        'matched_facility_pills': matched_pills,
        'matched_facility_labels': matched_labels,
        # Kelengkapan pemenuhan pill: dipakai untuk jujur menyebut atribut yang
        # belum punya bukti ulasan pada ringkasan tiap toko.
        'pill_coverage': {
            'covered': detail.get('covered_pills') or [],
            'uncovered': detail.get('uncovered_pills') or [],
            'covered_labels': [
                PILL_LABELS.get(p, p) for p in (detail.get('covered_pills') or [])
            ],
            'uncovered_labels': [
                PILL_LABELS.get(p, p) for p in (detail.get('uncovered_pills') or [])
            ],
            'activity_coverage': detail.get('activity_coverage'),
            'attribute_coverage': detail.get('attribute_coverage'),
            'coverage_ratio': detail.get('coverage_ratio'),
        },
        'supporting_evidence': evidence_out,
        'review_count': evidence_out.get('review_count', 0),
        'avg_user_rating': evidence_out.get('avg_user_rating'),
        'is_low_confidence': evidence_out.get('is_low_confidence', False),
    }
def _generate_llm_review_summary(
    top_shops,
    pills,
    search_keywords=None,
    user_intent_line=None,
    summary_framing=None,
):
    """
    NLP summary per shop, **selalu** dibangkitkan ulang setiap request.

    Sengaja tanpa cache: ringkasan harus menyesuaikan kombinasi pill aktivitas +
    atribut fasilitas yang dipilih user saat itu, termasuk catatan pill mana yang
    belum terbukti di ulasan. Cache per (place_id + pill) dulu membuat paragraf
    lama ikut terbawa dan sempat mengunci satu paragraf yang salah nama toko.
    Jika LLM tidak tersedia / gagal parse, pakai fallback deterministik.
    Shop tanpa kutipan relevan dibuang dari output.
    """
    empty_stats = {'summary_llm_count': 0, 'summary_fallback_count': 0}
    if not top_shops:
        return [], empty_stats

    search_keywords = _light_keyword_phrase_list(search_keywords or [])

    LOG_RECOMMEND.info(f"Summary: generate={len(top_shops)} (tanpa cache)")
    generated_summary_map, summary_stats = _llm_summaries_for_shops(
        top_shops,
        pills,
        search_keywords,
        user_intent_line=user_intent_line,
        summary_framing=summary_framing,
    )

    # Rakit output sesuai urutan asli; skip shop tanpa bukti kutipan.
    output = []
    for shop in top_shops:
        summary = (
            generated_summary_map.get(shop['place_id'])
            or _build_review_summary_deterministic(
                shop, pills,
                search_keywords=search_keywords,
                user_intent_line=user_intent_line,
            )
        )
        entry = _build_summary_output_entry(shop, summary, pills, search_keywords)
        if entry is None:
            LOG_RECOMMEND.warning(
                f"Summary: drop {shop.get('name')} — tanpa modal_display_quotes")
            continue
        output.append(entry)
    return output, summary_stats
def _unverified_summary_quotes(summary, shop):
    """
    Kutipan pada summary LLM yang tidak bisa ditemukan di korpus review toko.
    Kosong berarti seluruh kutipan tergrounding (atau grounding check dimatikan).
    """
    if not llm_grounding_check_enabled():
        return []
    corpus = shop_corpus_text((shop.get('profile') or {}).get('reviews') or [])
    if not corpus:
        return []
    return ungrounded_quotes(summary, corpus)
def _normalize_place_id(value):
    return re.sub(r'\s+', '', str(value or '')).strip()
def _normalize_shop_name_key(value):
    text = _normalize_whitespace(value).lower()
    return re.sub(r'[^\w\s]+', '', text, flags=re.UNICODE).strip()
def _llm_item_summary_text(item):
    """Ambil paragraf summary dari satu objek JSON LLM (string, list, atau objek bersarang)."""
    if not isinstance(item, dict):
        return ''

    def _as_text(value):
        if value is None or value == '':
            return ''
        if isinstance(value, dict):
            conclusion = value.get('conclusion') or value.get('kesimpulan') or ''
            strengths = value.get('strengths') or value.get('kelebihan') or ''
            weaknesses = (
                value.get('weaknesses')
                or value.get('kekurangan')
                or value.get('catatan')
                or ''
            )
            if isinstance(strengths, list):
                strengths = '; '.join(
                    _normalize_whitespace(str(v or '')) for v in strengths if str(v or '').strip()
                )
            if isinstance(weaknesses, list):
                weaknesses = '; '.join(
                    _normalize_whitespace(str(v or '')) for v in weaknesses if str(v or '').strip()
                )
            return _join_narrative_summary_parts(conclusion, strengths, weaknesses)
        if isinstance(value, list):
            return _join_narrative_summary_parts(*value)
        return _strip_structured_summary_labels(str(value))

    summary = _as_text(item.get('summary') or item.get('explanation'))
    if summary:
        return summary
    return _join_narrative_summary_parts(
        item.get('conclusion') or item.get('kesimpulan'),
        item.get('strengths') or item.get('kelebihan'),
        item.get('weaknesses') or item.get('kekurangan') or item.get('catatan'),
    )
def _assign_llm_summaries_to_shops(parsed_items, top_shops):
    """
    Pasangkan output JSON LLM ke toko: place_id exact, fuzzy, nama, lalu urutan.
    Toko yang tidak ketemu dibiarkan kosong (pemanggil memakai fallback deterministik).
    """
    assigned = {}
    used_pids = set()
    used_item_idx = set()
    items = list(parsed_items or [])

    def take(shop, summary, item_idx, via):
        if not shop or not summary:
            return False
        pid = shop.get('place_id')
        if not pid or pid in used_pids:
            return False
        assigned[pid] = summary
        used_pids.add(pid)
        if item_idx is not None:
            used_item_idx.add(item_idx)
        if via != 'place_id':
            LOG_RECOMMEND.info(
                f"Summary: match {via} → {shop.get('name')} ({pid})")
        return True

    pid_index = {_normalize_place_id(s.get('place_id')): s for s in top_shops if s.get('place_id')}

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        summary = _llm_item_summary_text(item)
        shop = pid_index.get(_normalize_place_id(item.get('place_id')))
        if shop:
            take(shop, summary, idx, 'place_id')

    for idx, item in enumerate(items):
        if idx in used_item_idx or not isinstance(item, dict):
            continue
        summary = _llm_item_summary_text(item)
        raw = _normalize_place_id(item.get('place_id'))
        if not raw:
            continue
        hits = [
            s for s in top_shops
            if s.get('place_id') not in used_pids
            and (
                raw in _normalize_place_id(s.get('place_id'))
                or _normalize_place_id(s.get('place_id')) in raw
            )
        ]
        if len(hits) == 1:
            take(hits[0], summary, idx, 'place_id_fuzzy')

    name_index = {}
    for shop in top_shops:
        key = _normalize_shop_name_key(shop.get('name'))
        if key:
            name_index.setdefault(key, []).append(shop)

    for idx, item in enumerate(items):
        if idx in used_item_idx or not isinstance(item, dict):
            continue
        summary = _llm_item_summary_text(item)
        key = _normalize_shop_name_key(item.get('name'))
        hits = [s for s in name_index.get(key, []) if s.get('place_id') not in used_pids]
        if len(hits) == 1:
            take(hits[0], summary, idx, 'name')

    leftover_shops = [s for s in top_shops if s.get('place_id') not in used_pids]
    leftover_items = [
        (idx, item)
        for idx, item in enumerate(items)
        if idx not in used_item_idx
        and isinstance(item, dict)
        and _llm_item_summary_text(item)
    ]
    for shop, (idx, item) in zip(leftover_shops, leftover_items):
        take(shop, _llm_item_summary_text(item), idx, 'index')

    return assigned
def _summary_sentence_count(text):
    normalized = _normalize_whitespace(str(text or ''))
    if not normalized:
        return 0
    parts = re.split(r'(?<=[.!?])\s+', normalized)
    return len([part for part in parts if part.strip()])
def _plain_summary_from_llm_raw(raw, shop):
    """Gemini kadang mengembalikan prosa tanpa JSON — dipakai jika memenuhi panjang."""
    text = str(raw or '').strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.I)
    text = re.sub(r'\s*```\s*$', '', text).strip()
    if text.startswith('{') or text.startswith('['):
        return ''
    text = _strip_structured_summary_labels(text)
    text = _normalize_whitespace(text)
    if len(text) < COFIND_SUMMARY_MIN_CHARS:
        return ''
    if _summary_sentence_count(text) < COFIND_SUMMARY_MIN_SENTENCES:
        return ''
    return text
def _coerce_step5_summary_text(raw, shop):
    """Parse JSON / prosa LLM menjadi paragraf Step 5, atau string kosong."""
    summary = _parse_single_shop_summary(raw, shop)
    if not summary:
        summary = _plain_summary_from_llm_raw(raw, shop)
    return summary or ''
def _invalid_llm_summary_reason(summary, shop, all_shops):
    """Alasan menolak ringkasan LLM, atau None kalau lolos jaring pengaman."""
    if not summary:
        return 'summary kosong'
    stripped = summary.strip()
    if len(stripped) < COFIND_SUMMARY_MIN_CHARS:
        return f'terlalu pendek ({len(stripped)} chars)'
    if _summary_sentence_count(stripped) < COFIND_SUMMARY_MIN_SENTENCES:
        return 'terlalu sedikit kalimat'
    if stripped[-1] not in '.!?…”"\')':
        # Kalimat terakhir tidak diakhiri tanda baca → kemungkinan terpotong
        # karena kehabisan max_tokens di tengah kalimat. Jangan tampilkan ke
        # user, lebih baik retry atau fallback deterministik yang lengkap.
        return 'ringkasan terpotong (tidak diakhiri tanda baca)'
    if _GENERIC_SHORT_SUMMARY_RE.match(stripped):
        return 'ringkasan generik terlalu pendek'
    shop_name = str((shop or {}).get('name') or '').strip()
    if shop_name and stripped.lower().startswith(shop_name.lower()):
        tail = stripped[len(shop_name):].lstrip(' ,.-–—')
        if len(tail.split()) < 6:
            return 'terlalu generik setelah nama toko'
    low = summary.lower()
    if any(bad in low for bad in ['place_id', '[fasilitas]', '[review]', 'json']):
        return 'summary mengandung artefak prompt'
    if re.search(
        r'cocok.{0,50}(tidak ada (informasi|ulasan|data)|belum ada informasi)',
        summary,
        re.I,
    ):
        return 'mengklaim cocok dari ketiadaan informasi'
    if re.search(r'tidak (?:cocok untuk|memiliki fasilitas|mendukung)', summary, re.I):
        # Menyimpulkan ketiadaan fasilitas dari ketiadaan ulasan adalah
        # klaim yang tidak tergrounding — lebih baik pakai deterministik.
        return 'menyimpulkan negatif dari absennya ulasan'
    intruder = _summary_mentions_other_shop(summary, shop, all_shops)
    if intruder:
        return f'menyebut kandidat lain ({intruder})'
    unverified = _unverified_summary_quotes(summary, shop)
    if unverified:
        return f'kutipan tidak ada di review: {unverified[0][:60]}'
    return None
def _looks_like_generic_praise(text):
    normalized = _normalize_keyword_phrase(text)
    if not normalized or len(normalized) > 90:
        return False
    return any(marker in normalized for marker in _GENERIC_PRAISE_MARKERS)
def _filter_generic_unrelated_quotes(quotes, pills, search_keywords=None):
    """Buang pujian generik tanpa kaitan aktivitas; jangan sampai kehabisan bukti."""
    rows = [row for row in (quotes or []) if isinstance(row, dict)]
    if not rows:
        return list(quotes or [])
    kept = []
    for row in rows:
        if _quote_has_activity_or_semantic_link(row, pills, search_keywords):
            kept.append(row)
            continue
        if _looks_like_generic_praise(row.get('quote') or ''):
            continue
        kept.append(row)
    return kept if kept else list(rows)
def _free_text_uncovered_keywords(shop, keywords, *, limit=6):
    """
    Keyword free text yang TIDAK ditemukan buktinya di korpus ulasan toko ini.

    Dipakai untuk jalur free text tanpa pill match (RRF), di mana tidak ada
    `covered_pills`/`uncovered_pills` (keduanya kosong karena `pills=[]`).
    Pencocokan memakai `text_matches_tokens` yang sama dengan hybrid retrieval,
    jadi konsisten dengan definisi "ada bukti" di tempat lain pipeline.
    """
    cleaned = []
    seen = set()
    for kw in keywords or []:
        text = str(kw or '').strip()
        key = text.lower()
        if not text or key in seen or key in _FREE_TEXT_GENERIC_STOP:
            continue
        seen.add(key)
        cleaned.append(text)
    if not cleaned:
        return [], []

    reviews = (shop.get('profile') or {}).get('reviews') or []
    corpus = shop_corpus_text(reviews)
    covered, uncovered = [], []
    for kw in cleaned:
        # Normalisasi slang/sinonim domain (sama seperti BM25/dense query) sebelum
        # dicocokkan — tanpa ini "wfc"/"colokan" tidak match korpus yang sudah
        # ternormalisasi jadi "work from cafe"/"stopkontak".
        kw_tokens = tokenize_normalized(kw) or [kw]
        if corpus and text_matches_tokens(corpus, kw_tokens):
            covered.append(kw)
        else:
            uncovered.append(kw)
    return covered, uncovered[:limit]
def _user_need_coverage_prompt_lines(shop, pills, search_keywords):
    """
    Baris injeksi konteks untuk Step 5: kebutuhan user mana yang terbukti vs belum
    di ulasan toko ini (pill path atau free-text keywords).
    """
    detail = shop.get('score_detail') or {}
    lines = []
    if pills:
        covered_labels = [
            _plain_pill_label(PILL_LABELS.get(p, p))
            for p in (detail.get('covered_pills') or [])
        ]
        uncovered_labels = [
            _plain_pill_label(PILL_LABELS.get(p, p))
            for p in (detail.get('uncovered_pills') or [])
        ]
        if covered_labels:
            lines.append(
                'Kebutuhan user yang TERBUKTI di ulasan toko ini: '
                + ', '.join(covered_labels)
            )
        if uncovered_labels:
            lines.append(
                'Kebutuhan user yang BELUM terbukti di ulasan toko ini: '
                + ', '.join(uncovered_labels)
            )
    else:
        covered_kw, uncovered_kw = _free_text_uncovered_keywords(shop, search_keywords)
        if covered_kw:
            lines.append(
                'Kata kunci kebutuhan user yang TERBUKTI di ulasan toko ini: '
                + ', '.join(covered_kw)
            )
        if uncovered_kw:
            lines.append(
                'Kata kunci kebutuhan user yang BELUM terbukti di ulasan toko ini: '
                + ', '.join(uncovered_kw)
            )
    return lines
def _shop_summary_data_block(shop, pills, search_keywords, *, prefer_gemini=False):
    """
    Blok data SATU toko untuk prompt ringkasan.

    Sengaja pendek: kutipan relevan dan sinyal fasilitas/aktivitas terbukti.
    """
    evidence = shop.get('evidence') or {}
    supporting_quotes, _caveat_quotes = _collect_modal_quote_groups(
        evidence, pills, search_keywords=search_keywords,
    )
    if not evidence.get('llm_extracted'):
        supporting_quotes = _filter_generic_unrelated_quotes(
            supporting_quotes, pills, search_keywords,
        )
    quote_limit = 5 if prefer_gemini else 4
    quote_char_limit = 260 if prefer_gemini else 220
    relevant_quote_lines = _relevant_quote_lines_for_prompt(
        {'modal_display_quotes': supporting_quotes[:quote_limit]},
        limit=quote_limit,
        char_limit=quote_char_limit,
    ) or ['- (tidak ada kutipan yang cocok konteks)']

    detail = shop.get('score_detail') or {}
    covered_activity = [
        _plain_pill_label(PILL_LABELS.get(p, p))
        for p in (detail.get('activity_pills') or [])
        if p in set(detail.get('covered_pills') or [])
    ]
    covered_activity_line = (
        ", ".join(covered_activity) if covered_activity else "(tidak ada bukti aktivitas di kutipan)"
    )
    shop_name = shop.get('name') or 'Coffee shop ini'
    supplement = supplemental_coverage_lines(shop, pills)
    supplement_block = ''
    if supplement:
        supplement_block = (
            'Sinyal pendukung (profil/jam buka):\n'
            + '\n'.join(supplement)
            + '\n'
        )
    covered_attrs = [
        _plain_pill_label(PILL_LABELS.get(p, p))
        for p in (detail.get('attribute_pills') or [])
        if p in set(detail.get('covered_pills') or [])
    ]
    covered_attr_line = (
        ', '.join(covered_attrs) if covered_attrs else '(tidak ada fasilitas tambahan terbukti)'
    )

    need_coverage_lines = _user_need_coverage_prompt_lines(shop, pills, search_keywords)
    need_coverage_block = ''
    if need_coverage_lines:
        need_coverage_block = (
            'Cakupan kebutuhan user vs ulasan toko (WAJIB dibahas di summary):\n'
            + '\n'.join(f'- {line}' for line in need_coverage_lines)
            + '\n'
        )

    return (
        f"Tempat: {shop_name}\n"
        f"Aktivitas yang ADA bukti ulasannya: {covered_activity_line}\n"
        f"Fasilitas tambahan yang ADA buktinya (ulasan/profil/jam buka): {covered_attr_line}\n"
        f"{supplement_block}"
        f"{need_coverage_block}"
        "Kutipan relevan (bukti utama — utamakan ini untuk kalimat pembuka):\n"
        + "\n".join(relevant_quote_lines)
    )
def _summary_use_gemini(summary_route_mode=None):
    """True jika Step 5 harus langsung Gemini (tanpa coba HF)."""
    if summary_route_mode == 'gemini':
        return True
    if summary_route_mode in ('hf', 'off'):
        return False
    route = get_llm_run_route()
    if route is not None:
        return route.mode == 'gemini'
    provider, _ = get_last_llm_provider()
    return provider == 'gemini'
def _summary_output_requirements_block(*, strict=False):
    min_chars = COFIND_SUMMARY_MIN_CHARS
    lines = [
        'Persyaratan panjang & kualitas:',
        f'- Field "summary" {COFIND_SUMMARY_MIN_SENTENCES}-4 kalimat mengalir dan '
        f'minimal ±{min_chars} karakter — tapi PRIORITASKAN kalimat selesai dengan rapi '
        'di atas menambah detail baru. Lebih baik 3 kalimat tuntas daripada 4 kalimat '
        'yang terpotong di tengah.',
        '- Isinya: nama toko + relevansi ke kebutuhan user, lalu 1-2 detail fasilitas/suasana '
        'konkret dari kutipan, dan selipkan secara natural info soal kebutuhan user yang '
        'belum ada buktinya di ulasan (jika ada) — bukan sebagai kalimat template terpisah, '
        'tapi menyatu dengan gaya bahasa paragraf.',
        '- Gunakan Bahasa Indonesia sehari-hari yang hangat dan mengalir seperti rekomendasi '
        'dari teman, BUKAN bahasa laporan/formal baku (hindari frasa seperti "berdasarkan hasil '
        'analisis", "sehubungan dengan", "secara eksplisit", "TERBUKTI"/"BELUM terbukti" '
        'secara literal — parafrase, jangan copy label data).',
        '- DILARANG kalimat generik seperti "X dinilai cocok", "X menjadi salah", '
        'atau hanya menyebut nama toko tanpa detail ulasan.',
        '- Jangan mengarang kebutuhan di luar data, dan jangan mengada-ada kekurangan kalau '
        'tidak ada data "belum terbukti".',
        '- WAJIB akhiri paragraf dengan tanda baca (. ! atau ?) sebelum berhenti menulis.',
    ]
    if strict:
        lines.append(
            '- Respons sebelumnya ditolak (terlalu pendek/generik/terpotong di tengah kalimat). '
            'Tulis ulang paragraf PENDEK tapi TUNTAS (3 kalimat utuh lebih aman daripada 4 '
            'kalimat yang berisiko terpotong), tetap berbasis kutipan di data.'
        )
    return '\n'.join(lines)
def _single_shop_summary_prompt(
    shop,
    pills,
    search_keywords,
    intent_line,
    *,
    quality_boost=False,
    prefer_gemini=False,
    summary_framing=None,
):
    """Prompt ringkas: satu toko, paragraf objektif dari kutipan relevan."""
    shop_name = shop.get('name') or 'Coffee shop ini'
    use_quality = quality_boost or prefer_gemini
    data_block = _compact_prompt_block(
        _shop_summary_data_block(
            shop, pills, search_keywords, prefer_gemini=prefer_gemini,
        ),
        2400,
    )
    activity_pills, _ = _split_preference_pills(pills)
    activity_context = format_activity_context_block(
        activity_pills,
        pill_mapping=PILL_MAPPING,
        pill_labels=PILL_LABELS,
    )
    context_section = f'{activity_context}\n\n' if activity_context else ''
    example_block = ''
    if use_quality:
        min_c = COFIND_SUMMARY_MIN_CHARS
        example_block = (
            f"\nContoh gaya (isi harus dari data {shop_name}, jangan salin teks contoh; "
            f'natural, bukan laporan formal):\n'
            f'{{"summary":"{shop_name} cukup pas buat kerja santai — ulasan bilang area '
            f'duduknya nyaman dan AC-nya dingin. Colokan juga lumayan banyak di tiap meja, '
            f'jadi enak buat yang bawa laptop. Sayangnya belum ada yang nyebut soal musholla '
            f'di ulasan, jadi belum pasti ada atau tidak."}}'
        )
    framing_block = ''
    if summary_framing:
        framing_block = f'Catatan framing (WAJIB diikuti):\n{summary_framing}\n\n'
    return (
        f"Tulis 1 paragraf singkat ({COFIND_SUMMARY_MIN_SENTENCES}-4 kalimat, mengalir natural) "
        f"tentang {shop_name} berdasarkan ulasan pelanggan — gaya rekomendasi dari teman, "
        "bukan laporan formal.\n\n"
        f"Kebutuhan user: {intent_line}.\n\n"
        f"{framing_block}"
        "Cek blok \"Cakupan kebutuhan user vs ulasan\" di data: sebutkan secara natural (bukan "
        "copy-paste label TERBUKTI/BELUM terbukti) apakah kebutuhan itu kelihatan ada buktinya "
        "di ulasan toko ini atau belum — selipkan jadi 1 klausa/kalimat singkat dalam paragraf, "
        "jangan dipaksakan jadi kalimat tambahan yang kaku.\n\n"
        f"{context_section}"
        f"{data_block}\n\n"
        "Aturan Penulisan:\n"
        "1. Faktual & Objektif tapi santai: sudut pandang orang ketiga, bahasa sehari-hari yang "
        "hangat (hindari \"berdasarkan hasil analisis\", \"secara eksplisit\", dsb). JANGAN "
        "menyalin kata 'saya'/'aku'/'kami' dari ulasan.\n"
        "2. Kalimat Pembuka: sebutkan nama tempat dan hubungkan dengan kebutuhan user (hanya "
        "jika didukung fakta ulasan).\n"
        "3. Detail Konkret: 1-2 fasilitas/suasana spesifik dari kutipan (bukan klaim sepihak).\n"
        "4. Cakupan Kebutuhan: selipkan 1 klausa natural soal kebutuhan yang belum ada buktinya "
        "(jika ada di data) — contoh gaya: \"belum ada yang nyebut soal musholla\", bukan "
        "\"BELUM terbukti: musholla\". Jangan klaim ada fasilitas yang justru belum terbukti.\n"
        "5. Prioritaskan paragraf TUNTAS: lebih baik 3 kalimat selesai rapi daripada 4 kalimat "
        "yang berisiko terpotong sebelum tanda baca penutup.\n"
        "6. Output: satu paragraf utuh, tanpa judul/label.\n"
        f"{example_block}\n"
        f"{_summary_output_requirements_block(strict=False)}\n\n"
        'Balas HANYA dengan JSON murni: {"summary":"..."}'
    )
def _parse_summary_json_local(raw_text, *, expected='any'):
    """Parse JSON tanpa panggilan LLM repair (json.loads + json_repair library)."""

    def _validate_shape(obj):
        if expected == 'array' and not isinstance(obj, list):
            raise ValueError("expected array")
        if expected == 'object' and not isinstance(obj, dict):
            raise ValueError("expected object")
        return obj

    candidate = _extract_json_candidate(raw_text, expected=expected)
    if not candidate:
        return None
    try:
        return _validate_shape(json.loads(candidate))
    except Exception:
        pass
    if repair_json is not None:
        try:
            fixed = repair_json(candidate, skip_json_loads=True)
            return _validate_shape(json.loads(str(fixed)))
        except Exception:
            pass
    return None
def _extract_summary_field_loose(raw_text):
    """Ambil string summary dari JSON tidak sempurna (Gemini sering hampir-valid)."""
    text = str(raw_text or '').strip()
    if not text:
        return ''
    match = re.search(
        r'"summary"\s*:\s*"((?:\\.|[^"\\])*)"',
        text,
        flags=re.I | re.S,
    )
    if not match:
        return ''
    try:
        return json.loads(f'"{match.group(1)}"')
    except Exception:
        return match.group(1).replace('\\"', '"').replace('\\n', ' ').strip()
def _parse_single_shop_summary(raw, shop):
    """Ambil teks summary dari JSON objek atau array 1 item."""
    parsed = _parse_summary_json_local(raw, expected='any')
    route = get_llm_run_route()
    skip_llm_repair = route is not None and route.mode == 'gemini'
    if parsed is None and llm_is_available() and not skip_llm_repair:
        try:
            parsed = _parse_llm_json_with_repair(
                raw,
                expected='any',
                model=None,
                max_llm_passes=1,
                usage_stage='summary_json_repair',
            )
        except ValueError:
            parsed = None
    if isinstance(parsed, dict):
        nested = parsed.get('recommendations') or parsed.get('items') or parsed.get('shops')
        items = nested if isinstance(nested, list) else [parsed]
    elif isinstance(parsed, list):
        items = parsed
    else:
        return ''
    assigned = _assign_llm_summaries_to_shops(items, [shop])
    text = assigned.get(shop.get('place_id')) or ''
    if text:
        return text
    loose = _extract_summary_field_loose(raw)
    return loose or ''
def _step5_summary_system_message(*, strict_json=False, for_gemini=False):
    base = (
        'Anda merangkum SATU coffee shop dari ulasan pelanggan untuk modal rekomendasi, '
        'dengan gaya rekomendasi santai dari teman — bukan laporan formal/baku. '
        'Sudut pandang orang ketiga; jangan menyalin kata saya/aku/kami. '
        f'Satu paragraf {COFIND_SUMMARY_MIN_SENTENCES}-4 kalimat ringkas, hanya fakta dari '
        'data kutipan, dan WAJIB selesai dengan tanda baca penutup (lebih baik 3 kalimat '
        'tuntas daripada 4 kalimat terpotong). '
        'Selipkan secara natural (bukan copy label) apakah kebutuhan user didukung ulasan '
        'toko ini atau belum, sesuai blok cakupan kebutuhan di data user. '
    )
    if for_gemini or strict_json:
        base += (
            f'Field JSON "summary" WAJIB berisi minimal {COFIND_SUMMARY_MIN_SENTENCES} kalimat '
            f'dan sekitar {COFIND_SUMMARY_MIN_CHARS}+ karakter, paragraf utuh Bahasa Indonesia. '
            'Tanpa markdown, tanpa code fence, tanpa teks di luar JSON. '
        )
    if strict_json:
        base += 'Respons sebelumnya ditolak karena terlalu pendek atau generik — perbaiki sekarang. '
    base += 'Jawab hanya JSON {"summary":"..."}.'
    return base
def _log_summary_llm_response(shop_name, raw, *, usage=None, label=''):
    """Log ringkas respons summary (tanpa dump penuh ke prod verbose)."""
    if not (COFIND_SUMMARY_DEBUG_LOG or COFIND_RECOMMEND_VERBOSE):
        return
    finish = get_last_llm_finish_reason()
    usage_bits = ''
    if usage:
        usage_bits = (
            f" completion_tokens={usage.get('completion_tokens', 0)}"
            f" total_tokens={usage.get('total_tokens', 0)}"
        )
    preview = re.sub(r'\s+', ' ', str(raw or '')).strip()[:220]
    tag = f" {label}" if label else ''
    LOG_RECOMMEND.info(
        f"Summary debug{tag} {shop_name}: finish_reason={finish!r}{usage_bits} "
        f"raw_chars={len(str(raw or ''))} preview={preview!r}"
    )
def _summary_llm_call_kwargs(
    *, strict_json=False, quality_boost=False, prefer_gemini=False,
):
    use_gemini = prefer_gemini or quality_boost or _summary_use_gemini(None)
    max_tokens = (
        COFIND_SUMMARY_GEMINI_MAX_TOKENS if use_gemini else COFIND_SUMMARY_MAX_TOKENS
    )
    temperature = 0.1 if (strict_json or use_gemini) else 0.2
    kwargs = {
        'max_tokens': max_tokens,
        'temperature': temperature,
        'usage_stage': 'summary_retry' if strict_json else 'summary',
    }
    if use_gemini:
        kwargs['model'] = None
        kwargs['prefer_provider'] = 'gemini'
    else:
        kwargs['model'] = _llm_model_id()
        kwargs['prefer_provider'] = None
    return kwargs
def _summary_user_prompt_for_shop(
    shop,
    pills,
    search_keywords,
    intent_line,
    *,
    prefer_gemini,
    reject_reason=None,
    summary_framing=None,
):
    """User prompt Step 5; untuk Gemini sudah strict sejak panggilan pertama."""
    prompt = _single_shop_summary_prompt(
        shop,
        pills,
        search_keywords,
        intent_line,
        quality_boost=prefer_gemini,
        prefer_gemini=prefer_gemini,
        summary_framing=summary_framing,
    )
    if prefer_gemini:
        prompt += (
            f"\n\n{_summary_output_requirements_block(strict=True)}\n"
            f'Field "summary" WAJIB ≥{COFIND_SUMMARY_MIN_CHARS} karakter dan '
            f'{COFIND_SUMMARY_MIN_SENTENCES}+ kalimat sebelum mengirim JSON.'
        )
    if reject_reason:
        prompt += (
            f"\n\nRespons ditolak: {reject_reason}. "
            f'Tulis ulang JSON dengan paragraf lengkap.'
        )
    return prompt
def _llm_summary_for_one_shop(
    shop,
    pills,
    search_keywords,
    intent_line,
    all_shops,
    summary_route_mode=None,
    summary_framing=None,
):
    """Satu panggilan LLM untuk satu toko. Kembalikan teks summary atau None."""
    prefer_gemini = _summary_use_gemini(summary_route_mode)
    gemini_single_shot = prefer_gemini and COFIND_SUMMARY_GEMINI_SINGLE_SHOT
    prompt = _summary_user_prompt_for_shop(
        shop,
        pills,
        search_keywords,
        intent_line,
        prefer_gemini=prefer_gemini,
        summary_framing=summary_framing,
    )
    LOG_RECOMMEND.info(
        f"Summary: kirim {shop.get('name')} "
        f"(prompt_chars={len(prompt)}, gemini_route={prefer_gemini}, "
        f"single_shot={gemini_single_shot}, route_mode={summary_route_mode})...")
    t0 = time.perf_counter()
    try:
        call_kw = _summary_llm_call_kwargs(
            strict_json=prefer_gemini,
            quality_boost=prefer_gemini,
            prefer_gemini=prefer_gemini,
        )
        if prefer_gemini:
            call_kw['usage_stage'] = 'summary'
        raw, usage = llm_chat_completions_create_with_usage(
            messages=[
                {
                    'role': 'system',
                    'content': _step5_summary_system_message(
                        strict_json=False,
                        for_gemini=prefer_gemini,
                    ),
                },
                {'role': 'user', 'content': prompt},
            ],
            **call_kw,
        )
        LOG_RECOMMEND.info(
            f"Summary: {shop.get('name')} siap "
            f"({round((time.perf_counter() - t0) * 1000, 1)} ms, "
            f"raw_chars={len(str(raw or ''))})")
        _log_summary_llm_response(shop.get('name'), raw, usage=usage, label='initial')
        summary = _coerce_step5_summary_text(raw, shop)
        reason = _invalid_llm_summary_reason(summary, shop, all_shops)
        if not summary and raw:
            LOG_RECOMMEND.info(
                f"Summary parse kosong untuk {shop.get('name')} "
                f"(coerce gagal, cek preview di Summary debug)")
        if gemini_single_shot:
            max_gemini_retries = 0
        elif prefer_gemini and COFIND_SUMMARY_GEMINI_RETRY:
            max_gemini_retries = 2
        elif COFIND_SUMMARY_GEMINI_RETRY:
            max_gemini_retries = 1
        else:
            max_gemini_retries = 0
        attempt = 0
        # Retry (jika budget tersisa) terlepas dari provider awal — sebelumnya
        # kondisi ini mensyaratkan panggilan awal sudah lewat Gemini, sehingga
        # ringkasan HF yang terpotong/invalid tidak pernah di-retry dan selalu
        # jatuh ke fallback deterministik. Retry selalu mengarah ke Gemini
        # (budget token lebih besar) supaya kasus "kehabisan token" di tengah
        # kalimat tidak terulang.
        while reason and attempt < max_gemini_retries:
            attempt += 1
            LOG_RECOMMEND.info(
                f"Summary retry Gemini #{attempt} untuk {shop.get('name')}: {reason}")
            retry_prompt = _summary_user_prompt_for_shop(
                shop,
                pills,
                search_keywords,
                intent_line,
                prefer_gemini=True,
                reject_reason=reason,
                summary_framing=summary_framing,
            )
            retry_kw = _summary_llm_call_kwargs(
                strict_json=True,
                quality_boost=True,
                prefer_gemini=True,
            )
            raw_retry, usage_retry = llm_chat_completions_create_with_usage(
                messages=[
                    {
                        'role': 'system',
                        'content': _step5_summary_system_message(
                            strict_json=True,
                            for_gemini=True,
                        ),
                    },
                    {'role': 'user', 'content': retry_prompt},
                ],
                **retry_kw,
            )
            _log_summary_llm_response(
                shop.get('name'),
                raw_retry,
                usage=usage_retry,
                label=f'retry{attempt}',
            )
            summary = _coerce_step5_summary_text(raw_retry, shop)
            reason = _invalid_llm_summary_reason(summary, shop, all_shops)
        if reason:
            LOG_RECOMMEND.warning(
                f"Summary ditolak untuk {shop.get('name')}: {reason}")
            return None
        return summary
    except Exception as e:
        LOG_RECOMMEND.warning(
            f"Summary error {shop.get('name')}: {e}")
        return None
def _llm_summaries_for_shops(
    top_shops,
    pills,
    search_keywords=None,
    user_intent_line=None,
    summary_framing=None,
):
    """
    Ringkasan per toko: SATU panggilan LLM per toko, dijalankan paralel.

    Satu toko per prompt menghapus risiko model mencampur nama/fakta antar
    kandidat. Validasi grounding (_invalid_llm_summary_reason) tetap di pemanggil.
    """
    empty_stats = {'summary_llm_count': 0, 'summary_fallback_count': 0}
    if not top_shops:
        return {}, empty_stats

    activity_pills, attribute_pills = _split_preference_pills(pills)
    activity_labels = [PILL_LABELS.get(p, p) for p in activity_pills]
    attribute_labels = [PILL_LABELS.get(p, p) for p in attribute_pills]
    if activity_labels and attribute_labels:
        intent_line = (
            ", ".join(activity_labels)
            + " (fasilitas tambahan, hanya jika ada bukti: "
            + ", ".join(attribute_labels)
            + ")"
        )
    else:
        pill_labels = [PILL_LABELS.get(p, p) for p in pills]
        intent_line = ", ".join(pill_labels) if pill_labels else "preferensi umum"
    if user_intent_line:
        intent_line = str(user_intent_line).strip() or intent_line
    search_keywords = _light_keyword_phrase_list(search_keywords or [])

    if not _llm_ready_for_recommend_run():
        if COFIND_DEV_LLM_STRICT:
            raise RuntimeError('LLM strict mode aktif: summary butuh LLM tersedia.')
        LOG_RECOMMEND.warning("Summary: LLM tidak tersedia, pakai fallback deterministik")
        n = len(top_shops)
        return {
            s['place_id']: _build_review_summary_deterministic(
                s, pills,
                search_keywords=search_keywords,
                user_intent_line=user_intent_line,
            )
            for s in top_shops
        }, {'summary_llm_count': 0, 'summary_fallback_count': n}

    route = get_llm_run_route()
    summary_route_mode = route.mode if route else None
    workers = min(3, len(top_shops))
    LOG_RECOMMEND.info(
        f"Summary: {len(top_shops)} toko, 1 panggilan/toko, "
        f"paralel={workers}, route_mode={summary_route_mode}")

    generated = {}
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                contextvars.copy_context().run,
                _llm_summary_for_one_shop,
                shop,
                pills,
                search_keywords,
                intent_line,
                top_shops,
                summary_route_mode,
                summary_framing,
            ): shop
            for shop in top_shops
        }
        for fut in as_completed(futures):
            shop = futures[fut]
            try:
                generated[shop['place_id']] = fut.result()
            except Exception as e:
                LOG_RECOMMEND.warning(
                    f"Summary future error {shop.get('name')}: {e}")
                generated[shop['place_id']] = None

    result_map = {}
    skipped = 0
    for shop in top_shops:
        summary = generated.get(shop['place_id'])
        if not summary:
            skipped += 1
            prefix = '[STRICT] ' if COFIND_DEV_LLM_STRICT else ''
            LOG_RECOMMEND.warning(
                f"{prefix}Summary fallback deterministik untuk "
                f"{shop.get('name')} ({shop.get('place_id')})")
            summary = _build_review_summary_deterministic(
                shop, pills,
                search_keywords=search_keywords,
                user_intent_line=user_intent_line,
            )
        result_map[shop['place_id']] = summary
    llm_count = len(top_shops) - skipped
    LOG_RECOMMEND.info(
        f"Summary: {llm_count} LLM / {skipped} fallback dari {len(top_shops)} toko")
    return result_map, {
        'summary_llm_count': llm_count,
        'summary_fallback_count': skipped,
    }
def _build_recommendation_progress_map(stages):
    """Peta tahap → payload progress, lengkap dengan target tahap berikutnya."""
    out = {}
    for idx, (stage, percent, label) in enumerate(stages):
        next_percent = stages[idx + 1][1] if idx + 1 < len(stages) else 100
        out[stage] = {
            'stage': stage,
            'percent': percent,
            'next_percent': next_percent,
            'label': label,
        }
    return out
def _preference_line_for_sentiment(pills):
    labels = [str(PILL_LABELS.get(p, p) or p).strip() for p in (pills or []) if p]
    return ', '.join(label for label in labels if label) or 'preferensi umum'
def _llm_ready_for_recommend_run():
    """True jika run rekomendasi boleh memanggil LLM (setelah probe route)."""
    route = get_llm_run_route()
    if route is None:
        return llm_is_available()
    return route.mode != 'off'
def _run_clause_sentiment_for_candidates(candidates, pills):
    """
    Nilai sentimen kutipan kandidat (pool kecil). Return (verdicts, telemetry).
    Kosong jika flag mati, LLM tidak tersedia, atau tidak ada kutipan.
    """
    telemetry = {'skipped': None, 'quotes': 0, 'verdicts': 0}
    if not clause_sentiment_enabled():
        telemetry['skipped'] = 'disabled'
        return {}, telemetry
    if not _llm_ready_for_recommend_run():
        telemetry['skipped'] = 'llm_unavailable'
        return {}, telemetry
    pool = list(candidates or [])[:clause_sentiment_pool()]
    quotes = []
    seen = set()
    for shop in pool:
        for text in _candidate_quotes_for_sentiment(shop.get('evidence') or {}):
            marker = clause_quote_key(text)
            if not marker or marker in seen:
                continue
            seen.add(marker)
            quotes.append(text)
    telemetry['quotes'] = len(quotes)
    if not quotes:
        telemetry['skipped'] = 'no_quotes'
        return {}, telemetry
    verdicts, sentiment_telemetry = classify_clause_quotes(
        quotes,
        preference_line=_preference_line_for_sentiment(pills),
        chat_fn=_llm_chat_for_pipeline,
        parse_json_fn=_parse_llm_json_with_repair,
    )
    telemetry.update(sentiment_telemetry or {})
    telemetry['verdicts'] = len(verdicts or {})
    return verdicts or {}, telemetry
def _candidate_quotes_for_sentiment(evidence, limit=_SENTIMENT_QUOTES_PER_CANDIDATE):
    """Kutipan kandidat yang perlu diverifikasi sentimennya oleh LLM."""
    ordered_keys = (
        'review_quotes',
        'search_keyword_matches',
        'semantic_matches',
        'positive_review_quotes',
        'negative_review_quotes',
    )
    quotes = []
    seen = set()
    for key in ordered_keys:
        for row in (evidence or {}).get(key) or []:
            if len(quotes) >= limit:
                return quotes
            text = _normalize_whitespace((row or {}).get('quote') or '')
            if len(text) < _MIN_QUOTE_CHARS:
                continue
            marker = clause_quote_key(text)
            if marker in seen:
                continue
            seen.add(marker)
            quotes.append(text)
    return quotes
def _enrich_evidence_with_profile_context(evidence, profile):
    """Salin jam buka profil ke evidence agar prompt/coverage konsisten."""
    ev = dict(evidence or {})
    prof = profile if isinstance(profile, dict) else {}
    hours = str(prof.get('opening_hours_display') or '').strip()
    if hours:
        ev['opening_hours_display'] = hours
    return ev
def _attach_pill_coverage(shop, pills):
    """Set covered/uncovered: kutipan + keyword hits + metadata + jam buka."""
    covered, uncovered = compute_pill_coverage(
        _quote_texts_for_coverage(shop),
        pills,
        pill_labels=PILL_LABELS,
        pill_mapping=PILL_MAPPING,
        activity_pills=[p for p in (pills or []) if p not in FACILITY_ATTRIBUTE_PILLS],
    )
    covered, uncovered = merge_pill_coverage(
        shop,
        pills,
        covered,
        uncovered,
        facility_attribute_pills=FACILITY_ATTRIBUTE_PILLS,
    )
    activity_pills, attribute_pills = _split_preference_pills(pills)
    covered_set = set(covered)

    def _layer_ratio(layer):
        if not layer:
            return 1.0
        return sum(1 for p in layer if p in covered_set) / len(layer)

    detail = dict(shop.get('score_detail') or {})
    detail['covered_pills'] = covered
    detail['uncovered_pills'] = uncovered
    detail['activity_pills'] = activity_pills
    detail['attribute_pills'] = attribute_pills
    detail['activity_coverage'] = round(_layer_ratio(activity_pills), 4)
    detail['attribute_coverage'] = round(_layer_ratio(attribute_pills), 4)
    shop['score_detail'] = detail
    return shop
def _iter_shop_quote_texts(shop):
    fit = shop.get('llm_fit') if isinstance(shop.get('llm_fit'), dict) else {}
    for key in ('evidence_quote', 'caveat_quote'):
        text = str(fit.get(key) or '').strip()
        if text:
            yield text
    evidence = shop.get('evidence') or {}
    for group in (
        'review_quotes',
        'modal_display_quotes',
        'modal_caveat_quotes',
        'positive_review_quotes',
        'negative_review_quotes',
    ):
        for row in evidence.get(group) or []:
            if isinstance(row, dict):
                text = str(row.get('quote') or '').strip()
            else:
                text = str(row or '').strip()
            if text:
                yield text
def _activity_support_span(text, activity_matcher=None, activity_tokens=None):
    """Klausul pendukung aktivitas; caveat keluarga di kalimat lain dibuang."""
    return extract_activity_support_text(
        text, activity_matcher, activity_tokens,
    )
def _shop_has_activity_contradiction(
    shop, activity_pills, activity_tokens, activity_matcher=None,
):
    """
    True hanya jika toko menolak aktivitas tanpa klausa pendukung.
    'Main game, keluarga kurang disarankan' tetap lolos.
    """
    has_support = False
    has_reject = False

    def _note(text):
        nonlocal has_support, has_reject
        if _activity_support_span(text, activity_matcher, activity_tokens):
            has_support = True
        if text_rejects_requested_activity(text, activity_matcher, activity_tokens):
            has_reject = True

    for text in _iter_shop_quote_texts(shop):
        _note(text)
        if has_support:
            return False
    for row in (shop.get('profile') or {}).get('reviews') or []:
        _note(review_text(row))
        if has_support:
            return False
    return has_reject and not has_support
def _supporting_quotes_without_activity_contradiction(
    quotes, activity_pills, activity_tokens, activity_matcher=None,
):
    """Sisakan klausa pendukung; jangan buang ulasan campuran utuh."""
    out = []
    for row in quotes or []:
        quote = row.get('quote') if isinstance(row, dict) else str(row or '')
        span = _activity_support_span(quote, activity_matcher, activity_tokens)
        if not span:
            if text_rejects_requested_activity(quote, activity_matcher, activity_tokens):
                continue
            if _quote_has_unsuitability_phrase(quote):
                continue
            continue
        if isinstance(row, dict):
            item = dict(row)
            item['quote'] = span
            out.append(item)
        else:
            out.append(span)
    return out
def _shop_has_activity_evidence(
    shop, activity_tokens, activity_pills=None, activity_matcher=None,
):
    activity_pills = list(activity_pills or [])

    def _usable(quote):
        text = str(quote or '')
        if _activity_support_span(text, activity_matcher, activity_tokens):
            return True
        if text_rejects_requested_activity(text, activity_matcher, activity_tokens):
            return False
        if activity_matcher and activity_matcher.get('pills'):
            return text_has_activity_signal(text, activity_matcher)
        if not activity_tokens:
            return True
        return text_matches_tokens(text, activity_tokens)

    if activity_matcher and activity_matcher.get('pills'):
        fit = shop.get('llm_fit') if isinstance(shop.get('llm_fit'), dict) else {}
        if _usable(fit.get('evidence_quote') or ''):
            return True
        evidence = shop.get('evidence') or {}
        for key in ('modal_display_quotes', 'review_quotes'):
            for row in evidence.get(key) or []:
                quote = row.get('quote') if isinstance(row, dict) else str(row or '')
                if _usable(quote):
                    return True
        reviews = (shop.get('profile') or {}).get('reviews') or []
        if shop_has_activity_signal(
            reviews, activity_tokens or [], activity_matcher=activity_matcher,
        ):
            return True
        return False
    if not activity_tokens:
        return True
    fit = shop.get('llm_fit') if isinstance(shop.get('llm_fit'), dict) else {}
    if _usable(fit.get('evidence_quote') or ''):
        return True
    evidence = shop.get('evidence') or {}
    for key in ('modal_display_quotes', 'review_quotes'):
        for row in evidence.get(key) or []:
            quote = row.get('quote') if isinstance(row, dict) else str(row or '')
            if _usable(quote):
                return True
    reviews = (shop.get('profile') or {}).get('reviews') or []
    if shop_has_activity_signal(reviews, activity_tokens or [], activity_matcher=activity_matcher):
        return True
    return False
def _activity_quote_rows(evidence, pills, activity_tokens, *, limit=3, activity_matcher=None):
    """Kutipan yang membahas aktivitas, urutan sudah dari rank_reviews_for_query."""
    pill = pills[0] if pills else ''
    rows = []
    seen = set()
    for row in (evidence or {}).get('review_quotes') or []:
        if not isinstance(row, dict):
            continue
        quote = (row.get('quote') or '').strip()
        if len(quote) < _MIN_QUOTE_CHARS:
            continue
        span = _activity_support_span(quote, activity_matcher, activity_tokens)
        if span:
            quote = span
        elif text_rejects_requested_activity(quote, activity_matcher, activity_tokens):
            continue
        elif _quote_has_unsuitability_phrase(quote):
            continue
        elif activity_matcher and activity_matcher.get('pills'):
            if not text_has_activity_signal(quote, activity_matcher):
                continue
        elif activity_tokens and not text_matches_tokens(quote, activity_tokens):
            continue
        if len(quote) < _MIN_QUOTE_CHARS:
            continue
        marker = clause_quote_key(quote)
        if not marker or marker in seen:
            continue
        seen.add(marker)
        item = dict(row)
        item['quote'] = quote
        item['pill'] = pill
        item['pill_label'] = PILL_LABELS.get(pill, pill) if pill else 'Ulasan pengunjung'
        rows.append(item)
        if len(rows) >= limit:
            break
    return rows
def _matched_terms_for_pill(text, pill):
    """Kata kunci pill yang muncul di teks ulasan."""
    terms = []
    for kw in _expand_pill_to_keywords(pill):
        if _matches_keyword_phrase(text, kw):
            terms.append(kw)
    return list(dict.fromkeys(terms))
def _tag_pill_for_review_excerpt(
    text,
    pills,
    *,
    activity_pills,
    activity_matcher=None,
):
    """Label pill + alasan untuk kutipan: fasilitas jika match keyword, else aktivitas."""
    for pill in [p for p in (pills or []) if p in FACILITY_ATTRIBUTE_PILLS]:
        terms = _matched_terms_for_pill(text, pill)
        if terms:
            return pill, ', '.join(terms[:4])
    for pill in activity_pills or []:
        if activity_matcher and activity_matcher.get('pills'):
            if text_has_activity_signal(text, activity_matcher):
                return pill, PILL_LABELS.get(pill, pill).lower()
        else:
            tokens = build_sparse_query_tokens(
                [pill], pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING,
            )
            if text_matches_tokens(text, tokens):
                return pill, PILL_LABELS.get(pill, pill).lower()
    fallback = (activity_pills or pills or [''])[0]
    return fallback, 'ulasan relevan'
def _attribute_quotes_from_reviews(
    reviews,
    attribute_pills,
    *,
    limit_per_pill=2,
    quote_chars=400,
):
    """Kutipan fasilitas dari seluruh korpus (di luar top-N ranking aktivitas)."""
    attribute_pills = [p for p in (attribute_pills or []) if p in FACILITY_ATTRIBUTE_PILLS]
    if not attribute_pills:
        return [], []
    review_quotes = []
    keyword_matches = []
    seen = set()
    for pill in attribute_pills:
        added = 0
        for review in reviews or []:
            if not isinstance(review, dict):
                continue
            text = _normalize_whitespace(review.get('text') or '')
            if len(text) < _MIN_QUOTE_CHARS:
                continue
            terms = _matched_terms_for_pill(text, pill)
            if not terms:
                continue
            quote = _truncate_evidence_text(text, quote_chars)
            marker = clause_quote_key(quote)
            dedupe = (marker, pill)
            if not marker or dedupe in seen:
                continue
            seen.add(dedupe)
            reason = ', '.join(terms[:4])
            row = {
                'pill': pill,
                'pill_label': PILL_LABELS.get(pill, pill),
                'quote': quote,
                'reason': reason,
                'rating': review.get('rating'),
                'username': review.get('username') or review.get('full_name'),
                'matched_terms': terms[:6],
                **_review_quote_detail_fields(review),
            }
            review_quotes.append(row)
            keyword_matches.append({
                'matched_terms': terms[:6],
                'quote': quote,
                'rating': review.get('rating'),
                'username': review.get('username') or review.get('full_name'),
                **_review_quote_detail_fields(review),
            })
            added += 1
            if added >= limit_per_pill:
                break
    return review_quotes, keyword_matches
def _merge_quote_rows(*groups):
    """Gabung baris kutipan; teks sama boleh beda pill fasilitas."""
    seen = set()
    out = []
    for group in groups:
        for row in group or []:
            if not isinstance(row, dict):
                continue
            quote = str(row.get('quote') or '').strip()
            marker = clause_quote_key(quote)
            pill = str(row.get('pill') or '').strip().lower()
            dedupe = (marker, pill)
            if not marker or dedupe in seen:
                continue
            seen.add(dedupe)
            out.append(dict(row))
    return out
def _attribute_quote_rows(evidence, attribute_pills, *, limit=4):
    """Kutipan fasilitas dari evidence yang sudah dibangun."""
    attribute_pills = {p for p in (attribute_pills or []) if p in FACILITY_ATTRIBUTE_PILLS}
    if not attribute_pills:
        return []
    rows = []
    seen = set()
    for key in (
        'search_keyword_matches',
        'positive_review_quotes',
        'review_quotes',
    ):
        for item in (evidence or {}).get(key) or []:
            if not isinstance(item, dict):
                continue
            pill = str(item.get('pill') or '').strip().lower()
            if pill not in attribute_pills:
                terms = item.get('matched_terms') or []
                if not any(
                    _matches_keyword_phrase(
                        str(item.get('quote') or ''),
                        kw,
                    )
                    for p in attribute_pills
                    for kw in _expand_pill_to_keywords(p)[:12]
                ):
                    continue
            quote = str(item.get('quote') or '').strip()
            marker = clause_quote_key(quote)
            if not marker or marker in seen:
                continue
            seen.add(marker)
            rows.append(dict(item))
            if len(rows) >= limit:
                return rows
    return rows
def _build_retrieval_evidence(
    profile,
    pills,
    query_text='',
    query_tokens=None,
    activity_tokens=None,
    activity_query_text='',
    attribute_tokens=None,
    activity_matcher=None,
    activity_pills=None,
    attribute_pills=None,
):
    """
    Cuplikan review: ranking aktivitas + kutipan fasilitas dari seluruh korpus.
    """
    activity_pills = list(activity_pills or [])
    attribute_pills = list(attribute_pills or [])
    if not activity_pills and not attribute_pills:
        activity_pills, attribute_pills = _split_preference_pills(pills)
    reviews = profile.get('reviews') or []
    ranked = rank_reviews_for_query(
        reviews,
        query_text=query_text or '',
        query_tokens=query_tokens or [],
        activity_tokens=activity_tokens or [],
        activity_query_text=activity_query_text or '',
        attribute_tokens=attribute_tokens or [],
        activity_matcher=activity_matcher,
    )
    ranked_excerpts = []
    for review in ranked:
        if not isinstance(review, dict):
            continue
        text = _normalize_whitespace(review.get('text') or '')
        if len(text) < _MIN_QUOTE_CHARS:
            continue
        pill, reason = _tag_pill_for_review_excerpt(
            text,
            pills,
            activity_pills=activity_pills,
            activity_matcher=activity_matcher,
        )
        ranked_excerpts.append({
            'pill': pill,
            'pill_label': PILL_LABELS.get(pill, pill) if pill else 'Ulasan pengunjung',
            'quote': _truncate_evidence_text(text, 400),
            'reason': reason,
            'rating': review.get('rating'),
            'username': review.get('username') or review.get('full_name'),
            **_review_quote_detail_fields(review),
        })
    attr_rows, attr_keyword = _attribute_quotes_from_reviews(
        reviews,
        attribute_pills,
        limit_per_pill=2,
    )
    review_quotes = _merge_quote_rows(ranked_excerpts, attr_rows)
    search_keyword_matches = list(attr_keyword)
    ev = _build_empty_supporting_evidence()
    ev.update({
        'review_quotes': review_quotes,
        'search_keyword_matches': search_keyword_matches,
        'category_ratings': profile.get('avg_category_ratings') or ev['category_ratings'],
        'avg_user_rating': profile.get('avg_user_rating'),
        'review_count': profile.get('review_count', 0),
        'google_rating': profile.get('google_rating'),
        'google_total_reviews': profile.get('google_total_reviews'),
        'community_signals': profile.get('community_signals') or {},
        'facilities_tab': profile.get('facilities_tab') or ev['facilities_tab'],
    })
    return ev
def _apply_llm_extracted_quotes(shop, pills, activity_tokens=None, activity_matcher=None):
    """Isi kutipan tampilan: utamakan ulasan aktivitas; label sentimen LLM menang."""
    fit = shop.get('llm_fit') if isinstance(shop.get('llm_fit'), dict) else {}
    evidence = dict(shop.get('evidence') or _build_empty_supporting_evidence())
    supporting = str(fit.get('evidence_quote') or '').strip()
    caveat = str(fit.get('caveat_quote') or '').strip()
    reason = str(fit.get('reason') or '').strip() or 'cocok dengan preferensi'
    pill = pills[0] if pills else ''

    def _is_activity_quote(text):
        if _activity_support_span(text, activity_matcher, activity_tokens):
            return True
        if activity_matcher and activity_matcher.get('pills'):
            return text_has_activity_signal(text, activity_matcher)
        if activity_tokens:
            return text_matches_tokens(text, activity_tokens)
        return True

    activity_rows = _activity_quote_rows(
        evidence, pills, activity_tokens, limit=3, activity_matcher=activity_matcher,
    )
    display = []
    caveats_out = []
    seen = set()

    def _row(quote, row_reason, extra=None):
        item = {
            'pill': pill,
            'pill_label': PILL_LABELS.get(pill, pill) if pill else 'Ulasan pengunjung',
            'quote': quote,
            'reason': row_reason,
        }
        if extra:
            item.update({k: v for k, v in extra.items() if k not in item})
        return item

    def _accept(quote, row_reason, default_dest, extra=None):
        text = str(quote or '').strip()
        attr_pill = str((extra or {}).get('pill') or '').strip().lower()
        is_facility_row = attr_pill in FACILITY_ATTRIBUTE_PILLS
        if default_dest == 'supporting' and not is_facility_row:
            span = _activity_support_span(text, activity_matcher, activity_tokens)
            if span:
                text = span
            elif text_rejects_requested_activity(text, activity_matcher, activity_tokens):
                return
        if len(text) < _MIN_QUOTE_CHARS:
            return
        marker = clause_quote_key(text)
        if not marker or marker in seen:
            return
        dest = _quote_destination(text, default_dest)
        if dest is None:
            return
        seen.add(marker)
        item = _row(text, row_reason, extra)
        item['sentiment'] = dest
        if _quote_llm_label(text):
            item['sentiment_source'] = 'llm'
        if dest == 'caveat':
            caveats_out.append(item)
        else:
            display.append(item)

    if supporting and _is_activity_quote(supporting):
        _accept(supporting, reason, 'supporting')
    for row in activity_rows:
        if len(display) >= 3:
            break
        _accept(
            row.get('quote'),
            row.get('reason') or reason,
            'supporting',
            extra=row,
        )
    # Jangan fallback ke kutipan fasilitas jika aktivitas diminta.
    if not display:
        for row in _activity_quotes_from_reviews(
            shop, activity_matcher, activity_tokens, limit=3,
        ):
            _accept(
                row.get('quote'),
                row.get('reason') or reason,
                'supporting',
                extra=row,
            )
            if len(display) >= 3:
                break
    _, attribute_pills = _split_preference_pills(pills)
    if attribute_pills:
        for row in _attribute_quote_rows(evidence, attribute_pills, limit=3):
            if len(display) >= 3:
                break
            _accept(
                row.get('quote'),
                row.get('reason') or PILL_LABELS.get(row.get('pill'), 'fasilitas'),
                'supporting',
                extra=row,
            )
    if caveat:
        _accept(caveat, 'catatan dari ulasan', 'caveat')
    if display:
        evidence['modal_display_quotes'] = display[:3]
        evidence['llm_extracted'] = True
        if fit and display[0].get('quote'):
            fit = dict(fit)
            fit['evidence_quote'] = display[0]['quote']
            shop['llm_fit'] = fit
    merged_caveats = _merge_caveat_quote_rows(
        evidence.get('metadata_contradiction_quotes'),
        caveats_out,
        evidence.get('modal_caveat_quotes'),
        limit=2,
    )
    if merged_caveats:
        evidence['modal_caveat_quotes'] = merged_caveats
        if display or caveats_out:
            evidence['llm_extracted'] = True
    shop['evidence'] = evidence
    return shop
def _activity_quotes_from_reviews(shop, activity_matcher=None, activity_tokens=None, *, limit=3):
    """Cadangan kutipan aktivitas dari korpus ulasan, tanpa syarat fasilitas."""
    detail = shop.get('score_detail') if isinstance(shop.get('score_detail'), dict) else {}
    pills = list(detail.get('activity_pills') or [])
    pill = pills[0] if pills else ''
    rows = []
    seen = set()
    for row in (shop.get('profile') or {}).get('reviews') or []:
        span = _activity_support_span(review_text(row), activity_matcher, activity_tokens)
        if not span or len(span) < _MIN_QUOTE_CHARS:
            continue
        marker = clause_quote_key(span)
        if not marker or marker in seen:
            continue
        seen.add(marker)
        rows.append({
            'pill': pill,
            'pill_label': PILL_LABELS.get(pill, pill) if pill else 'Ulasan pengunjung',
            'quote': span,
            'reason': 'ulasan membahas aktivitas',
            'rating': row.get('rating') if isinstance(row, dict) else None,
            'username': (row.get('username') or row.get('full_name')) if isinstance(row, dict) else None,
        })
        if len(rows) >= limit:
            break
    return rows
def _shop_relevance_sort_key(shop):
    """Aktivitas dulu, lalu fasilitas sebagai penguat, lalu skor campuran."""
    detail = shop.get('score_detail') if isinstance(shop.get('score_detail'), dict) else {}
    final = float(shop.get('final_score') or shop.get('score') or 0.0)
    act = float(detail.get('activity_combo') or detail.get('activity_lex') or 0.0)
    attr = float(detail.get('attribute_bm25') or 0.0)
    attr_cov = float(detail.get('attribute_coverage') or 0.0)
    act_hits = int(detail.get('activity_hits') or 0)
    return (-final, -attr_cov, -attr, -act, -act_hits)
def _select_top_shops(
    ranked_candidates,
    max_rec=3,
    activity_tokens=None,
    activity_pills=None,
    activity_matcher=None,
):
    """
    Ambil toko yang punya bukti aktivitas. Fasilitas tambahan tidak wajib.
    Urutan: aktivitas terkuat, lalu kecocokan fasilitas, lalu skor campuran.
    """
    def _eligible(shop):
        if _shop_has_activity_contradiction(
            shop, activity_pills, activity_tokens, activity_matcher=activity_matcher,
        ):
            return False
        return _shop_has_activity_evidence(
            shop, activity_tokens,
            activity_pills=activity_pills,
            activity_matcher=activity_matcher,
        )

    picked = [shop for shop in (ranked_candidates or []) if _eligible(shop)]
    if ranked_candidates and not picked:
        for shop in ranked_candidates:
            fit = shop.get('llm_fit') if isinstance(shop.get('llm_fit'), dict) else {}
            LOG_RECOMMEND.info(
                f"Fase 3 skip {shop.get('name')}: selected={fit.get('selected')} "
                f"fit={fit.get('fit_score')} quote={(fit.get('evidence_quote') or '')[:80]}"
            )
    picked.sort(key=_shop_relevance_sort_key)
    return picked[:max_rec]


def _sse_pack(event, payload):
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
def _recommendation_summary_pill_key(pills):
    return '+'.join(sorted(str(p).strip().lower() for p in (pills or []) if str(p).strip()))
def _recommendation_summary_keyword_digest(search_keywords):
    """Hash stabil dari keyword intent (token query retrieval)."""
    terms = _light_keyword_phrase_list(search_keywords or [])
    if not terms:
        return ''
    blob = '\n'.join(sorted(terms))
    return hashlib.sha1(blob.encode('utf-8')).hexdigest()[:12]
def _preference_definition_digest(pills):
    """Hash pendek dari definition + negative_scope preferensi terpilih."""
    parts = []
    for pill in sorted({str(p).strip().lower() for p in (pills or []) if str(p).strip()}):
        spec = PILL_MAPPING.get(pill) or {}
        definition = ' '.join(str(spec.get('definition') or '').split())
        negative_scope = ' '.join(str(spec.get('negative_scope') or '').split())
        parts.append(f'{pill}|{definition}|{negative_scope}')
    blob = '\n'.join(parts)
    return hashlib.md5(blob.encode('utf-8')).hexdigest()[:12]
def rerank_cache_enabled():
    raw = (os.getenv('COFIND_LLM_RERANK_CACHE') or '').strip().lower()
    if not raw:
        return True
    return raw in ('1', 'true', 'yes', 'on')
def _load_rerank_cache():
    if os.path.exists(RERANK_CACHE_PATH):
        try:
            with open(RERANK_CACHE_PATH, 'r', encoding='utf-8') as f:
                cache = json.load(f)
                return cache if isinstance(cache, dict) else {}
        except Exception:
            return {}
    return {}
def _save_rerank_cache(cache):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(RERANK_CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        LOG_CACHE.warning(f"Error saving rerank cache: {e}")
def _rerank_candidate_fingerprint(candidates):
    """
    Sidik jari kandidat: place_id BESERTA jumlah ulasannya.

    Konsekuensinya disengaja: satu ulasan baru pada salah satu kandidat mengubah
    sidik jari, jadi penilaian dihitung ulang dan ulasan baru itu ikut
    diperhitungkan — cache tidak pernah menyembunyikan ulasan terbaru. Diurutkan
    supaya urutan skor hybrid tidak ikut jadi bagian kunci.
    """
    parts = []
    for candidate in candidates or []:
        place_id = str(candidate.get('place_id') or '').strip()
        reviews = ((candidate.get('profile') or {}).get('reviews') or [])
        parts.append(f"{place_id}:{len(reviews)}")
    return '|'.join(sorted(parts))
def _rerank_cache_key(candidates, pills, user_id=None, search_keywords=None):
    """
    Kunci cache rerank: kombinasi pill + hash definisi + user + sidik jari kandidat.

    Hash definisi membuat cache otomatis usang jika definition/negative_scope
    di PILL_MAPPING berubah. user_id wajib masuk kunci karena prompt rerank
    memuat konteks selera user (review sendiri + favorit). Tanpa itu, user
    kedua dengan pill sama akan memakai penilaian yang dipersonalisasi untuk
    user pertama.
    """
    blob = '\u241f'.join([
        _recommendation_summary_pill_key(pills),
        _preference_definition_digest(pills),
        _recommendation_summary_keyword_digest(search_keywords),
        str(user_id or 'anon'),
        _rerank_candidate_fingerprint(candidates),
    ])
    return hashlib.sha1(blob.encode('utf-8')).hexdigest()
def _get_cached_rerank_fits(candidates, pills, user_id=None, search_keywords=None):
    """Penilaian LLM per place_id dari cache, atau None bila tidak ada/kedaluwarsa."""
    if not rerank_cache_enabled():
        return None
    try:
        cache = _load_rerank_cache()
    except Exception:
        return None
    entry = cache.get(_rerank_cache_key(candidates, pills, user_id, search_keywords))
    if not isinstance(entry, dict):
        return None
    if entry.get('version') != RERANK_CACHE_VERSION:
        return None
    if (time.time() - entry.get('timestamp', 0)) / (60 * 60 * 24) > RERANK_CACHE_EXPIRY_DAYS:
        return None
    fits = entry.get('fits')
    return fits if isinstance(fits, dict) and fits else None
def _store_rerank_fits(candidates, pills, fits, user_id=None, search_keywords=None):
    if not fits or not rerank_cache_enabled():
        return
    try:
        cache = _load_rerank_cache()
    except Exception:
        cache = {}
    if not isinstance(cache, dict):
        cache = {}
    cache[_rerank_cache_key(candidates, pills, user_id, search_keywords)] = {
        'version': RERANK_CACHE_VERSION,
        'timestamp': time.time(),
        'pills': sorted(str(p).strip().lower() for p in (pills or []) if str(p).strip()),
        'user_id': str(user_id or 'anon'),
        'fits': fits,
    }
    try:
        _save_rerank_cache(cache)
    except Exception as e:
        LOG_CACHE.warning(f"Error storing rerank fits: {e}")


_RECOMMENDATION_PROGRESS_STAGES = (
    ('start', 6, 'Memahami konteks Anda'),
    ('profiles', 22, 'Mengumpulkan ulasan pengunjung'),
    ('scoring', 48, 'Mencari tempat yang relevan'),
    ('rerank', 72, 'Memilih yang paling cocok'),
    ('summary', 88, 'Menyusun rekomendasi untuk Anda'),
    ('done', 100, 'Rekomendasi siap'),
)
_RECOMMENDATION_PROGRESS_BY_STAGE = _build_recommendation_progress_map(
    _RECOMMENDATION_PROGRESS_STAGES,
)

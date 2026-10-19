from dotenv import load_dotenv

# Wajib sebelum import llm_backend: variabel HF_* dibaca saat modul dimuat.
load_dotenv()

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS
import os
import json
import re
import contextvars
import hashlib
import importlib
import time

try:
    repair_json = importlib.import_module('json_repair').repair_json
except Exception:
    repair_json = None

from llm_backend import (
    GEMINI_SUMMARY_MAX_TOKENS,
    HF_MODEL,
    LLM_BACKEND,
    get_last_llm_finish_reason,
    get_last_llm_provider,
    get_llm_run_route,
    begin_llm_run_route,
    llm_chat_completions_create,
    llm_chat_completions_create_with_usage,
    llm_is_available,
    probe_llm_for_recommendation_run,
    reset_llm_run_route,
)
from review_utils import get_reviews_for_recommendation_batch
from vote_utils import migrate_review_ratings_to_votes, get_vote_summaries_batch
from recommendation_feedback_utils import (
    ensure_recommendation_feedback_table,
    upsert_recommendation_feedback,
    get_user_feedback_map,
    get_feedback_evaluation_summary,
    preferences_key_from_pills,
)
from pipeline_telemetry import (
    begin_llm_usage_collection,
    build_degradation_snapshot,
    fetch_pipeline_dashboard_stats,
    full_pipeline_config,
    log_recommendation_run_json,
    new_pipeline_run_id,
    record_pipeline_run,
    reset_llm_usage_collection,
    summarize_llm_usage,
)
from slang_normalize import normalize_text_with_slang, tokenize_normalized
from hybrid_retrieval import (
    retrieve_top_k,
    retrieve_top_k_by_text,
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
from free_text_intent import (
    MAX_FREE_TEXT_CHARS as FREE_TEXT_MAX_CHARS,
    extract_search_intent,
)
from recommendation_coverage import (
    merge_pill_coverage,
    supplemental_coverage_lines,
)
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
from api import register_blueprints
from auth_guards import require_authenticated_user
from facilities_store import load_facilities_index
from logging_config import configure_logging, get_logger
from cache_paths import CACHE_DIR, RERANK_CACHE_EXPIRY_DAYS

configure_logging()
LOG_STARTUP = get_logger('startup')
LOG_API = get_logger('api')
LOG_RECOMMEND = get_logger('recommend')
LOG_METRIC = get_logger('metric')
LOG_CACHE = get_logger('cache')

# Initialize Flask app
app = Flask(__name__)

# Endpoint per area (coffee shop, auth, review, favorit, vote, want-to-visit, admin)
# didefinisikan sebagai blueprint di paket api/. Endpoint rekomendasi & analisis
# review tetap di modul ini karena melekat pada pipeline LLM di bawah.
register_blueprints(app)

# Database: lihat db_backend.py (Supabase Postgres via DATABASE_URL / SUPABASE_DB_URL)
# Rerank: LLM menilai kandidat teratas hasil hybrid retrieval (lihat llm_recommender.py).
COFIND_RERANK_BACKEND = 'llm' if llm_rerank_enabled() else 'none'
COFIND_DEV_LLM_STRICT = os.getenv('COFIND_DEV_LLM_STRICT', 'false').strip().lower() in ('1', 'true', 'yes', 'on')
# Modal quote summary: default deterministik (tanpa LLM per toko). Set true untuk LLM.
COFIND_MODAL_QUOTE_LLM = os.getenv('COFIND_MODAL_QUOTE_LLM', 'false').strip().lower() in ('1', 'true', 'yes', 'on')
COFIND_SUMMARY_MIN_CHARS = max(
    40,
    int(os.getenv('COFIND_SUMMARY_MIN_CHARS', '120') or '120'),
)
COFIND_SUMMARY_MIN_SENTENCES = 2
COFIND_SUMMARY_GEMINI_RETRY = os.getenv(
    'COFIND_SUMMARY_GEMINI_RETRY', 'true',
).strip().lower() in ('1', 'true', 'yes', 'on')
# Gemini: single_shot=true = tanpa retry; default false + COFIND_SUMMARY_GEMINI_RETRY = hingga 2 retry
COFIND_SUMMARY_GEMINI_SINGLE_SHOT = os.getenv(
    'COFIND_SUMMARY_GEMINI_SINGLE_SHOT', 'false',
).strip().lower() in ('1', 'true', 'yes', 'on')
COFIND_SUMMARY_DEBUG_LOG = os.getenv(
    'COFIND_SUMMARY_DEBUG_LOG', 'true',
).strip().lower() in ('1', 'true', 'yes', 'on')
COFIND_SUMMARY_MAX_TOKENS = max(
    256,
    # 480 (bukan 400): instruksi cakupan kebutuhan menambah 1 klausa wajib di
    # paragraf, model kecil (HF 8B) butuh sedikit ruang ekstra agar kalimat
    # terakhir tidak terpotong sebelum tanda baca penutup.
    int(os.getenv('COFIND_SUMMARY_MAX_TOKENS', '480') or '480'),
)
COFIND_SUMMARY_GEMINI_MAX_TOKENS = max(
    COFIND_SUMMARY_MAX_TOKENS,
    int(os.getenv('GEMINI_SUMMARY_MAX_TOKENS', str(GEMINI_SUMMARY_MAX_TOKENS)) or GEMINI_SUMMARY_MAX_TOKENS),
)
COFIND_RECOMMEND_VERBOSE = os.getenv('COFIND_RECOMMEND_VERBOSE', 'false').strip().lower() in ('1', 'true', 'yes', 'on')
# Muat model embedding saat startup (thread terpisah) supaya request rekomendasi
# pertama tidak menanggung waktu load model. Default off untuk dev lokal.
COFIND_SEMANTIC_PRELOAD = os.getenv('COFIND_SEMANTIC_PRELOAD', 'false').strip().lower() in ('1', 'true', 'yes', 'on')

if COFIND_SEMANTIC_PRELOAD and semantic_gate_enabled():
    import threading

    LOG_STARTUP.info('Semantic preload: muat model embedding di background...')
    threading.Thread(
        target=semantic_model_available,
        name='cofind-semantic-preload',
        daemon=True,
    ).start()


try:
    _migrated_votes = migrate_review_ratings_to_votes()
    if _migrated_votes:
        LOG_STARTUP.info(f"Migrasi rating review -> shop_votes: {_migrated_votes} baris diperbarui/dibuat.")
except Exception as _migrate_err:
    LOG_STARTUP.warning(f"Migrasi rating review -> shop_votes gagal: {_migrate_err}")

try:
    if ensure_recommendation_feedback_table():
        LOG_STARTUP.info("Table recommendation_feedback siap.")
except Exception as _fb_err:
    LOG_STARTUP.warning(f"Inisialisasi recommendation_feedback gagal: {_fb_err}")

try:
    from db_backend import get_connection
    from google_places_sync import ensure_coffee_shop_google_columns
    from google_reviews_snapshot_import import ensure_reviews_unified_schema

    _places_conn = get_connection()
    ensure_coffee_shop_google_columns(_places_conn)
    ensure_reviews_unified_schema(_places_conn)
    _places_conn.close()
except Exception as _places_schema_err:
    LOG_STARTUP.warning(f"Inisialisasi kolom Google Places gagal: {_places_schema_err}")

# Konfigurasi LLM: lihat llm_backend.py (HF_LLM_BACKEND, HF_MODEL, HF_API_TOKEN, dll.)
LOG_STARTUP.info(f"LLM backend aktif: {LLM_BACKEND} | model={HF_MODEL}")
LOG_STARTUP.info("Database backend: postgresql (Supabase)")

# CORS: frontend Vercel + local Vite. Override lewat CORS_ORIGINS (comma-separated).
_CORS_DEFAULT_ORIGINS = (
    "https://cofind-pi.vercel.app,"
    "http://localhost:5173,"
    "http://127.0.0.1:5173,"
    "http://localhost:3000,"
    "http://127.0.0.1:3000"
)
_cors_origins_raw = (os.getenv("CORS_ORIGINS") or "".join(_CORS_DEFAULT_ORIGINS)).strip()
_CORS_ORIGINS = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()] or ["*"]
_CORS_ALLOW_HEADERS = [
    "Content-Type",
    "Authorization",
    "Cache-Control",
    "Pragma",
    "Expires",
    "If-Modified-Since",
    "If-None-Match",
    "Accept",
    "X-Requested-With",
]
_CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

CORS(
    app,
    resources={r"/api/*": {
        "origins": _CORS_ORIGINS,
        "methods": _CORS_ALLOW_METHODS,
        "allow_headers": _CORS_ALLOW_HEADERS,
        "expose_headers": ["Content-Type", "ETag"],
        "max_age": 86400,
    }},
    supports_credentials=False,
)


@app.after_request
def add_cors_headers_to_response(response):
    """Pastikan semua response /api/* (termasuk 4xx/5xx & preflight) punya CORS headers."""
    if not request.path.startswith("/api/"):
        return response

    origin = request.headers.get("Origin")
    if origin and ("*" in _CORS_ORIGINS or origin in _CORS_ORIGINS):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    elif "*" in _CORS_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = "*"
    elif _CORS_ORIGINS:
        # Fallback: izinkan origin pertama yang dikonfigurasi
        response.headers["Access-Control-Allow-Origin"] = _CORS_ORIGINS[0]

    response.headers["Access-Control-Allow-Methods"] = ", ".join(_CORS_ALLOW_METHODS)
    # Echo requested headers jika ada (preflight), plus daftar default
    requested = request.headers.get("Access-Control-Request-Headers")
    if requested:
        allowed = {h.strip().lower() for h in _CORS_ALLOW_HEADERS}
        extra = [h.strip() for h in requested.split(",") if h.strip().lower() in allowed]
        response.headers["Access-Control-Allow-Headers"] = ", ".join(
            dict.fromkeys(_CORS_ALLOW_HEADERS + extra)
        )
    else:
        response.headers["Access-Control-Allow-Headers"] = ", ".join(_CORS_ALLOW_HEADERS)
    response.headers["Access-Control-Max-Age"] = "86400"
    return response



# ============================================================================
# COFFEE SHOPS API ENDPOINTS
# ============================================================================






# ============================================================================
# AUTHENTICATION API ENDPOINTS
# ============================================================================









# ============================================================================
# ADMIN API ENDPOINTS
# ============================================================================




















































# ============================================================================
# REVIEWS API ENDPOINTS
# ============================================================================














# ============================================================================
# FAVORITES API ENDPOINTS
# ============================================================================






# ============================================================================
# SHOP VOTES API ENDPOINTS
# ============================================================================






# ============================================================================
# PROS & CONS ("What People Say") API ENDPOINTS
# ============================================================================




# ============================================================================
# WANT TO VISIT API ENDPOINTS
# ============================================================================







_FACILITY_POPULAR_FOR_LABELS = {
    'breakfast': 'sarapan',
    'lunch': 'makan siang',
    'dinner': 'makan malam',
    'brunch': 'brunch',
    'solo_dining': 'makan sendiri',
    'good_for_working_on_laptop': 'wfc / kerja laptop',
    'good_for_kids': 'ramah anak',
    'good_for_groups': 'berkelompok',
}
_FACILITY_HIGHLIGHT_LABELS = {
    'good_coffee': 'kopi enak',
    'good_desserts': 'dessert enak',
    'good_tea_selection': 'pilihan teh beragam',
    'sports': 'cocok nonton olahraga',
    'live_music': 'live music',
    'fast_service': 'layanan cepat',
    'great_cocktails': 'cocktail recommended',
}
_FACILITY_POPULAR_FOR_ORDER = [
    'breakfast', 'brunch', 'lunch', 'dinner',
    'solo_dining', 'good_for_working_on_laptop', 'good_for_groups', 'good_for_kids',
]
_FACILITY_HIGHLIGHT_ORDER = [
    'good_coffee', 'good_desserts', 'good_tea_selection', 'live_music', 'sports',
]


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


def _llm_chat_for_pipeline(*, messages, max_tokens, temperature, usage_stage=None):
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









# Helper function untuk fetch coffee shops dengan REVIEWS dari file JSON lokal


# ============================================================================
# NEW RECOMMENDATION PIPELINE - Weighted Multi-Signal Scoring + LLM Reasoning
# ============================================================================

PILL_MAPPING = {
    'belajar': {
        'label': 'Belajar',
        'definition': (
            'Aktivitas mandiri atau kelompok kecil seperti membaca buku, mengerjakan tugas, '
            'skripsi, atau belajar ujian yang menuntut suasana kondusif, tenang, dan tidak bising.'
        ),
        'negative_scope': (
            'Bukan tempat nongkrong komunal yang riuh, kafe dengan live music keras, '
            'atau tempat yang hanya cocok untuk mengobrol santai tanpa konsentrasi.'
        ),
        'facility_fields': {
            'popular_for': ['good_for_working_on_laptop'],
            'amenities': ['wifi', 'free_wifi'],
            'crowd': ['mahasiswa'],
        },
        'review_keywords': [
            'belajar', 'tugas', 'nugas', 'ngerjain tugas', 'kuliah', 'kampus', 'ujian',
            'skripsi', 'buku', 'baca buku', 'fokus belajar', 'ruang belajar', 'temen belajar',
            'anak kuliahan', 'mahasiswa', 'tugas sekolah',
        ],
    },
    'kerja': {
        'label': 'Kerja/WFC',
        'definition': (
            'Aktivitas kerja jarak jauh (work from cafe/remote/WFA), produktif dengan laptop '
            'dalam durasi lama, rapat daring, atau menyelesaikan deadline profesional.'
        ),
        'negative_scope': (
            'Bukan sekadar mampir minum kopi sebentar (grab-and-go), dan bukan kunjungan santai '
            'tanpa niat kerja remote atau menyelesaikan pekerjaan.'
        ),
        'facility_fields': {
            'popular_for': ['good_for_working_on_laptop'],
            'amenities': ['wifi', 'free_wifi'],
        },
        'review_keywords': [
            # 8 teratas juga dipakai sebagai frasa acuan gerbang makna
            # (_semantic_reference_terms), jadi istilah paling representatif
            # untuk "kerja dari kafe" ditaruh di depan.
            'kerja', 'wfc', 'work from cafe', 'laptopan', 'laptop', 'wfh',
            'kerja remote', 'ngantor',
            'zoom', 'meeting online', 'video call', 'webinar', 'produktif',
            'deadline', 'presentasi', 'dokumen', 'ngerjain kerjaan', 'kerjaan kantor',
            'lembur', 'freelance', 'remote working', 'work from anywhere',
            'bisnis', 'kantor',
        ],
    },
    'bermain game': {
        'label': 'Nge-game',
        'definition': (
            'Aktivitas bermain mobile/online game bersama teman (mabar) seperti Mobile Legends, '
            'PUBG, atau turnamen game.'
        ),
        'negative_scope': (
            'Bukan kafe hening/perpustakaan yang melarang obrolan seru, dan bukan tempat yang '
            'membatasi waktu kunjungan singkat.'
        ),
        'facility_fields': {
            'popular_for': ['good_for_groups'],
        },
        'review_keywords': [
            'main game', 'gaming', 'gamer', 'game', 'ngegame', 'nge-game', 'nge game',
            'mobile legends', 'mobile legend', 'mlbb', 'main ml', 'main ML',
            'pubg', 'valorant', 'free fire', 'main ff', 'honor of kings',
            'mabar', 'ngemabar', 'gas game', 'turnamen', 'push rank', 'ngerank',
            'bermain game', 'mainbareng', 'playstation', 'ps5', 'esport',
        ],
    },
    'meeting_sosialisasi': {
        'label': 'Meeting/Pertemuan',
        'definition': (
            'Pertemuan terencana kelompok seperti rapat kerja formal, diskusi tim/komunitas, '
            'arisan, presentasi bisnis, atau sesi jejaring yang membutuhkan tata ruang meja '
            'yang memadai untuk banyak orang.'
        ),
        'negative_scope': (
            'Bukan nongkrong santai perorangan, dan bukan tempat dengan kapasitas tempat duduk '
            'sangat sempit untuk kelompok.'
        ),
        'facility_fields': {
            'popular_for': ['good_for_groups'],
            'crowd': ['berkelompok'],
        },
        # Hindari kata longgar seperti "kumpul"/"grup": "berkumpul dengan keluarga"
        # bukan bukti meeting. Pakai frasa pertemuan/rapat yang lebih spesifik.
        'review_keywords': [
            'meeting', 'rapat', 'diskusi', 'arisan', 'sosialisasi', 'networking',
            'catch up', 'untuk meeting', 'buat rapat', 'untuk rapat',
            'pertemuan bisnis', 'pertemuan kerja', 'meeting kantor',
            'kumpul kerja', 'kumpul kantor', 'kumpul tim',
        ],
    },
    'keluarga': {
        'label': 'Keluarga',
        'definition': (
            'Kunjungan santai bersama anggota keluarga lintas usia (anak-anak, orang tua) '
            'yang membutuhkan tempat makan dan minum yang aman untuk anak, nyaman, dan ramah keluarga.'
        ),
        'negative_scope': (
            'Bukan area bar/lounge yang tidak ramah anak, dan bukan tempat sempit yang berbahaya '
            'bagi anak kecil dan orang tua.'
        ),
        'facility_fields': {
            'children': ['good_for_kids', 'kids_menu', 'high_chairs'],
            'popular_for': ['good_for_groups'],
            'crowd': ['keluarga', 'ramah_keluarga', 'berkelompok'],
        },
        'review_keywords': [
            'keluarga', 'family', 'anak-anak', 'ramah keluarga',
            'cocok keluarga', 'bawa anak kecil', 'family friendly',
            'berkumpul bersama', 'kumpul bersama', 'quality time',
            'ramah anak', 'playground', 'area bermain', 'kursi bayi', 'menu anak',
        ],
    },
    'instagrammable': {
        'label': 'Instagrammable',
        'definition': (
            'Kunjungan untuk berswafoto, konten visual, atau menikmati estetika interior dan '
            'arsitektur tempat yang unik, artistik, trendi, dan memiliki pencahayaan menarik.'
        ),
        'negative_scope': (
            'Bukan tempat dengan visual kumuh, pencahayaan gelap/suram tanpa konsep estetik, '
            'atau kafe ruko polos tanpa elemen dekoratif visual.'
        ),
        'facility_fields': {
            'atmosphere': ['trendi', 'artistic'],
        },
        'review_keywords': [
            'instagrammable', 'instagramable', 'instagenic', 'fotogenik',
            'spot foto', 'photo spot', 'banyak spot foto', 'estetik',
        ],
    },
    # --- Preferensi lapis 2: atribut fasilitas ---------------------------------
    # Struktur identik dengan pill aktivitas, jadi seluruh pipeline (BM25,
    # evidence, rerank) otomatis mengenalinya tanpa cabang khusus.
    'ruangan_ac': {
        'facility_fields': {
            'atmosphere': ['nyaman', 'sejuk'],
        },
        'review_keywords': [
            # "dingin"/"adem" sengaja tidak berdiri sendiri: "kopi dingin" / "tempatnya adem"
            # bukan bukti ruangan ber-AC.
            'ac', 'ber ac', 'ruangan ac', 'sejuk', 'indoor ac',
            'ac dingin', 'ruangan dingin', 'ruangan sejuk', 'udara dingin',
        ],
    },
    'suasana_tenang': {
        'facility_fields': {
            'atmosphere': ['tenang', 'santai'],
        },
        'review_keywords': [
            'tenang', 'sepi', 'sunyi', 'hening', 'tidak berisik', 'ga berisik',
            'nggak ribut', 'suasana tenang', 'kondusif', 'damai',
        ],
    },
    'area_outdoor': {
        'facility_fields': {
            'service_options': ['outdoor_seating'],
        },
        'review_keywords': [
            'outdoor', 'area outdoor', 'outdoor seating', 'tempat outdoor',
            'area terbuka', 'tempat terbuka', 'teras outdoor', 'taman outdoor',
            'duduk di luar', 'kursi outdoor', 'al fresco',
            'di luar ruangan', 'lesehan outdoor', 'rooftop', 'open space',
            'taman',
        ],
    },
    'smoking_area': {
        'facility_fields': {
            'amenities': ['smoking_area'],
        },
        'review_keywords': [
            'smoking area', 'area smoking', 'area merokok', 'tempat merokok',
            'bisa merokok', 'boleh merokok', 'ruang merokok', 'smoking room',
            'kawasan merokok',
        ],
    },
    'wifi_kencang': {
        'facility_fields': {
            'amenities': ['wifi', 'free_wifi'],
        },
        'review_keywords': [
            'wifi', 'wifi kencang', 'wifi cepat', 'wifi lancar', 'wifi stabil',
            'internet cepat', 'internet lancar', 'koneksi stabil', 'sinyal kuat',
            'jaringan lancar', 'kecepatan internet',
        ],
    },
    'banyak_colokan_terminal': {
        'facility_fields': {
            'popular_for': ['good_for_working_on_laptop'],
        },
        'review_keywords': [
            'colokan', 'stop kontak', 'terminal listrik', 'banyak colokan',
            'colokan di tiap meja', 'charge laptop', 'ngecas', 'charging',
            'power outlet',
        ],
    },
    'ruang_privat': {
        'facility_fields': {
            'offerings': ['private_dining_room'],
            'planning': ['accepts_reservations'],
        },
        'review_keywords': [
            'ruang privat', 'private room', 'ruang meeting', 'meeting room',
            'ruangan tertutup', 'vip room', 'ruang khusus', 'ruang diskusi',
            'bisa reservasi ruangan',
        ],
    },
    'buka_sampai_malam_24_hours': {
        'facility_fields': {
            'offerings': ['late_night_food'],
        },
        'review_keywords': [
            '24 jam', '24 hours', 'buka 24 jam', 'open 24 hours', 'operasional 24 jam',
            'buka sepanjang hari', 'buka nonstop', '24/7', 'buka 24/7',
            'never close', 'tutup never', 'jam operasional 24 jam',
        ],
    },
    'musholla': {
        'facility_fields': {
            'amenities': ['musholla', 'prayer_room'],
        },
        'review_keywords': [
            'musholla', 'mushola', 'musola', 'tempat sholat', 'tempat solat',
            'ruang sholat', 'bisa sholat', 'ada mukena', 'sajadah',
        ],
    },
    'parkir_luas': {
        'facility_fields': {
            'parking': ['lots_of_parking', 'parking_available', 'paid_parking_lot'],
        },
        'review_keywords': [
            'parkir', 'parkiran', 'parkir luas', 'parkir lega', 'lahan parkir',
            'parkir mudah', 'tempat parkir', 'parkir motor', 'parkir mobil',
        ],
    },
    'toilet_bersih': {
        'facility_fields': {
            'amenities': ['toilet', 'gender_neutral_toilet'],
        },
        'review_keywords': [
            'toilet', 'toilet bersih', 'kamar mandi', 'wc', 'restroom',
            'toiletnya wangi', 'kamar mandi bersih',
        ],
    },
    'makanan_berat': {
        # Menu lengkap = toko menyajikan makanan (bukan hanya kopi/minuman).
        # Sinyal utama ada di popular_for / dining_options (breakfast|brunch|
        # lunch|dinner), bukan hanya offerings.restaurant.
        'facility_fields': {
            'popular_for': ['breakfast', 'brunch', 'lunch', 'dinner'],
            'dining_options': ['breakfast', 'brunch', 'lunch', 'dinner'],
            'offerings': ['restaurant'],
        },
        'review_keywords': [
            'makanan berat', 'menu makanan berat', 'nasi', 'nasi goreng',
            'makan siang', 'makan malam', 'kenyang', 'lauk', 'ayam goreng',
            'steak', 'pasta', 'rice bowl', 'soto', 'bakso', 'mie ayam',
            'menu lengkap', 'bisa makan berat', 'sarapan', 'brunch',
        ],
    },
}

# Pill lapis 2 dibedakan dari pill aktivitas hanya saat validasi input & pembatasan
# jumlah; sisanya diperlakukan sama oleh pipeline.
# Nilainya harus sama dengan FACILITY_ATTRIBUTE_GROUPS di
# frontend-cofind/src/constants/reviewPills.js.
FACILITY_ATTRIBUTE_PILLS = frozenset({
    'ruangan_ac', 'suasana_tenang', 'area_outdoor', 'smoking_area',
    'wifi_kencang', 'banyak_colokan_terminal', 'ruang_privat',
    'buka_sampai_malam_24_hours', 'musholla', 'parkir_luas', 'toilet_bersih',
    'makanan_berat',
})

# Label lapis 2: fallback jika mapping fasilitas belum punya kunci `label`.
_FACILITY_PILL_LABELS = {
    'ruangan_ac': 'Ruangan sejuk',
    'suasana_tenang': 'Suasana tenang',
    'area_outdoor': 'Outdoor area',
    'smoking_area': 'Smoking area',
    'wifi_kencang': 'Wifi kencang',
    'banyak_colokan_terminal': 'Banyak colokan / terminal',
    'ruang_privat': 'Ruang privat / meeting',
    'buka_sampai_malam_24_hours': '24 hours',
    'musholla': 'Ada musholla',
    'parkir_luas': 'Parkir luas',
    'toilet_bersih': 'Toilet bersih',
    'makanan_berat': 'Menu Lengkap (Makanan & Minuman)',
}

PILL_LABELS = {}
for _pill_key, _pill_spec in PILL_MAPPING.items():
    _spec = _pill_spec if isinstance(_pill_spec, dict) else {}
    PILL_LABELS[_pill_key] = (
        str(_spec.get('label') or '').strip()
        or _FACILITY_PILL_LABELS.get(_pill_key)
        or _pill_key
    )
for _pill_key, _pill_label in _FACILITY_PILL_LABELS.items():
    PILL_LABELS.setdefault(_pill_key, _pill_label)

RATING_VOTE_WEIGHTS = {
    'love': 1.0,
    'like': 0.75,
    'ok': 0.5,
    'dislike': 0.25,
    'hate': 0.0,
}

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


def _facilities_item_matches_intent(item_label, intent_blob_lower):
    if not item_label or not intent_blob_lower:
        return False
    blob = intent_blob_lower
    label = str(item_label).strip().lower()
    label_norm = re.sub(r'[^\w\s]', ' ', label)
    for token in label_norm.split():
        tok = token.strip()
        if len(tok) >= 3 and tok in blob:
            return True
        if len(tok) <= 2 and tok and re.search(r'\b' + re.escape(tok) + r'\b', blob):
            return True
    compact = re.sub(r'\s+', ' ', label_norm).strip()
    if len(compact) >= 5 and compact in blob:
        return True
    return False


def _facilities_tab_display_for_intent(facilities_tab, intent_blob_lower):
    """
    Jika ada label fasilitas yang overlap dengan intent user, kembalikan subset itu;
    jika tidak, kembalikan penuh (tetap sebagai konteks profil tempat).
    """
    full = facilities_tab or {}

    def _filt(items):
        if not isinstance(items, list):
            return []
        return [x for x in items if _facilities_item_matches_intent(x, intent_blob_lower)]

    if not (intent_blob_lower or '').strip():
        return full, False

    rel = {
        'popular_for': _filt(full.get('popular_for')),
        'highlights': _filt(full.get('highlights')),
        'atmosphere': _filt(full.get('atmosphere')),
    }
    if any(rel.get(k) for k in ('popular_for', 'highlights', 'atmosphere')):
        return rel, True
    return full, False


def _build_facilities_evidence_summary(display_tab, intent_aligned):
    """Kalimat bukti berbasis tab fasilitas (popular_for, atmosphere, highlights)."""
    pop = list(display_tab.get('popular_for') or [])
    atm = list(display_tab.get('atmosphere') or [])
    hi = list(display_tab.get('highlights') or [])
    if not (pop or atm or hi):
        return ''
    parts = []
    if pop:
        parts.append(f"terkenal dengan {', '.join(pop[:6])}")
    if atm:
        parts.append(f"memiliki suasana {', '.join(atm[:6])}")
    if hi:
        parts.append(f"memiliki keunggulan {', '.join(hi[:6])}")
    if len(parts) == 1:
        body = parts[0]
    elif len(parts) == 2:
        body = f"{parts[0]} dan {parts[1]}"
    else:
        body = f"{parts[0]}, {parts[1]}, dan {parts[2]}"
    text = f"Berdasarkan tab fasilitas, coffee shop ini {body}."
    if intent_aligned:
        text += " Ini selaras dengan preferensi yang Anda masukkan."
    return text


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


# ============================================================================
# REVIEW-ONLY RECOMMENDATION PIPELINE
# ----------------------------------------------------------------------------
# Semua ranking, evidence, dan summary rekomendasi dibangun dari review
# user di tabel `reviews`. Data facilities.json hanya prior/penguat lemah
# (bisa self-claim owner) dan dipotong jika ulasan menentang klaim itu.
# Rating Google hanya untuk fallback tampilan nama/rating.
# ============================================================================

# Pemetaan pill -> kategori rating review (makanan/layanan/suasana) sebagai
# sinyal tambahan. Tidak semua pill punya kategori rating yang cocok.
PILL_TO_REVIEW_CATEGORY = {
    'belajar': 'rating_suasana',
    'kerja': 'rating_suasana',
    'bermain game': 'rating_suasana',
    'meeting_sosialisasi': 'rating_suasana',
    'keluarga': 'rating_suasana',
    'instagrammable': 'rating_suasana',
}

# Batas minimal review agar sebuah toko ikut ranking berbasis review.
REVIEW_BASED_MIN_REVIEWS = 1


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


_MANUAL_UNCLEAR_MESSAGE = (
    'Belum ada coffee shop yang cukup relevan dengan konteks yang dipilih. '
    'Coba pilih kombinasi konteks lain.'
)


def _normalize_keyword_phrase(value):
    """Normalisasi + slang map (bgt→banget, jgn→jangan, dll.) untuk matching."""
    return normalize_text_with_slang(value)


# Imbuhan Indonesia yang boleh menempel pada kata kunci (anaknya, ngegame, berkeluarga).
# Bukan substring bebas: "anak" di dalam "pontianak" atau "story" di dalam "history" tidak lolos.
_ID_AFFIX_SUFFIXES = ('nya', 'lah', 'kah', 'pun', 'ku', 'mu', 'kan', 'an', 'i')
_ID_AFFIX_PREFIXES = ('ber', 'me', 'di', 'ter', 'se', 'pe', 'per', 'ke', 'nge', 'ng')


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


# Tokens stopword sederhana untuk text-overlap.
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

# Frasa “tidak/kurang cocok untuk …” di kalimat yang sama dengan keyword preferensi
# = caveat, meski jarak token lebih jauh dari jendela kelemahan generik.
_UNSUITABILITY_PHRASES = (
    'kurang disarankan',
    'kurang direkomendasikan',
    'kurang recommended',
    'kurang cocok',
    'tidak disarankan',
    'tidak direkomendasikan',
    'tidak recommended',
    'tidak cocok',
    'ga cocok',
    'gak cocok',
    'nggak cocok',
    'enggak cocok',
    'bukan tempat yang cocok',
    'bukan untuk',
)

# Bukti pendek yang sah ("wifi ok"); di bawah ini dianggap noise.
_MIN_QUOTE_CHARS = 6

# Kata terlalu longgar untuk meeting/pertemuan (boleh tetap dipakai pill lain).
_MEETING_OVERBROAD_TERMS = frozenset({
    'kumpul', 'ngumpul', 'berkumpul', 'grup', 'group', 'acara', 'komunitas',
    'nongkrong', 'nongki', 'hangout',
})
_MEETING_OVERBROAD_KEEP_TOKENS = frozenset({
    'kerja', 'kantor', 'rapat', 'meeting', 'bisnis', 'tim', 'klien', 'client',
    'diskusi', 'profesional',
})

# Jendela ±N token dari blok keyword preferensi (pill + review_keywords) untuk
# mengaitkan fragmen kelemahan dengan konteks preferensi user.
_PREFERENCE_WEAKNESS_TOKEN_WINDOW = 6

_REVIEW_WEAKNESS_FRAGMENTS_SORTED = tuple(
    sorted(_REVIEW_WEAKNESS_FRAGMENTS, key=len, reverse=True)
)


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


def _quote_ui_extras(src):
    """Field opsional yang diwariskan ke JSON kutipan untuk UI."""
    if not isinstance(src, dict):
        return {}
    out = {}
    for k in ('review_id', 'rating_makanan', 'rating_layanan', 'rating_suasana'):
        if src.get(k) is not None:
            out[k] = src[k]
    if 'has_photos' in src:
        out['has_photos'] = bool(src['has_photos'])
    return out


def _quote_completeness_score(q):
    """Jumlah sinyal rating/foto yang terisi pada satu kutipan (untuk urutan sekunder)."""
    n = 0
    if q.get('rating') is not None and q.get('rating') != '':
        n += 1
    for k in ('rating_layanan', 'rating_suasana', 'rating_makanan'):
        if q.get(k) is not None and q.get(k) != '':
            n += 1
    if q.get('has_photos'):
        n += 1
    return n


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


# Verdict sentimen klausa dari LLM untuk request rekomendasi yang sedang berjalan.
# Disimpan di contextvar agar tidak bocor antar request/thread.
_clause_verdicts_var = contextvars.ContextVar('cofind_clause_verdicts', default=None)


def _set_clause_verdicts(verdicts):
    """Pasang verdict LLM untuk request ini; return token untuk reset."""
    return _clause_verdicts_var.set(dict(verdicts or {}))


def _reset_clause_verdicts(token):
    if token is not None:
        try:
            _clause_verdicts_var.reset(token)
        except ValueError:
            _clause_verdicts_var.set(None)


def _quote_llm_verdict(quote_text):
    """
    Verdict LLM untuk satu kutipan bila kutipan itu sudah dinilai pada request ini.
    None berarti belum dinilai, sehingga pemanggil memakai heuristik lama.
    """
    verdicts = _clause_verdicts_var.get()
    if not verdicts:
        return None
    return verdicts.get(clause_quote_key(quote_text))


def _quote_has_unsuitability_phrase(quote_text):
    """True jika kutipan secara eksplisit menolak kecocokan (kurang/tidak disarankan)."""
    normalized = _normalize_keyword_phrase(quote_text)
    if not normalized:
        return False
    return any(phrase in normalized for phrase in _UNSUITABILITY_PHRASES)


def _quote_mentions_activity(quote_text, activity_pills, activity_tokens):
    text = str(quote_text or '')
    if not text.strip():
        return False
    if activity_tokens and text_matches_tokens(text, activity_tokens):
        return True
    for pill in activity_pills or []:
        for keyword in _expand_pill_to_keywords(pill):
            if _matches_keyword_phrase(text, keyword):
                return True
    return False


def _quote_rejects_activity(quote_text, activity_pills, activity_tokens, activity_matcher=None):
    """Kontradiksi: klausa yang sama menyebut aktivitas dan menolaknya."""
    return text_rejects_requested_activity(
        quote_text, activity_matcher, activity_tokens,
    )


def _quote_llm_label(quote_text):
    """Label sentimen LLM: supporting | caveat | irrelevant, atau None bila belum dinilai."""
    verdict = _quote_llm_verdict(quote_text)
    if not isinstance(verdict, dict):
        return None
    label = str(verdict.get('label') or '').strip().lower()
    if label in ('supporting', 'caveat', 'irrelevant'):
        return label
    return None


def _quote_destination(quote_text, default):
    """
    Bucket kutipan: supporting | caveat | None (buang).
    Frasa ekstrem (kurang/tidak disarankan) selalu caveat, termasuk jika LLM
    sempat menandai supporting. Tanpa itu, verdict LLM menang.
    """
    if _quote_has_unsuitability_phrase(quote_text):
        return 'caveat'
    label = _quote_llm_label(quote_text)
    if label is None:
        return default
    if label == 'irrelevant':
        return None
    return label


def _quote_marker_key(quote_text):
    return clause_quote_key(str(quote_text or '').strip())


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


def _attach_metadata_gate_to_evidence(
    evidence,
    score_detail=None,
    metadata_gate=None,
    reviews=None,
):
    """Salin prior/penalti metadata ke evidence + caveat jika ulasan menentang klaim."""
    ev = dict(evidence or {})
    gate = metadata_gate or (score_detail or {}).get('metadata_gate')
    if not isinstance(gate, dict) and isinstance(score_detail, dict):
        gate = {
            'claimed_pills': score_detail.get('metadata_claimed_pills') or [],
            'contradicted_pills': score_detail.get('metadata_contradicted_pills') or [],
            'matched_attribute_pills': score_detail.get('metadata_matched_attribute_pills') or [],
            'matched_attribute_labels': score_detail.get('metadata_matched_attribute_labels') or [],
            'prior': score_detail.get('metadata_prior') or 0.0,
            'contradiction': score_detail.get('metadata_contradiction') or 0.0,
            'quotes': [],
        }
    gate = gate or {}
    quotes = list(gate.get('quotes') or ev.get('metadata_contradiction_quotes') or [])
    claimed = list(gate.get('claimed_pills') or [])
    contradicted = list(gate.get('contradicted_pills') or [])
    matched_pills, matched_labels = _matched_facility_from_gate(
        gate,
        score_detail,
        reviews=reviews,
    )
    ev['metadata_gate'] = {
        'claimed_pills': claimed,
        'contradicted_pills': contradicted,
        'matched_attribute_pills': matched_pills,
        'matched_attribute_labels': matched_labels,
        'prior': gate.get('prior') or 0.0,
        'contradiction': gate.get('contradiction') or 0.0,
        'prior_boost': (score_detail or {}).get('metadata_prior_boost'),
        'penalty': (score_detail or {}).get('metadata_penalty'),
    }
    ev['matched_facility_pills'] = matched_pills
    ev['matched_facility_labels'] = matched_labels
    ev['metadata_contradiction_quotes'] = quotes
    if contradicted:
        labels = [PILL_LABELS.get(p, p) for p in contradicted]
        ev['facilities_evidence_summary'] = (
            'Profil tempat menandai '
            + _join_indonesian_topics([str(label).lower() for label in labels])
            + ', tetapi ulasan pengunjung menentang klaim itu.'
        )
    elif matched_labels:
        note = (
            'Profil tempat menandai '
            + _join_indonesian_topics([str(label).lower() for label in matched_labels])
            + ' (klaim pendukung, bukan bukti utama).'
        )
        if not ev.get('facilities_evidence_summary'):
            ev['facilities_evidence_summary'] = note
    if quotes:
        ev['modal_caveat_quotes'] = _merge_caveat_quote_rows(
            quotes,
            ev.get('modal_caveat_quotes'),
            limit=2,
        )
    return ev


def _quote_is_caveat(quote_text, preference_keywords):
    """
    True bila kutipan tidak layak dipakai sebagai bukti kecocokan.

    Urutan:
      1. frasa ekstrem ("kurang/tidak disarankan") — selalu caveat
      2. verdict LLM per kutipan
      3. heuristik jendela token (fallback)
    """
    text = str(quote_text or '')
    if len(text.strip()) < _MIN_QUOTE_CHARS:
        return False
    if _quote_has_unsuitability_phrase(text):
        return True
    llm_label = _quote_llm_label(text)
    if llm_label is not None:
        return llm_label in ('caveat', 'irrelevant')
    normalized = _normalize_keyword_phrase(text)
    if normalized and any(phrase in normalized for phrase in _UNSUITABILITY_PHRASES):
        return True
    if preference_keywords:
        return _review_has_weakness_near_preference_keywords(text, preference_keywords)
    return _review_has_weakness_signal(text)


def _apply_llm_verdicts_to_quote_groups(supporting, caveats):
    """
    Re-bucket kutipan rerank/modal menurut verdict LLM.
    Tanpa verdict, bucket asal dipertahankan (rule tidak menimpa rerank).
    """
    out_supporting = []
    out_caveats = []
    seen = set()

    def push(row, default_bucket):
        if not isinstance(row, dict):
            return
        quote = str(row.get('quote') or '').strip()
        if len(quote) < _MIN_QUOTE_CHARS:
            return
        marker = clause_quote_key(quote)
        if not marker or marker in seen:
            return
        dest = _quote_destination(quote, default_bucket)
        if dest is None:
            return
        seen.add(marker)
        item = dict(row)
        item['quote'] = quote
        item['sentiment'] = dest
        verdict = _quote_llm_verdict(quote)
        if verdict is not None:
            item['sentiment_source'] = 'llm'
            item['sentiment_clause'] = verdict.get('clause') or ''
        if dest == 'caveat':
            out_caveats.append(item)
        else:
            out_supporting.append(item)

    for row in supporting or []:
        push(row, 'supporting')
    for row in caveats or []:
        push(row, 'caveat')
    return out_supporting, out_caveats


def _collect_modal_quote_groups(evidence, pills, search_keywords=None):
    """
    Kumpulkan kutipan modal lalu pisahkan berdasarkan sentimen terhadap preferensi.

    Return: (supporting, caveats)
      - supporting: kutipan yang cocok preferensi TANPA keluhan pada aspek itu,
        dipakai sebagai "bukti kecocokan".
      - caveats: kutipan yang cocok preferensi tetapi memuat keluhan pada aspek itu,
        dipakai sebagai "catatan dari ulasan" (bukan bukti kecocokan).
    """
    if not evidence:
        return [], []
    if evidence.get('llm_extracted') and (evidence.get('modal_display_quotes') or []):
        supporting = [
            dict(row) for row in (evidence.get('modal_display_quotes') or [])
            if isinstance(row, dict) and str(row.get('quote') or '').strip()
        ]
        caveats = [
            dict(row) for row in (evidence.get('modal_caveat_quotes') or [])
            if isinstance(row, dict) and str(row.get('quote') or '').strip()
        ]
        return _apply_llm_verdicts_to_quote_groups(supporting, caveats)
    search_keywords = _light_keyword_phrase_list(
        search_keywords or evidence.get('search_keywords') or [],
    )
    preference_keywords = _preference_keywords_for_evidence(pills, search_keywords)
    pill_set = {str(p).strip().lower() for p in (pills or []) if str(p).strip()}
    seen = set()
    candidates = []

    def _reason_ok(reason):
        if not reason or not str(reason).strip():
            return False
        return True

    def push(item):
        q = str(item.get('quote') or '').strip()
        if len(q) < _MIN_QUOTE_CHARS:
            return
        k = clause_quote_key(q)
        if not k or k in seen:
            return
        seen.add(k)
        candidates.append(dict(item))

    review_quotes = evidence.get('review_quotes') or []
    for item in review_quotes:
        pill = str(item.get('pill') or '').lower()
        if pill_set:
            if not (
                pill in pill_set
                or pill == 'search_keywords'
                or pill == 'semantic_match'
            ):
                continue
        reason = item.get('reason')
        if not _reason_ok(reason):
            continue
        push(item)

    for item in evidence.get('positive_review_quotes') or []:
        terms = item.get('matched_terms') or []
        reason = ', '.join(str(t).strip() for t in terms[:4] if str(t).strip())
        if not _reason_ok(reason):
            continue
        row = {**item, 'reason': reason, 'pill_label': item.get('pill_label') or 'Ulasan pengguna'}
        push(row)

    for item in evidence.get('search_keyword_matches') or []:
        terms = item.get('matched_terms') or []
        reason = ', '.join(str(t).strip() for t in terms[:4] if str(t).strip())
        if not _reason_ok(reason):
            continue
        row = {**item, 'reason': reason, 'pill_label': 'Kecocokan kata kunci'}
        push(row)

    for item in evidence.get('semantic_matches') or []:
        terms = item.get('matched_terms') or []
        reason = ', '.join(str(t).strip() for t in terms[:3] if str(t).strip())
        if not _reason_ok(reason):
            continue
        row = {
            **item,
            'reason': f'mirip makna: {reason}',
            'pill_label': 'Makna serupa',
            'match_source': 'semantic',
        }
        push(row)

    # Bucket negatif hanya masuk sebagai catatan, dan hanya bila kutipannya memang
    # menyentuh keyword preferensi (bukan sekadar review berating rendah).
    for item in evidence.get('negative_review_quotes') or []:
        terms = item.get('matched_terms') or []
        reason = ', '.join(str(t).strip() for t in terms[:4] if str(t).strip())
        if not _reason_ok(reason):
            continue
        row = {**item, 'reason': reason, 'pill_label': item.get('pill_label') or 'Catatan pengguna'}
        push(row)

    supporting = []
    caveats = []
    for item in _sort_quotes_for_modal_display(candidates):
        row = dict(item)
        verdict = _quote_llm_verdict(row.get('quote'))
        if verdict is not None:
            # Kutipan yang menurut LLM tidak membahas preferensi user sama sekali
            # dibuang: bukan bukti kecocokan, dan tidak layak jadi catatan.
            if str(verdict.get('label')) == 'irrelevant':
                continue
            row['sentiment_source'] = 'llm'
            row['sentiment_clause'] = verdict.get('clause') or ''
        if _quote_is_caveat(row.get('quote'), preference_keywords):
            row['sentiment'] = 'caveat'
            caveats.append(row)
        else:
            row['sentiment'] = 'supporting'
            supporting.append(row)

    meta_caveats = []
    for item in evidence.get('metadata_contradiction_quotes') or []:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row['sentiment'] = 'caveat'
        row['source'] = row.get('source') or 'metadata_contradiction'
        meta_caveats.append(row)
    if meta_caveats:
        caveats = _merge_caveat_quote_rows(meta_caveats, caveats, limit=max(2, len(caveats) + 2))
        support_keys = {_quote_marker_key(row.get('quote')) for row in caveats}
        supporting = [
            row for row in supporting
            if _quote_marker_key(row.get('quote')) not in support_keys
        ]
    return supporting, caveats


def _collect_modal_display_quotes(evidence, pills, search_keywords=None, limit=3):
    """Bukti kecocokan untuk modal: hanya kutipan relevan tanpa keluhan pada aspek itu."""
    if limit <= 0:
        return []
    supporting, _ = _collect_modal_quote_groups(
        evidence, pills, search_keywords=search_keywords,
    )
    return supporting[:limit]


def _build_modal_quote_summary_deterministic(shop_name, quotes, intent_phrase, evidence=None):
    """Fallback ringkasan modal (tanpa LLM)."""
    name = str(shop_name or 'Coffee shop ini').strip() or 'Coffee shop ini'
    if not quotes:
        # Jangan tampilkan pesan kosong-bukti; shop tanpa kutipan harus difilter dari output.
        return ''

    ev = evidence or {}
    reasons = []
    for q in quotes:
        r = str(q.get('reason') or '').strip()
        if r and r not in reasons:
            reasons.append(r)
        if len(reasons) >= 3:
            break
    themes = ', '.join(reasons[:2]) if reasons else 'pengalaman pengunjung'

    nums = []
    for q in quotes:
        try:
            if q.get('rating') is not None and q.get('rating') != '':
                nums.append(float(q['rating']))
        except (TypeError, ValueError):
            continue
    detail_parts = []
    avg_user_rating = ev.get('avg_user_rating')
    review_count = _safe_float(ev.get('review_count'))
    if avg_user_rating is not None:
        line = f'Rata-rata rating pengguna {float(avg_user_rating):.1f}/5'
        if review_count:
            line += f' dari {int(review_count)} ulasan'
        detail_parts.append(line)
    elif nums:
        detail_parts.append(f'Rata-rata rating pada kutipan di atas {sum(nums) / len(nums):.1f}/5')

    category_bits = []
    for key, label in (('suasana', 'suasana'), ('layanan', 'layanan'), ('makanan', 'makanan')):
        value = (ev.get('category_ratings') or {}).get(key)
        if value is not None:
            category_bits.append(f'{label} {float(value):.1f}')
    if category_bits:
        detail_parts.append('penilaian ' + ', '.join(category_bits))

    detail_line = (' ' + '; '.join(detail_parts) + '.') if detail_parts else ''

    ctx = str(intent_phrase or '').strip()
    if ctx:
        body = (
            f'{name} menurut ulasan pengunjung relevan untuk {ctx}, '
            f'terkait {themes}.{detail_line}'
        )
        return _normalize_whitespace(body)
    body = f'Pengunjung menyoroti {themes} tentang {name}.{detail_line}'
    return _normalize_whitespace(body)


def _safe_float(value):
    try:
        if value is None or value == '':
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _relevant_quote_lines_for_prompt(evidence, *, limit=6, char_limit=260):
    """
    Baris kutipan review yang paling relevan dengan konteks preferensi user.
    Urutan sumber mengikuti kekuatan bukti: kutipan modal (sudah tersaring),
    lalu match keyword pencarian, lalu kutipan positif umum.
    """
    ev = evidence or {}
    lines = []
    seen = set()
    for key in (
        'modal_display_quotes',
        'search_keyword_matches',
        'review_quotes',
        'positive_review_quotes',
    ):
        for row in ev.get(key) or []:
            if len(lines) >= limit:
                return lines
            if not isinstance(row, dict):
                continue
            text = _normalize_whitespace(str(row.get('quote') or row.get('text') or ''))
            if len(text) < _MIN_QUOTE_CHARS:
                continue
            dedupe = clause_quote_key(text)
            if not dedupe or dedupe in seen:
                continue
            seen.add(dedupe)
            rating = row.get('rating')
            rating_text = str(rating) if rating not in (None, '') else '?'
            reason = _normalize_whitespace(str(row.get('reason') or ''))
            if not reason:
                terms = [
                    str(t).strip()
                    for t in (row.get('matched_terms') or row.get('keywords') or [])
                    if str(t).strip()
                ]
                reason = ', '.join(terms[:4])
            suffix = f' | relevan karena: {reason}' if reason else ''
            lines.append(
                f'  - (rating {rating_text}) "{_truncate_evidence_text(text, char_limit)}"{suffix}'
            )
    return lines


def _weakness_quote_lines_for_prompt(evidence, *, limit=2, char_limit=220):
    """
    Baris kutipan bernada kurang positif untuk bagian catatan.
    `modal_caveat_quotes` diprioritaskan karena keluhannya sudah terbukti menempel
    pada konteks preferensi user, bukan sekadar review berating rendah.
    """
    ev = evidence or {}
    rows = ev.get('modal_caveat_quotes') or ev.get('negative_review_quotes') or []
    lines = []
    for row in rows[:limit]:
        if not isinstance(row, dict):
            continue
        text = _normalize_whitespace(str(row.get('quote') or row.get('text') or ''))
        if len(text) < _MIN_QUOTE_CHARS:
            continue
        rating = row.get('rating')
        rating_text = str(rating) if rating not in (None, '') else '?'
        lines.append(f'  - (rating {rating_text}) "{_truncate_evidence_text(text, char_limit)}"')
    return lines


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


def _evidence_has_relevant_quotes(evidence, pills=None, search_keywords=None):
    """True jika ada minimal 1 kutipan PENDUKUNG (bukan hanya keluhan) untuk preferensi."""
    quotes = _collect_modal_display_quotes(
        evidence or {},
        pills,
        search_keywords=search_keywords,
        limit=1,
    )
    return len(quotes) > 0


def _build_modal_quote_summary(shop_name, quotes, intent_phrase, evidence=None, pills=None, search_keywords=None):
    """
    Ringkasan modal berbasis chat completion dari evidence review yang tersedia.
    Fallback ke ringkasan deterministik saat LLM tidak tersedia / gagal.
    """
    name = str(shop_name or 'Coffee shop ini').strip() or 'Coffee shop ini'
    ev = evidence or {}
    fallback_summary = _build_modal_quote_summary_deterministic(name, quotes, intent_phrase, evidence=ev)

    if not llm_is_available():
        LOG_RECOMMEND.warning(f"Modal quote summary: LLM off, fallback ({name})")
        return fallback_summary

    LOG_RECOMMEND.info(f"Modal quote summary: panggil LLM untuk '{name}'...")
    modal_t0 = time.perf_counter()

    pill_stats = ev.get('pill_stats') or []
    facilities_tab = ev.get('facilities_tab_intent') or ev.get('facilities_tab') or {}
    facilities_intent_aligned = bool(ev.get('facilities_intent_aligned'))
    ctx = str(intent_phrase or '').strip() or 'preferensi umum'
    keyword_line = ", ".join(_light_keyword_phrase_list(search_keywords or [])) or 'tidak ada'
    profile_lines = _shop_profile_lines_for_prompt({}, ev, pills=pills) or ['  - (tidak ada data rating)']

    stats_lines = []
    for item in pill_stats[:6]:
        if not isinstance(item, dict):
            continue
        label = str(item.get('pill_label') or item.get('pill') or '').strip() or 'konteks'
        hits = item.get('keyword_review_hits')
        cat_field = item.get('category_field')
        cat_avg = item.get('category_avg')
        line = f"  - {label}: {hits} ulasan menyebut kata terkait"
        if cat_field and cat_avg is not None:
            line += f", rata-rata {cat_field} {cat_avg}/5"
        stats_lines.append(line)
    if not stats_lines:
        stats_lines = ['  - (tidak ada statistik pill)']

    facility_lines = []
    for key, label in (('popular_for', 'Populer untuk'), ('highlights', 'Keunggulan'), ('atmosphere', 'Suasana')):
        values = facilities_tab.get(key) or []
        if values:
            facility_lines.append(f"  - {label}: {', '.join(str(v) for v in values[:6])}")
    if facility_lines and facilities_intent_aligned:
        facility_lines.append('  - (sinyal fasilitas di atas selaras dengan preferensi user)')
    if not facility_lines:
        facility_lines = ['  - (tidak ada sinyal fasilitas tab)']
    gate = ev.get('metadata_gate') or {}
    matched_labels = [
        str(x) for x in (gate.get('matched_attribute_labels') or []) if x
    ]
    if matched_labels:
        facility_lines.append(
            '  - Profil fasilitas resmi selaras pill user: ' + ', '.join(matched_labels)
        )
    hours = str(ev.get('opening_hours_display') or '').strip()
    if hours:
        facility_lines.append(f'  - Jam operasional toko (database): {hours}')

    # Bukti kecocokan dan keluhan dipisah: kutipan yang memuat keluhan pada aspek
    # preferensi tidak boleh jadi alasan merekomendasikan.
    supporting_source = (
        {'modal_display_quotes': ev.get('modal_display_quotes') or []}
        if ev.get('modal_display_quotes')
        else ev
    )
    quote_lines = _relevant_quote_lines_for_prompt(supporting_source, limit=6, char_limit=300)
    if not quote_lines:
        quote_lines = ['  - (tidak ada kutipan review yang bisa diringkas)']

    prompt = f"""Anda meringkas ulasan SATU coffee shop secara objektif (orang ketiga).
Tulis 1 paragraf 3-4 kalimat padat berdasarkan kutipan di bawah. Jangan menyalin kata saya/aku/kami.

Syarat:
- Kalimat pertama: nama {name} + kebutuhan "{ctx}" hanya jika kutipan mendukung
- 1-2 detail konkret dari kutipan (bukan hanya nyaman/cozy)
- Satu paragraf, tanpa markdown, tanpa mengarang fakta

Nama coffee shop: {name}
Kebutuhan user: {ctx}
Keyword intent: {keyword_line}
Pill preferensi: {", ".join(pills or []) if pills else "tidak ada"}

Profil dari database:
{chr(10).join(profile_lines)}

Seberapa sering konteks ini dibahas:
{chr(10).join(stats_lines)}

Sinyal fasilitas:
{chr(10).join(facility_lines)}

Kutipan ulasan paling relevan dengan konteks:
{chr(10).join(quote_lines)}"""
    prompt = _compact_prompt_block(prompt, 5600)

    try:
        raw = llm_chat_completions_create(
            model=(HF_MODEL or "meta-llama/Meta-Llama-3-8B").strip(),
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'Anda merangkum SATU coffee shop dari ulasan. '
                        'Orang ketiga, 3-4 kalimat padat, hanya fakta dari data kutipan.'
                    ),
                },
                {'role': 'user', 'content': prompt},
            ],
            max_tokens=400,
            temperature=0.4,
        )
        summary = _normalize_whitespace(str(raw or ''))
        if summary.startswith('```'):
            summary = re.sub(r'^```[a-zA-Z]*\s*', '', summary).strip()
            summary = re.sub(r'\s*```$', '', summary).strip()
        # Prompt modal tidak lagi mewajibkan format label; cukup validasi teks natural.
        if not summary:
            return fallback_summary
        lowered = summary.lower()
        if lowered.startswith('{') or lowered.startswith('[') or '```' in summary or 'json' in lowered:
            return fallback_summary
        sentence_parts = [
            part.strip()
            for part in re.split(r'(?<=[.!?])\s+', summary)
            if part.strip()
        ]
        if not sentence_parts:
            return fallback_summary
        if len(sentence_parts) > 4:
            summary = ' '.join(sentence_parts[:4]).strip()
            if summary and summary[-1] not in '.!?':
                summary += '.'
        LOG_RECOMMEND.info(
            f"Modal quote summary: OK '{name}' "
            f"({round((time.perf_counter() - modal_t0) * 1000, 1)} ms)")
        return summary
    except Exception as err:
        LOG_RECOMMEND.warning(
            f"Modal quote summary LLM fallback triggered ({name}): {err}")
        return fallback_summary


def _attach_modal_evidence_to_supporting(evidence, shop_name, pills, search_keywords=None):
    """Salin evidence dan tambah modal_display_quotes, modal_caveat_quotes, modal_quote_summary."""
    ev = dict(evidence or {})
    if ev.get('llm_extracted') and (ev.get('modal_display_quotes') or []):
        if COFIND_MODAL_QUOTE_LLM and not ev.get('modal_quote_summary'):
            pill_labels = [PILL_LABELS.get(p, p) for p in (pills or [])]
            intent_phrase = ' dan '.join(pill_labels[:3]) if pill_labels else ''
            ev['modal_quote_summary'] = _build_modal_quote_summary(
                shop_name,
                ev.get('modal_display_quotes') or [],
                intent_phrase,
                evidence=ev,
                pills=pills,
                search_keywords=search_keywords,
            )
        else:
            ev.setdefault('modal_quote_summary', '')
        return ev

    quotes = list(ev.get('modal_display_quotes') or [])[:3]
    if not quotes:
        quotes = list(ev.get('review_quotes') or [])[:3]
    ev['modal_display_quotes'] = quotes
    ev['modal_caveat_quotes'] = list(ev.get('modal_caveat_quotes') or [])[:2]
    pill_labels = [PILL_LABELS.get(p, p) for p in (pills or [])]
    intent_phrase = ' dan '.join(pill_labels[:3]) if pill_labels else ''
    # Opsional via COFIND_MODAL_QUOTE_LLM=true. Saat mati, biarkan kosong supaya modal
    # memakai `explanation` (ringkasan LLM berbasis seluruh korpus review) yang jauh
    # lebih informatif ketimbang kalimat template deterministik.
    if COFIND_MODAL_QUOTE_LLM:
        ev['modal_quote_summary'] = _build_modal_quote_summary(
            shop_name,
            quotes,
            intent_phrase,
            evidence=ev,
            pills=pills,
            search_keywords=search_keywords,
        )
    else:
        ev['modal_quote_summary'] = ''
    return ev


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


def coverage_bonus():
    """Kekuatan bonus kelengkapan pill (0..1). 0 = fitur mati."""
    raw = (os.getenv('COFIND_COVERAGE_BONUS') or '').strip()
    if not raw:
        return 0.15
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        return 0.15


def coverage_semantic_min():
    """
    Ambang keyakinan agar kecocokan makna boleh dihitung sebagai "pill terbukti".

    Sengaja lebih tinggi dari COFIND_SEMANTIC_THRESHOLD: menarik kandidat ke
    pipeline (retrieval) boleh longgar, tetapi mengklaim sebuah atribut terbukti
    di ulasan harus lebih ketat supaya kesimpulan tidak menyesatkan.
    """
    raw = (os.getenv('COFIND_COVERAGE_SEMANTIC_MIN') or '').strip()
    if not raw:
        return 0.65
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        return 0.65


def activity_coverage_share():
    """
    Porsi cakupan yang langsung didapat begitu pill aktivitas terbukti (0..1).

    Sisanya (1 - nilai ini) disumbang lapis fasilitas. Nilai 0.8 berarti toko
    yang cocok aktivitasnya tapi belum terbukti fasilitasnya tetap unggul atas
    toko yang hanya terbukti fasilitasnya (cakupan 0), sesuai niat utama user.
    """
    raw = (os.getenv('COFIND_ACTIVITY_COVERAGE_SHARE') or '').strip()
    if not raw:
        return 0.8
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        return 0.8


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


def _generate_llm_review_summary(top_shops, pills, search_keywords=None, user_intent_line=None):
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
        top_shops, pills, search_keywords, user_intent_line=user_intent_line,
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


_GENERIC_SHORT_SUMMARY_RE = re.compile(
    r'^.+\s+(dinilai cocok|menjadi salah|sangat cocok|kurang cocok)\.?\s*$',
    re.I | re.S,
)


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


_GENERIC_PRAISE_MARKERS = (
    'kopi enak', 'kopinya enak', 'makanan enak', 'makanannya enak',
    'pelayanan ramah', 'pelayanannya ramah', 'recommended', 'worth it',
    'tempatnya nyaman', 'tempat nyaman', 'enak banget', 'recommended banget',
    'rasanya enak', 'menu enak',
)


def _quote_has_activity_or_semantic_link(row, pills, search_keywords=None):
    """True jika kutipan terhubung ke aktivitas, rerank, atau gerbang makna."""
    if not isinstance(row, dict):
        return False
    pill = str(row.get('pill') or '').strip().lower()
    if row.get('match_source') == 'semantic' or pill == 'semantic_match':
        return True
    if row.get('llm_extracted') or row.get('supporting_index'):
        return True
    activity_pills, _ = _split_preference_pills(pills)
    activity_set = {str(p).strip().lower() for p in activity_pills if p}
    if pill and pill in activity_set:
        return True
    if row.get('matched_terms'):
        return True
    text = str(row.get('quote') or '')
    keywords = _preference_keywords_for_evidence(activity_pills or pills, search_keywords)
    return any(_matches_keyword_phrase(text, keyword) for keyword in keywords)


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


# Kata domain generik yang tidak boleh dianggap "kebutuhan belum terbukti"
# saat memeriksa cakupan keyword free text (bukan bagian dari preferensi nyata).
_FREE_TEXT_GENERIC_STOP = frozenset({
    'coffee', 'shop', 'kafe', 'cafe', 'tempat', 'kedai',
})


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
    return (
        f"Tulis 1 paragraf singkat ({COFIND_SUMMARY_MIN_SENTENCES}-4 kalimat, mengalir natural) "
        f"tentang {shop_name} berdasarkan ulasan pelanggan — gaya rekomendasi dari teman, "
        "bukan laporan formal.\n\n"
        f"Kebutuhan user: {intent_line}.\n\n"
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
):
    """User prompt Step 5; untuk Gemini sudah strict sejak panggilan pertama."""
    prompt = _single_shop_summary_prompt(
        shop,
        pills,
        search_keywords,
        intent_line,
        quality_boost=prefer_gemini,
        prefer_gemini=prefer_gemini,
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


def _llm_summaries_for_shops(top_shops, pills, search_keywords=None, user_intent_line=None):
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


# Bobot persen tiap tahap pipeline. Angkanya perkiraan porsi waktu, bukan hasil ukur
# real-time: yang dijamin akurat adalah *tahap mana* yang sedang berjalan.
_RECOMMENDATION_PROGRESS_STAGES = (
    ('start', 6, 'Memahami konteks Anda'),
    ('profiles', 22, 'Mengumpulkan ulasan pengunjung'),
    ('scoring', 48, 'Mencari tempat yang relevan'),
    ('rerank', 72, 'Memilih yang paling cocok'),
    ('summary', 88, 'Menyusun rekomendasi untuk Anda'),
    ('done', 100, 'Rekomendasi siap'),
)
_RECOMMENDATION_PROGRESS_BY_STAGE = _build_recommendation_progress_map(
    _RECOMMENDATION_PROGRESS_STAGES
)


# Kutipan per kandidat yang dikirim ke verifikasi sentimen LLM. Dibatasi supaya
# jumlah klausa (dan panggilan LLM) tetap terkendali untuk satu request.
_SENTIMENT_QUOTES_PER_CANDIDATE = 6


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


def _recommendation_progress(stage, **extra):
    payload = dict(
        _RECOMMENDATION_PROGRESS_BY_STAGE.get(stage)
        or {'stage': stage, 'percent': 0, 'next_percent': 100, 'label': ''}
    )
    payload.update(extra)
    return ('progress', payload)


def _split_preference_pills(pills):
    pills = list(pills or [])
    activity_pills = [p for p in pills if p not in FACILITY_ATTRIBUTE_PILLS]
    attribute_pills = [p for p in pills if p in FACILITY_ATTRIBUTE_PILLS]
    return activity_pills, attribute_pills


def _enrich_evidence_with_profile_context(evidence, profile):
    """Salin jam buka profil ke evidence agar prompt/coverage konsisten."""
    ev = dict(evidence or {})
    prof = profile if isinstance(profile, dict) else {}
    hours = str(prof.get('opening_hours_display') or '').strip()
    if hours:
        ev['opening_hours_display'] = hours
    return ev


def _quote_texts_for_coverage(shop):
    """Korpus teks untuk coverage: semua kutipan evidence + teks review profil."""
    seen = set()
    texts = []

    def _add(raw):
        text = str(raw or '').strip()
        if len(text) < 6:
            return
        key = text[:180].lower()
        if key in seen:
            return
        seen.add(key)
        texts.append(text)

    for chunk in _iter_shop_quote_texts(shop):
        _add(chunk)
    profile = shop.get('profile') if isinstance(shop.get('profile'), dict) else {}
    for review in profile.get('reviews') or []:
        if isinstance(review, dict):
            _add(review.get('text') or review.get('review_text') or review.get('body'))
    return texts


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


def _recommendation_pipeline_events(prefs, _auth_user, query_text=''):
    """
    Pipeline RAG 3 fase. Dua jalur input SALING EKSKLUSIF per request:

      A. Jalur pill (seperti sebelumnya): `prefs` berisi pill aktivitas +
         atribut fasilitas dari PILL_MAPPING.
      B. Jalur free text: `query_text` (maks FREE_TEXT_MAX_CHARS) → LLM intent
         (keywords + dense_query); output langsung ke hybrid retrieval yang
         sama (BM25 + dense/ANN → RRF). Tidak ada upgrade otomatis ke pill.

      Fase 1 — Hard filter: wajib minimal 1 ulasan pipeline (Cofind + Google Places,
               get_reviews_for_recommendation_batch / REVIEW_BASED_MIN_REVIEWS=1).
      Fase 2 — Hybrid retrieval (semua jalur): BM25 + dense/ANN → RRF (k=COFIND_RRF_K).
               Jalur pill: gerbang aktivitas + metadata gate setelah RRF.
               Jalur free text: tanpa gerbang pill (rerank/summary yang menilai bukti).
               Top ~7 ke LLM.
      Fase 2b — Sentimen kutipan kandidat (default nyala, COFIND_LLM_CLAUSE_SENTIMENT):
                LLM label supporting/caveat; rule hanya fallback.
      Fase 3 — LLM rerank: pilih 0–3 toko yang kutipannya mendukung aktivitas,
               ekstrak kutipan pendukung (bukan jendela ±6 token).

      Feedback thumbs (helpful / not_helpful) disimpan via API feedback ke DB untuk
      analitik, evaluasi admin, dan UI modal — tidak mem-filter toko di Fase 1/2/3.

    Generator: yield ('progress', payload) di tiap batas tahap, lalu tepat satu
    ('result', (body_dict, status_code)) di akhir. Autentikasi dan parsing body
    dilakukan pemanggil supaya generator ini bebas dari request context Flask.
    """
    request_t0 = time.perf_counter()
    stage_t0 = request_t0
    stage_ms = {}
    clause_sentiment_token = None
    clause_sentiment_telemetry = {}
    semantic_budget_token = begin_semantic_encode_budget()
    llm_usage_token = None
    llm_route_token = None
    llm_run_route = None
    pipeline_run_id = None
    try:
        pipeline_run_id = new_pipeline_run_id()
        llm_usage_token = begin_llm_usage_collection()
        llm_route_token = begin_llm_run_route()

        query_text = str(query_text or '').strip()[:FREE_TEXT_MAX_CHARS]
        has_pills_input = bool(prefs)
        has_query_text = bool(query_text)

        if not has_pills_input and not has_query_text:
            yield ('result', ({
                'status': 'error',
                'message': 'Pilih pill preferensi atau isi kata kunci pencarian.',
            }, 400))
            return
        if has_pills_input and has_query_text:
            # Frontend menjaga eksklusivitas pill vs free text; ini jaring kedua
            # defensif di backend bila klien lama/custom mengirim keduanya.
            yield ('result', ({
                'status': 'error',
                'message': 'Kirim salah satu: pill preferensi atau kata kunci pencarian, tidak keduanya.',
            }, 400))
            return

        free_text_keywords = []
        free_text_dense_query = ''
        free_text_telemetry = {}
        user_intent_line = ''

        if has_pills_input:
            valid_pills = [p for p in prefs if p in PILL_MAPPING]
            if not valid_pills:
                yield ('result', ({
                    'status': 'error',
                    'message': f'Preferensi tidak dikenali: {", ".join(prefs)}',
                }, 400))
                return
        else:
            # --- Jalur free text: deteksi intent via LLM sebelum Fase 2 ---
            yield _recommendation_progress('intent')
            intent_t0 = time.perf_counter()
            intent_result = extract_search_intent(
                query_text,
                pill_labels=PILL_LABELS,
                pill_mapping=PILL_MAPPING,
                chat_fn=_llm_chat_for_pipeline,
                parse_json_fn=_parse_llm_json_with_repair,
            )
            stage_ms['intent_ms'] = round((time.perf_counter() - intent_t0) * 1000, 1)
            free_text_telemetry = intent_result.get('telemetry') or {}
            free_text_telemetry['intent_hint_pill'] = intent_result.get('matched_pill')
            free_text_telemetry['intent_hint_attributes'] = (
                intent_result.get('matched_attribute_pills') or []
            )
            LOG_RECOMMEND.info(
                f"Free text intent: query={query_text!r} backend={free_text_telemetry.get('backend')} "
                f"hint_pill={intent_result.get('matched_pill')} "
                f"keywords={intent_result.get('keywords')}"
            )

            valid_pills = []
            user_intent_line = query_text
            free_text_keywords = [
                str(k).strip() for k in (intent_result.get('keywords') or []) if str(k or '').strip()
            ]
            free_text_dense_query = str(intent_result.get('dense_query') or '').strip() or query_text

            if not free_text_keywords:
                yield ('result', ({
                    'status': 'success',
                    'message': 'Kata kunci terlalu umum, coba kata kunci lain atau pilih pill preferensi.',
                    'recommendations': [],
                }, 200))
                return

        if COFIND_DEV_LLM_STRICT and not llm_is_available():
            yield ('result', ({
                'status': 'error',
                'message': 'LLM strict mode aktif tetapi LLM tidak tersedia.',
                'recommendations': [],
            }, 503))
            return

        llm_run_route = probe_llm_for_recommendation_run()
        stage_ms['llm_run_route'] = llm_run_route.mode
        stage_ms['llm_probe_reason'] = llm_run_route.reason
        if llm_run_route.hf_error_snippet:
            stage_ms['llm_probe_hf_error'] = llm_run_route.hf_error_snippet[:120]
        route_log = (
            f"LLM route run: {llm_run_route.mode} (reason={llm_run_route.reason})"
        )
        if llm_run_route.hf_error_snippet and llm_run_route.mode == 'gemini':
            route_log += f" hf_err={llm_run_route.hf_error_snippet[:100]}"
        LOG_RECOMMEND.info(route_log)
        if llm_run_route.mode == 'off':
            LOG_RECOMMEND.info(
                "LLM probe: fase LLM (rerank/sentiment/summary) memakai fallback "
                "hybrid/deterministik untuk run ini."
            )

        activity_pills, attribute_pills = _split_preference_pills(valid_pills)
        LOG_RECOMMEND.info(f"Pills: {valid_pills}")
        yield _recommendation_progress('start')

        # Umpan balik not_helpful (thumbs-down) dicatat ke DB lewat
        # /api/recommend-by-preferences/feedback (upsert_recommendation_feedback) untuk
        # analitik, ringkasan admin, dan state UI modal — BUKAN filter hard retrieval.
        # Toko yang pernah not_helpful tetap diload di Fase 1 (_build_profiles_for_recommendation
        # tanpa excluded_place_ids dari feedback). Jika LLM rerank memilih toko itu lagi,
        # rekomendasi tetap dikirim ke client.

        # Konteks personalisasi (review sendiri + favorit) untuk tahap keputusan LLM.
        taste_profile = build_user_taste_profile(_auth_user.get('id'))
        user_taste_block = format_user_taste_prompt_block(taste_profile)

        all_place_ids = _load_all_place_ids()
        if not all_place_ids:
            yield ('result', ({'status': 'error', 'message': 'Data coffee shop kosong.'}, 500))
            return
        facilities_index = load_facilities_index()

        MAX_REC = 3

        # --- Fase 1: hard filter (min review pipeline; bukan exclude not_helpful) ---
        LOG_RECOMMEND.info("Fase 1: batch load profil + reviews...")
        profiles, shops_without_reviews = _build_profiles_for_recommendation(
            all_place_ids,
            facilities_index=facilities_index,
        )
        LOG_RECOMMEND.info(
            f"Fase 1 selesai: profiles={len(profiles)} "
            f"tanpa_review={len(shops_without_reviews)}")
        stage_ms['profile_load_ms'] = round((time.perf_counter() - stage_t0) * 1000, 1)
        stage_t0 = time.perf_counter()
        yield _recommendation_progress('profiles', shops_with_reviews=len(profiles))

        # --- Fase 2: Hybrid retrieval (BM25 + dense/ANN → RRF) ---
        quality_by_place = {
            str(profile.get('place_id')): _quality_score_for_profile(profile)
            for profile in profiles
            if profile.get('place_id')
        }
        if has_pills_input:
            retrieval = retrieve_top_k(
                profiles,
                valid_pills,
                pill_labels=PILL_LABELS,
                pill_mapping=PILL_MAPPING,
                quality_by_place=quality_by_place,
                top_k=retrieval_top_k(),
                activity_pills=activity_pills,
                attribute_pills=attribute_pills,
            )
        else:
            retrieval = retrieve_top_k_by_text(
                profiles,
                query_tokens=free_text_keywords,
                dense_query_text=free_text_dense_query,
                quality_by_place=quality_by_place,
                top_k=retrieval_top_k(),
            )
        retrieval_telemetry = dict(retrieval.get('telemetry') or {}, free_text=free_text_telemetry)
        query_tokens = retrieval.get('query_tokens') or []
        # NB: `query_text` di sini SENGAJA menimpa parameter free-text mentah di
        # atas — dari titik ini sampai akhir fungsi, `query_text` berarti teks
        # dense query hasil retrieval (konsisten dengan jalur pill sebelumnya).
        query_text = retrieval.get('query_text') or ''
        activity_tokens = retrieval.get('activity_tokens') or []
        attribute_tokens = retrieval.get('attribute_tokens') or []
        activity_query_text = retrieval.get('activity_query_text') or query_text
        activity_matcher = retrieval.get('activity_matcher') or compile_activity_matcher(
            activity_pills, pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING,
        )
        search_keywords = query_tokens
        scored_candidates = []
        for item in retrieval.get('candidates') or []:
            profile = item.get('profile') or {}
            score_detail = dict(item.get('score_detail') or {})
            keyword_detail = _score_shop_by_user_reviews(
                profile, valid_pills, search_keywords=query_tokens,
            )
            score_detail['per_pill_stats'] = keyword_detail.get('per_pill_stats') or {}
            retrieval_ev = _build_retrieval_evidence(
                profile,
                valid_pills,
                query_text=query_text,
                query_tokens=query_tokens,
                activity_tokens=activity_tokens,
                activity_query_text=activity_query_text,
                attribute_tokens=attribute_tokens,
                activity_matcher=activity_matcher,
                activity_pills=activity_pills,
                attribute_pills=attribute_pills,
            )
            review_ev = _build_review_based_evidence(
                profile, score_detail, valid_pills, search_keywords=query_tokens,
            )
            retrieval_ev['pill_stats'] = review_ev.get('pill_stats') or []
            if review_ev.get('positive_review_quotes'):
                retrieval_ev['positive_review_quotes'] = _merge_quote_rows(
                    retrieval_ev.get('positive_review_quotes'),
                    review_ev.get('positive_review_quotes'),
                )
            shop = {
                'place_id': item.get('place_id'),
                'name': item.get('name') or profile.get('name') or '',
                'score': item.get('score', 0),
                'profile': profile,
                'score_detail': score_detail,
                'evidence': _enrich_evidence_with_profile_context(
                    _attach_metadata_gate_to_evidence(
                        retrieval_ev,
                        score_detail=score_detail,
                        metadata_gate=item.get('metadata_gate'),
                        reviews=(profile.get('reviews') or []),
                    ),
                    profile,
                ),
            }
            _attach_pill_coverage(shop, valid_pills)
            scored_candidates.append(shop)
        stage_ms['hybrid_retrieval_ms'] = round((time.perf_counter() - stage_t0) * 1000, 1)
        stage_t0 = time.perf_counter()
        LOG_RECOMMEND.info(
            f"Fase 2 selesai: {len(scored_candidates)}/{retrieval_telemetry.get('kept_with_signal', 0)} "
            f"kandidat (gated={retrieval_telemetry.get('activity_gated')}, "
            f"lex={retrieval_telemetry.get('activity_pass_lexical', 0)}, "
            f"dense_only={retrieval_telemetry.get('activity_pass_dense_only', 0)}, "
            f"rejected={retrieval_telemetry.get('activity_rejected', 0)}, "
            f"meta_prior={retrieval_telemetry.get('metadata_prior_applied', 0)}, "
            f"meta_penalty={retrieval_telemetry.get('metadata_penalized', 0)}) "
            f"bm25_shops={retrieval_telemetry.get('bm25_shops')}, "
            f"dense={retrieval_telemetry.get('dense')})")
        yield _recommendation_progress('scoring', candidates=len(scored_candidates))

        if not scored_candidates:
            yield _recommendation_progress('done', shortlisted=0)
            yield ('result', ({
                'status': 'success',
                'message': _MANUAL_UNCLEAR_MESSAGE,
                'recommendations': [],
            }, 200))
            return

        sentiment_t0 = time.perf_counter()
        verdicts, clause_sentiment_telemetry = _run_clause_sentiment_for_candidates(
            scored_candidates, valid_pills,
        )
        if verdicts:
            clause_sentiment_token = _set_clause_verdicts(verdicts)
        stage_ms['clause_sentiment_ms'] = round((time.perf_counter() - sentiment_t0) * 1000, 1)
        if clause_sentiment_telemetry.get('skipped'):
            LOG_RECOMMEND.info(
                f"Clause sentiment dilewati: {clause_sentiment_telemetry.get('skipped')}")
        else:
            LOG_RECOMMEND.info(
                f"Clause sentiment: quotes={clause_sentiment_telemetry.get('quotes', 0)} "
                f"verdicts={clause_sentiment_telemetry.get('verdicts', 0)} "
                f"llm_calls={clause_sentiment_telemetry.get('llm_calls', 0)}")

        # --- Fase 3: LLM rerank + ekstraksi kutipan/caveat (fallback: urutan hybrid) ---
        rerank_backend = 'hybrid'
        rerank_telemetry = {}
        ranked_candidates = scored_candidates
        keyword_line = query_text or ', '.join(query_tokens[:20])
        if scored_candidates and _llm_ready_for_recommend_run() and llm_rerank_enabled():
            rerank_pool = scored_candidates[:llm_rerank_pool()]
            rerank_user_id = _auth_user.get('id')
            cached_fits = _get_cached_rerank_fits(
                rerank_pool,
                valid_pills,
                user_id=rerank_user_id,
                search_keywords=query_tokens,
            )
            rerank_result = llm_rerank_candidates(
                scored_candidates,
                valid_pills,
                pill_labels=PILL_LABELS,
                pill_mapping=PILL_MAPPING,
                chat_fn=_llm_chat_for_pipeline,
                parse_json_fn=_parse_llm_json_with_repair,
                user_taste_block=user_taste_block,
                keyword_line=keyword_line,
                cached_fits=cached_fits,
                max_candidates=retrieval_top_k(),
                activity_pills=activity_pills,
                activity_tokens=activity_tokens,
                activity_matcher=activity_matcher,
            ) or {}
            rerank_telemetry = rerank_result.get('telemetry') or {}
            if rerank_result.get('ranked'):
                ranked_candidates = rerank_result['ranked']
                rerank_backend = rerank_telemetry.get('backend') or 'llm'
                if not cached_fits:
                    _store_rerank_fits(
                        rerank_pool,
                        valid_pills,
                        rerank_result.get('fits') or {},
                        user_id=rerank_user_id,
                        search_keywords=query_tokens,
                    )
            else:
                LOG_RECOMMEND.warning(
                    f"Fase 3: LLM rerank tidak dipakai "
                    f"({rerank_telemetry.get('backend')}: {rerank_telemetry.get('error')})")
                if COFIND_DEV_LLM_STRICT:
                    raise RuntimeError(
                        f"LLM strict mode aktif: rerank gagal ({rerank_telemetry.get('error')})"
                    )

        top_shops = _select_top_shops(
            ranked_candidates,
            max_rec=max(MAX_REC, retrieval_top_k()),
            activity_tokens=activity_tokens,
            activity_pills=activity_pills,
            activity_matcher=activity_matcher,
        )
        kept = []
        dropped_activity = 0
        for shop in top_shops:
            _apply_llm_extracted_quotes(
                shop, valid_pills,
                activity_tokens=activity_tokens,
                activity_matcher=activity_matcher,
            )
            if _shop_has_activity_contradiction(
                shop, activity_pills, activity_tokens, activity_matcher=activity_matcher,
            ):
                dropped_activity += 1
                LOG_RECOMMEND.info(
                    f"Drop {shop.get('name')}: kutipan menolak aktivitas "
                    f"{[PILL_LABELS.get(p, p) for p in activity_pills]}"
                )
                continue
            evidence = shop.get('evidence') or {}
            caveat_rows = list(evidence.get('modal_caveat_quotes') or [])
            caveat_keys = {
                clause_quote_key(row.get('quote') if isinstance(row, dict) else row)
                for row in caveat_rows
            }
            display = _supporting_quotes_without_activity_contradiction(
                evidence.get('modal_display_quotes') or [],
                activity_pills,
                activity_tokens,
                activity_matcher=activity_matcher,
            )
            display = [
                row for row in display
                if clause_quote_key(
                    row.get('quote') if isinstance(row, dict) else row
                ) not in caveat_keys
            ]
            if not display:
                display = _activity_quotes_from_reviews(
                    shop, activity_matcher, activity_tokens, limit=3,
                )
            if attribute_pills and len(display) < 3:
                existing = {
                    clause_quote_key(row.get('quote') if isinstance(row, dict) else row)
                    for row in display
                }
                for row in _attribute_quote_rows(evidence, attribute_pills, limit=3):
                    if len(display) >= 3:
                        break
                    key = clause_quote_key(row.get('quote'))
                    if not key or key in existing:
                        continue
                    existing.add(key)
                    display.append(row)
            evidence['modal_display_quotes'] = display
            shop['evidence'] = evidence
            if not display:
                LOG_RECOMMEND.info(
                    f"Keep {shop.get('name')}: bukti aktivitas tanpa kutipan fasilitas"
                )
            _attach_pill_coverage(shop, valid_pills)
            kept.append(shop)
            if len(kept) >= MAX_REC:
                break
        top_shops = kept
        if dropped_activity:
            LOG_RECOMMEND.info(
                f"Fase 3: {dropped_activity} toko dibuang karena kontradiksi aktivitas"
            )
        stage_ms['rerank_ms'] = round((time.perf_counter() - stage_t0) * 1000, 1)
        stage_ms['rerank_backend'] = rerank_backend
        stage_t0 = time.perf_counter()
        LOG_RECOMMEND.info(
            f"Fase 3: {len(top_shops)}/{MAX_REC} toko dari rerank={rerank_backend} "
            f"(kandidat dinilai LLM={rerank_telemetry.get('scored_by_llm', 0)}, "
            f"kutipan tidak tergrounding={rerank_telemetry.get('ungrounded_quotes', 0)})")
        for rank, shop in enumerate(top_shops, 1):
            fit = shop.get('llm_fit') or {}
            LOG_RECOMMEND.debug(
                f"#{rank} {shop.get('name')} score={shop.get('score')} "
                f"final={shop.get('final_score', shop.get('score'))} "
                f"llm_fit={fit.get('fit_score')}")

        yield _recommendation_progress('rerank', shortlisted=len(top_shops))

        if not top_shops:
            yield _recommendation_progress('done', shortlisted=0)
            yield ('result', ({
                'status': 'success',
                'message': _MANUAL_UNCLEAR_MESSAGE,
                'recommendations': [],
            }, 200))
            return

        # --- Step 5: LLM NLP summary wajib mengutip review ---
        LOG_RECOMMEND.info(
            f"Step 5: generate summary untuk {len(top_shops)} shop...")
        yield _recommendation_progress('summary', shortlisted=len(top_shops))
        recommendations, summary_stats = _generate_llm_review_summary(
            top_shops,
            valid_pills,
            search_keywords=query_tokens,
            user_intent_line=user_intent_line or None,
        )
        stage_ms['llm_summary_ms'] = round((time.perf_counter() - stage_t0) * 1000, 1)
        stage_ms['summary_llm_count'] = summary_stats.get('summary_llm_count')
        stage_ms['summary_fallback_count'] = summary_stats.get('summary_fallback_count')
        stage_ms['total_ms'] = round((time.perf_counter() - request_t0) * 1000, 1)
        token_usage = summarize_llm_usage()
        stage_ms['llm_prompt_tokens'] = token_usage.get('prompt_tokens')
        stage_ms['llm_completion_tokens'] = token_usage.get('completion_tokens')
        stage_ms['llm_total_tokens'] = token_usage.get('total_tokens')
        degradation = build_degradation_snapshot(
            llm_available=_llm_ready_for_recommend_run(),
            clause_sentiment_telemetry=clause_sentiment_telemetry,
            rerank_backend=rerank_backend,
            rerank_telemetry=rerank_telemetry,
            delivered_count=len(recommendations),
            summary_fallback_count=int(
                summary_stats.get('summary_fallback_count') or 0
            ),
        )
        dense_tel = retrieval_telemetry.get('dense') or {}
        pipeline_snapshot = dict(degradation)
        pipeline_snapshot['hybrid_retrieval_ms'] = stage_ms.get('hybrid_retrieval_ms')
        pipeline_snapshot['dense_pool'] = dense_tel.get('pool')
        pipeline_snapshot['dense_store'] = dense_tel.get('store')
        pipeline_snapshot['ann_reviews'] = dense_tel.get('ann_reviews')
        prefs_key = preferences_key_from_pills(valid_pills)
        metric_payload = {
            'run_id': pipeline_run_id,
            'user_id': _auth_user.get('id'),
            'preferences_key': prefs_key,
            'status': 'success',
            'delivered_count': len(recommendations),
            'stage_ms': stage_ms,
            'token_usage': token_usage,
            'degradation': degradation,
            'retrieval': {
                'metadata_prior_applied': retrieval_telemetry.get('metadata_prior_applied'),
                'metadata_penalized': retrieval_telemetry.get('metadata_penalized'),
            },
        }
        log_recommendation_run_json(metric_payload)
        record_pipeline_run(
            run_id=pipeline_run_id or new_pipeline_run_id(),
            user_id=_auth_user.get('id'),
            preferences_key=prefs_key,
            status='success',
            delivered_count=len(recommendations),
            stage_ms=stage_ms,
            retrieval_telemetry=retrieval_telemetry,
            snapshot=pipeline_snapshot,
            token_usage=token_usage,
        )
        LOG_METRIC.info(f"recommend_by_preferences {stage_ms}")
        LOG_RECOMMEND.info(
            f"Selesai: {len(recommendations)} rekomendasi dikirim ke client "
            f"(run_id={pipeline_run_id}, llm_tokens={token_usage.get('total_tokens')})")

        yield _recommendation_progress('done', delivered=len(recommendations))
        yield ('result', ({
            'status': 'success',
            'preferences': valid_pills,
            'preference_activities': [p for p in valid_pills if p not in FACILITY_ATTRIBUTE_PILLS],
            'preference_attributes': [p for p in valid_pills if p in FACILITY_ATTRIBUTE_PILLS],
            'search_keywords': search_keywords,
            'llm_pipeline': {
                'run_id': pipeline_run_id,
                'config': full_pipeline_config(),
                'degradation': degradation,
                'token_usage': token_usage,
                'stage_ms': dict(stage_ms),
                'retrieval': dict(retrieval_telemetry),
                'rerank': dict(rerank_telemetry, backend=rerank_backend),
                'clause_sentiment': dict(
                    clause_sentiment_config(),
                    **clause_sentiment_telemetry,
                ),
                'personalization_used': bool(user_taste_block),
                'semantic': dict(
                    semantic_gate_config(),
                    model_ready=semantic_model_available(),
                    budget=semantic_encode_budget_state(),
                ),
            },
            'recommendations': recommendations,
        }, 200))

    except Exception as e:
        LOG_RECOMMEND.exception("Pipeline rekomendasi gagal")
        yield ('result', ({'status': 'error', 'message': str(e), 'recommendations': []}, 500))
    finally:
        _reset_clause_verdicts(clause_sentiment_token)
        reset_semantic_encode_budget(semantic_budget_token)
        if llm_route_token is not None:
            reset_llm_run_route(llm_route_token)
        if llm_usage_token is not None:
            reset_llm_usage_collection(llm_usage_token)
        # Vektor & verdict baru ditulis ke lapis file sekali per request, bukan
        # per kalimat, supaya request berikutnya tidak menghitung ulang.
        for flush_fn in (flush_semantic_cache, flush_clause_sentiment_cache):
            try:
                flush_fn()
            except Exception as flush_err:
                LOG_RECOMMEND.warning(f"Gagal flush cache: {str(flush_err)[:120]}")
        try:
            if 'total_ms' not in stage_ms:
                stage_ms['total_ms'] = round((time.perf_counter() - request_t0) * 1000, 1)
            stage_ms.setdefault('rerank_backend', 'none')
            LOG_METRIC.info(f"recommend_by_preferences_final {stage_ms}")
        except Exception as metric_err:
            # Telemetry tidak boleh menggagalkan request yang sudah selesai.
            LOG_METRIC.debug(f"Gagal menulis metrik akhir: {metric_err}")


_MAX_ACTIVITY_PILLS = 1
_MAX_ATTRIBUTE_PILLS = 3


def _as_pill_list(value):
    if not isinstance(value, list):
        value = [value] if value else []
    out = []
    for item in value:
        pill = str(item).strip().lower()
        if pill and pill not in out:
            out.append(pill)
    return out


def _read_recommendation_preferences():
    """
    Normalisasi body request menjadi (pills, query_text).

    Dua jalur SALING EKSKLUSIF (ditegakkan juga di frontend — lihat
    ShopList.jsx handlePillClick/handleSearchKeywordChange):
      - Jalur pill: `preferences` (konteks aktivitas, maks 1) + `attributes`
        (atribut fasilitas lapis 2, maks 3). Atribut yang terkirim di dalam
        `preferences` juga diterima agar klien lama/baru sama-sama jalan.
      - Jalur free text: `query_text` (maks FREE_TEXT_MAX_CHARS karakter) —
        kata kunci bebas yang diparse LLM (lihat free_text_intent.py) saat
        user tidak menemukan pill yang cocok.

    Return: (pills: List[str], query_text: str)
    """
    data = request.get_json(silent=True) or {}
    raw_prefs = _as_pill_list(data.get('preferences'))
    raw_attrs = _as_pill_list(data.get('attributes'))
    raw_query_text = str(data.get('query_text') or '').strip()[:FREE_TEXT_MAX_CHARS]

    activities = [p for p in raw_prefs if p not in FACILITY_ATTRIBUTE_PILLS][:_MAX_ACTIVITY_PILLS]
    attributes = []
    for pill in raw_prefs + raw_attrs:
        if pill in FACILITY_ATTRIBUTE_PILLS and pill not in attributes:
            attributes.append(pill)
    pills = activities + attributes[:_MAX_ATTRIBUTE_PILLS]
    return pills, raw_query_text


@app.route('/api/recommend-by-preferences', methods=['POST'])
def api_recommend_by_preferences():
    """Rekomendasi pill/free-text (respons JSON sekali kirim). Progress diabaikan di sini."""
    prefs, query_text = _read_recommendation_preferences()
    auth_user, auth_error = require_authenticated_user()
    if auth_error is not None:
        return auth_error

    body, status = {'status': 'error', 'message': 'Pipeline tidak menghasilkan respons.'}, 500
    for kind, payload in _recommendation_pipeline_events(prefs, auth_user, query_text=query_text):
        if kind == 'result':
            body, status = payload
    return jsonify(body), status


def _sse_pack(event, payload):
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.route('/api/recommend-by-preferences/stream', methods=['POST'])
def api_recommend_by_preferences_stream():
    """
    Versi streaming dari rekomendasi pill/free-text: mengirim event `progress`
    tiap tahap pipeline, lalu satu event `result` berisi payload yang identik
    dengan endpoint JSON biasa. Klien memakai fetch + ReadableStream (bukan
    EventSource) karena butuh header Authorization.
    """
    prefs, query_text = _read_recommendation_preferences()
    auth_user, auth_error = require_authenticated_user()
    if auth_error is not None:
        return auth_error

    LOG_RECOMMEND.info(
        f"Stream rekomendasi: user_id={auth_user.get('id')} prefs={prefs!r} "
        f"query_text={query_text!r}"
    )

    def generate():
        # Padding awal supaya proxy/browser tidak menahan byte pertama.
        yield ': cofind-stream\n\n'
        delivered_result = False
        try:
            for kind, payload in _recommendation_pipeline_events(prefs, auth_user, query_text=query_text):
                if kind == 'progress':
                    yield _sse_pack('progress', payload)
                elif kind == 'result':
                    body, status = payload
                    delivered_result = True
                    yield _sse_pack('result', {'status_code': status, 'body': body})
        except Exception as stream_err:
            LOG_RECOMMEND.exception("Stream rekomendasi gagal")
            if not delivered_result:
                delivered_result = True
                yield _sse_pack('result', {
                    'status_code': 500,
                    'body': {
                        'status': 'error',
                        'message': str(stream_err),
                        'recommendations': [],
                    },
                })
        if not delivered_result:
            yield _sse_pack('result', {
                'status_code': 500,
                'body': {
                    'status': 'error',
                    'message': 'Pipeline tidak menghasilkan respons.',
                    'recommendations': [],
                },
            })

    response = Response(stream_with_context(generate()), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache, no-transform'
    response.headers['Connection'] = 'keep-alive'
    # Matikan buffering nginx supaya event sampai real-time.
    response.headers['X-Accel-Buffering'] = 'no'
    return response


@app.route('/api/recommend-by-preferences/feedback', methods=['POST'])
def api_recommend_feedback_upsert():
    """
    Simpan thumbs up/down untuk satu item rekomendasi pill (persist DB / telemetri evaluasi).
    Vote not_helpful tidak mengecualikan toko dari request rekomendasi berikutnya.
    Body: {
      place_id, preferences: [...], vote: 'helpful'|'not_helpful',
      reason?, rank_position?, score?
    }
    """
    try:
        auth_user, auth_error = require_authenticated_user()
        if auth_error is not None:
            return auth_error

        data = request.get_json(silent=True) or {}
        place_id = data.get('place_id')
        preferences = data.get('preferences') or []
        vote = data.get('vote')
        reason = data.get('reason')
        rank_position = data.get('rank_position')
        score = data.get('score')

        result = upsert_recommendation_feedback(
            auth_user.get('id'),
            place_id,
            preferences,
            vote,
            reason=reason,
            rank_position=rank_position,
            score=score,
        )
        if not result.get('success'):
            return jsonify({'status': 'error', 'message': result.get('error') or 'Gagal menyimpan feedback'}), 400
        return jsonify({'status': 'success', 'feedback': result.get('feedback')}), 200
    except Exception as e:
        LOG_API.exception("api_recommend_feedback_upsert gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/recommend-by-preferences/feedback', methods=['GET'])
def api_recommend_feedback_get():
    """
    Ambil feedback user untuk set preferensi (+ opsional filter place_ids).
    Query: preferences=belajar,kerja & place_ids=id1,id2
    """
    try:
        auth_user, auth_error = require_authenticated_user()
        if auth_error is not None:
            return auth_error

        prefs_raw = request.args.get('preferences') or ''
        if ',' in prefs_raw:
            preferences = [p.strip() for p in prefs_raw.split(',') if p.strip()]
        elif prefs_raw.strip():
            preferences = [prefs_raw.strip()]
        else:
            preferences = []

        place_ids_raw = request.args.get('place_ids') or ''
        place_ids = [p.strip() for p in place_ids_raw.split(',') if p.strip()] or None

        feedback_map = get_user_feedback_map(auth_user.get('id'), preferences, place_ids=place_ids)
        return jsonify({
            'status': 'success',
            'preferences': preferences,
            'feedback_by_place_id': feedback_map,
        }), 200
    except Exception as e:
        LOG_API.exception("api_recommend_feedback_get gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/recommend-by-preferences/feedback/summary', methods=['GET'])
def api_recommend_feedback_summary():
    """
    Ringkasan evaluasi feedback (helpful vs not_helpful).
    Query opsional: preferences=belajar
    Membutuhkan login (dipakai evaluasi/admin tooling).
    """
    try:
        _auth_user, auth_error = require_authenticated_user()
        if auth_error is not None:
            return auth_error

        prefs_raw = request.args.get('preferences') or ''
        preferences = [p.strip() for p in prefs_raw.split(',') if p.strip()] or None
        try:
            limit = int(request.args.get('limit') or 200)
        except (TypeError, ValueError):
            limit = 200

        result = get_feedback_evaluation_summary(preferences=preferences, limit=limit)
        if not result.get('success'):
            return jsonify({'status': 'error', 'message': result.get('error') or 'Gagal mengambil ringkasan'}), 400
        return jsonify({
            'status': 'success',
            'counts': result.get('counts') or {},
            'not_helpful_recent': result.get('not_helpful_recent') or [],
        }), 200
    except Exception as e:
        LOG_API.exception("api_recommend_feedback_summary gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500



# Endpoint untuk cek status LLM availability (lightweight, no token usage)
@app.route('/api/llm/status', methods=['GET'])
def llm_status():
    """Check if LLM is available (HF and/or Gemini configured)"""
    from llm_backend import llm_provider_summary

    providers = llm_provider_summary()
    if llm_is_available():
        msg = f'LLM siap ({LLM_BACKEND})'
    else:
        msg = 'LLM nonaktif: set HF_API_TOKEN dan/atau GEMINI_API_KEY'
    return jsonify({
        'available': llm_is_available(),
        'backend': LLM_BACKEND,
        'providers': providers,
        'pipeline': full_pipeline_config(),
        'semantic_gate': semantic_gate_config(),
        'clause_sentiment': clause_sentiment_config(),
        'message': msg,
    })


@app.route('/health', methods=['GET'])
def health_check():
    """Health check ringkas untuk komponen utama runtime AI."""
    health = {
        'status': 'ok',
        'llm_available': llm_is_available(),
        'llm_backend': LLM_BACKEND,
        'rerank_backend': COFIND_RERANK_BACKEND,
        'llm_pipeline': full_pipeline_config(),
    }
    try:
        from redis_utils import get_redis_url, ping_redis
        health['redis_ok'] = ping_redis(timeout=2.0)
        health['redis_url_scheme'] = get_redis_url().split('://', 1)[0]
    except Exception as redis_err:
        health['redis_ok'] = False
        health['redis_error'] = str(redis_err)[:160]
    try:
        from celery_app import celery_app
        insp = celery_app.control.inspect(timeout=1.0)
        ping_resp = insp.ping() if insp else None
        health['celery_worker_ok'] = bool(ping_resp)
    except Exception:
        health['celery_worker_ok'] = False
    code = 200 if health['llm_available'] else 503
    return jsonify(health), code

# Ringkasan per toko sengaja TIDAK di-cache (lihat _generate_llm_review_summary):
# paragrafnya harus mengikuti kombinasi pill yang dipilih user saat itu. Dua helper
# di bawah tetap dipakai untuk kunci cache kesimpulan perbandingan.

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


# Cache penilaian rerank LLM (fit_score + alasan + kutipan per toko).
RERANK_CACHE_PATH = os.path.join(CACHE_DIR, 'rerank_cache.json')
RERANK_CACHE_VERSION = 'v3-pill-set'


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





if __name__ == '__main__':
    # Jalankan app secara langsung untuk pengembangan
    # Gunakan host 0.0.0.0 untuk bind ke semua interface; port default 5000 (override lewat FLASK_RUN_PORT / PORT untuk E2E)
    # Debug False untuk menghindari restart cycle saat development
    import logging

    logging.getLogger('werkzeug').setLevel(logging.INFO)
    _run_port = int(os.getenv('FLASK_RUN_PORT') or os.getenv('PORT') or '5000')
    app.run(debug=False, host='0.0.0.0', port=_run_port, threaded=True)

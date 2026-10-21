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
from free_text_intent import (
    MAX_FREE_TEXT_CHARS as FREE_TEXT_MAX_CHARS,
    extract_search_intent,
)
from free_text_query_handling import (
    QUERY_CLASS_FALSE_PRESUP,
    QUERY_CLASS_NEGATIVE,
    apply_false_presupposition_retrieval,
    merge_query_classification,
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
    from shop_search_store import ensure_coffee_shop_search_columns
    if ensure_coffee_shop_search_columns():
        LOG_STARTUP.info("Kolom coffee_shops review_tsv siap.")
except Exception as _fts_err:
    LOG_STARTUP.warning(f"Inisialisasi FTS coffee_shops gagal: {_fts_err}")

try:
    from review_embedding_store import ensure_review_embedding_vector_dim
    ensure_review_embedding_vector_dim()
except Exception as _emb_dim_err:
    LOG_STARTUP.warning(f"Selarasan dimensi pgvector: {_emb_dim_err}")

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
        response.headers["Access-Control-Allow-Origin"] = _CORS_ORIGINS[0]

    response.headers["Access-Control-Allow-Methods"] = ", ".join(_CORS_ALLOW_METHODS)
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


























































# Helper function untuk fetch coffee shops dengan REVIEWS dari file JSON lokal


# ============================================================================
# NEW RECOMMENDATION PIPELINE - Weighted Multi-Signal Scoring + LLM Reasoning
# ============================================================================

# Pill config: lihat pill_config.py

from recommendation.pipeline import recommendation_pipeline_events
from recommendation.evidence import _quote_is_caveat
from recommendation.helpers import (
    _attribute_quotes_from_reviews,
    _build_retrieval_evidence,
    _candidate_quotes_for_sentiment,
    _coerce_step5_summary_text,
    _extract_summary_field_loose,
    _invalid_llm_summary_reason,
    _llm_chat_for_pipeline,
    _matched_facility_from_gate,
    _merge_quote_rows,
    _parse_llm_json_with_repair,
    _plain_summary_from_llm_raw,
    _preference_keywords_for_evidence,
    _reset_clause_verdicts,
    _seed_search_keywords,
    _semantic_reference_terms,
    _set_clause_verdicts,
    _summary_sentence_count,
    rerank_cache_enabled,
)
from pill_config import PILL_MAPPING, PILL_LABELS, FACILITY_ATTRIBUTE_PILLS

# Backward compat untuk smoke/tests yang impor dari app
_recommendation_pipeline_events = recommendation_pipeline_events
from recommendation.request_prefs import read_recommendation_preferences as _read_recommendation_preferences

from pill_config import (
    FACILITY_ATTRIBUTE_PILLS,
    PILL_LABELS,
    PILL_MAPPING,
)

RATING_VOTE_WEIGHTS = {
    'love': 1.0,
    'like': 0.75,
    'ok': 0.5,
    'dislike': 0.25,
    'hate': 0.0,
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














# Endpoint rekomendasi: api/recommendation_routes.py (blueprint)


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



















if __name__ == '__main__':
    # Jalankan app secara langsung untuk pengembangan
    # Gunakan host 0.0.0.0 untuk bind ke semua interface; port default 5000 (override lewat FLASK_RUN_PORT / PORT untuk E2E)
    # Debug False untuk menghindari restart cycle saat development
    import logging

    logging.getLogger('werkzeug').setLevel(logging.INFO)
    _run_port = int(os.getenv('FLASK_RUN_PORT') or os.getenv('PORT') or '5000')
    app.run(debug=False, host='0.0.0.0', port=_run_port, threaded=True)

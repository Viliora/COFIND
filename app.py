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
    HF_MODEL,
    LLM_BACKEND,
    llm_chat_completions_create,
    llm_is_available,
)
from review_utils import (
    get_reviews_for_shop,
    get_reviews_for_recommendation_batch,
)
from vote_utils import migrate_review_ratings_to_votes, get_vote_summaries_batch
from recommendation_feedback_utils import (
    ensure_recommendation_feedback_table,
    upsert_recommendation_feedback,
    get_user_feedback_map,
    get_not_helpful_place_ids,
    get_feedback_evaluation_summary,
)
from preference_suggestion_utils import (
    ensure_preference_suggestions_table,
    create_preference_suggestion,
)
from slang_normalize import normalize_text_with_slang, tokenize_normalized
from hybrid_retrieval import (
    retrieve_top_k,
    retrieval_top_k,
    rank_reviews_for_query,
    text_matches_tokens,
    compute_pill_coverage,
    min_fit_score,
)
from llm_recommender import (
    build_user_taste_profile,
    format_user_taste_prompt_block,
    grounding_check_enabled as llm_grounding_check_enabled,
    llm_rerank_candidates,
    pipeline_config as llm_pipeline_config,
    rerank_candidate_pool as llm_rerank_pool,
    rerank_enabled as llm_rerank_enabled,
    shop_corpus_text,
    ungrounded_quotes,
)
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
COFIND_RECOMMEND_VERBOSE = os.getenv('COFIND_RECOMMEND_VERBOSE', 'false').strip().lower() in ('1', 'true', 'yes', 'on')
# Muat model embedding saat startup (thread terpisah) supaya request rekomendasi
# pertama tidak menanggung waktu load model. Default off untuk dev lokal.
COFIND_SEMANTIC_PRELOAD = os.getenv('COFIND_SEMANTIC_PRELOAD', 'false').strip().lower() in ('1', 'true', 'yes', 'on')

if COFIND_SEMANTIC_PRELOAD and semantic_gate_enabled():
    import threading

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
    if ensure_preference_suggestions_table():
        LOG_STARTUP.info("Table preference_suggestions siap.")
except Exception as _ps_err:
    LOG_STARTUP.warning(f"Inisialisasi preference_suggestions gagal: {_ps_err}")

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


def _parse_llm_json_with_repair(raw_text, *, expected='any', model=None):
    """
    Parse JSON output LLM, lalu sekali repair pass jika parse gagal.
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
    for _ in range(2):
        repaired = llm_chat_completions_create(
            model=(model or HF_MODEL or "meta-llama/Meta-Llama-3-8B").strip(),
            messages=repair_messages[:-1] + [{'role': 'user', 'content': f'Fix this into {shape_hint}:\n{repaired_text[:3200]}'}],
            max_tokens=320,
            temperature=0.0,
            top_p=0.9,
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


def _llm_chat_for_pipeline(*, messages, max_tokens, temperature):
    """Adapter chat completion untuk tahap keputusan LLM di llm_recommender."""
    return llm_chat_completions_create(
        model=_llm_model_id(),
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
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
        'facility_fields': {
            'popular_for': ['good_for_groups'],
        },
        'review_keywords': [
            'main game', 'gaming', 'game', 'ngegame', 'nge-game', 'nge game',
            'mobile legends', 'pubg', 'valorant', 'mabar', 'gas game',
            'turnamen', 'push rank', 'bermain game', 'mainbareng',
        ],
    },
    'meeting_sosialisasi': {
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
        'facility_fields': {
            'children': ['good_for_kids', 'kids_menu', 'high_chairs'],
            'popular_for': ['good_for_groups'],
            'crowd': ['keluarga', 'ramah_keluarga', 'berkelompok'],
        },
        'review_keywords': [
            'keluarga', 'anak', 'family', 'anak-anak', 'ramah keluarga',
            'cocok keluarga', 'bawa anak', 'family friendly',
            'berkumpul bersama', 'kumpul bersama', 'quality time',
            'ramah anak', 'playground', 'area bermain', 'kursi bayi', 'menu anak',
        ],
    },
    'instagrammable': {
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
    'area_non_smoking': {
        'facility_fields': {
            'amenities': ['non_smoking', 'no_smoking'],
        },
        'review_keywords': [
            'non smoking', 'no smoking', 'bebas asap', 'tidak berasap',
            'area bebas rokok', 'ruangan bebas rokok', 'smoking area terpisah',
            'tanpa asap rokok',
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
}

# Pill lapis 2 dibedakan dari pill aktivitas hanya saat validasi input & pembatasan
# jumlah; sisanya diperlakukan sama oleh pipeline.
# Nilainya harus sama dengan FACILITY_ATTRIBUTE_GROUPS di
# frontend-cofind/src/constants/reviewPills.js.
FACILITY_ATTRIBUTE_PILLS = frozenset({
    'ruangan_ac', 'suasana_tenang', 'area_non_smoking', 'smoking_area',
    'wifi_kencang', 'banyak_colokan_terminal', 'ruang_privat',
    'buka_sampai_malam_24_hours', 'musholla', 'parkir_luas', 'toilet_bersih',
})

PILL_LABELS = {
    'belajar': 'Belajar',
    # Label mengikuti teks tombol di frontend (CONTEXT_PILL_OPTIONS).
    'kerja': 'Kerja/WFC',
    'bermain game': 'Bermain game',
    'meeting_sosialisasi': 'Meeting/sosialisasi',
    'keluarga': 'Keluarga',
    'instagrammable': 'Instagrammable',
    # Label lapis 2 mengikuti teks di FACILITY_ATTRIBUTE_GROUPS (frontend).
    'ruangan_ac': 'Ruangan sejuk',
    'suasana_tenang': 'Suasana tenang',
    'area_non_smoking': 'Area non-smoking',
    'smoking_area': 'Smoking area',
    'wifi_kencang': 'Wifi kencang',
    'banyak_colokan_terminal': 'Banyak colokan / terminal',
    'ruang_privat': 'Ruang privat / meeting',
    'buka_sampai_malam_24_hours': '24 hours',
    'musholla': 'Ada musholla',
    'parkir_luas': 'Parkir luas',
    'toilet_bersih': 'Toilet bersih',
}

PILL_TO_BEST_FOR = {
    'belajar': 'belajar',
    'kerja': 'kerja',
    'bermain game': 'nge_game',
    'meeting_sosialisasi': 'meeting',
    'keluarga': 'family_time',
    'instagrammable': 'instagrammable',
}

BEST_FOR_PROMPT_LABELS = {
    'belajar': 'belajar',
    'kerja': 'kerja / WFC (work from cafe)',
    'nge_game': 'bermain game',
    'meeting': 'meeting',
    'family_time': 'keluarga',
    'instagrammable': 'instagrammable',
}

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
# Semua ranking, evidence, dan summary rekomendasi HANYA dibangun dari review
# user di tabel `reviews`. Tidak menggunakan facilities.json ataupun rating
# Google Maps sebagai sinyal peringkat. Data Google hanya untuk fallback
# tampilan nama/rating ketika toko belum punya review.
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
        'google_rating': float(shop_data.get('rating') or 0),
        'google_total_reviews': int(shop_data.get('total_reviews') or 0),
    }


def _build_profiles_for_recommendation(place_ids, facilities_index=None, excluded_place_ids=None):
    """
    Batch-load profil rekomendasi:
      1 query coffee_shops + 1 query reviews lean (tanpa foto/like).
    Return: (profiles, shops_without_reviews)
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
            f"SELECT place_id, name, rating, total_reviews FROM coffee_shops WHERE place_id IN ({placeholders})",
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
            "fallback per-shop get_reviews_for_shop")
        reviews_by_place = {}
        for pid in shops_by_id:
            one = get_reviews_for_shop(pid, limit=None)
            reviews_by_place[pid] = one.get('reviews', []) if one.get('success') else []

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
                    'best_for_counts': vote.get('best_for_counts') or {},
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
    """Span token inklusif tempat fragmen kelemahan muncul di line ter-normalisasi."""
    found = set()
    if not line or not tokens:
        return found
    for frag in _REVIEW_WEAKNESS_FRAGMENTS_SORTED:
        found.update(_find_keyword_token_spans(tokens, frag))
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
    Kelemahan terhadap preferensi: fragmen _REVIEW_WEAKNESS_FRAGMENTS dalam jendela
    gabungan (maks window token sebelum blok keyword + maks window sesudah),
    dengan blok = frasa utuh dari pill / review_keywords (atau search_keywords).
    """
    if window is None:
        window = _PREFERENCE_WEAKNESS_TOKEN_WINDOW
    if not preference_keywords:
        return False
    normalized_line = _normalize_keyword_phrase(text)
    if not normalized_line:
        return False
    tokens, spans = _split_tokens_with_spans(normalized_line)
    return _line_has_weakness_near_anchors(
        tokens, spans, normalized_line, preference_keywords, window,
    )


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
    return any(fragment in normalized for fragment in _REVIEW_WEAKNESS_FRAGMENTS)


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


def _quote_is_caveat(quote_text, preference_keywords):
    """
    True bila kutipan tidak layak dipakai sebagai bukti kecocokan.

    Tiga lapis, dari yang paling murah dan paling pasti:
      1. frasa "tidak/kurang cocok ..." — selalu caveat
      2. verdict LLM per klausa (bila kutipan ini termasuk yang diverifikasi)
      3. heuristik jendela token di sekitar keyword preferensi (fallback)
    """
    text = str(quote_text or '')
    if len(text.strip()) < 10:
        return False
    normalized = _normalize_keyword_phrase(text)
    # "kurang cocok / tidak disarankan" tidak pernah jadi bukti pendukung,
    # meski keyword pill tidak ada di kalimat yang sama.
    if normalized and any(phrase in normalized for phrase in _UNSUITABILITY_PHRASES):
        return True
    verdict = _quote_llm_verdict(text)
    if verdict is not None:
        return str(verdict.get('label')) in ('caveat', 'irrelevant')
    if preference_keywords:
        return _review_has_weakness_near_preference_keywords(text, preference_keywords)
    return _review_has_weakness_signal(text)


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
        return supporting, caveats
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
        if len(q) < 10:
            return
        k = q.lower()[:160]
        if k in seen:
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
    caveat_quotes = ev.get('modal_caveat_quotes') or ev.get('negative_review_quotes') or []
    first_caveat = ''
    for row in caveat_quotes:
        if isinstance(row, dict):
            first_caveat = _third_person_review_snippet(row.get('quote') or '', limit=100)
        if first_caveat:
            break
    closing_bits = []
    if first_caveat:
        closing_bits.append(f'Terdapat keluhan pengunjung mengenai {first_caveat}')
    if closing_bits:
        closer = '. '.join(closing_bits) + '.'
    else:
        closer = _no_complaint_summary_sentence()
    if ctx:
        return (
            f'{name} menurut ulasan pengunjung relevan untuk {ctx}, '
            f'terkait {themes}.{detail_line} {closer}'
        ).strip()
    return f'Pengunjung menyoroti {themes} tentang {name}.{detail_line} {closer}'.strip()


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
            if len(text) < 12:
                continue
            dedupe = text.lower()[:160]
            if dedupe in seen:
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
        if len(text) < 12:
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

    best_for_counts = vote.get('best_for_counts') or {}
    mapped_tags = [PILL_TO_BEST_FOR[p] for p in (pills or []) if p in PILL_TO_BEST_FOR]
    total_best = sum(int(v or 0) for v in best_for_counts.values())
    if mapped_tags and total_best > 0:
        aligned = sum(int(best_for_counts.get(tag) or 0) for tag in mapped_tags)
        parts.append(min(1.0, aligned / float(total_best)))
        weights.append(0.20)

    pros = data.get('top_pros') or []
    if pros:
        nets = [max(0, int(item.get('net') or 0)) for item in pros]
        avg_net = sum(nets) / max(1, len(nets))
        parts.append(min(1.0, avg_net / 8.0))
        weights.append(0.15)

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

    best_for_counts = vote.get('best_for_counts') or {}
    preferred_tags = [PILL_TO_BEST_FOR[p] for p in (pills or []) if p in PILL_TO_BEST_FOR]
    ranked_tags = sorted(
        ((tag, int(count or 0)) for tag, count in best_for_counts.items() if int(count or 0) > 0),
        key=lambda item: (-item[1], item[0]),
    )
    if preferred_tags:
        ranked_tags = [item for item in ranked_tags if item[0] in preferred_tags] + [
            item for item in ranked_tags if item[0] not in preferred_tags
        ]
    if ranked_tags:
        best_bits = [
            f'{BEST_FOR_PROMPT_LABELS.get(tag, tag)} ({count})'
            for tag, count in ranked_tags[:3]
        ]
        lines.append(f'{indent}Sering dipilih untuk: {", ".join(best_bits)}')

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
    weakness_lines = _weakness_quote_lines_for_prompt(ev, limit=2)

    weakness_block = ''
    if weakness_lines:
        weakness_block = (
            '\nKeluhan di ulasan (WAJIB disebut secara profesional di kalimat penutup):\n'
            + '\n'.join(weakness_lines)
            + '\n'
        )

    prompt = f"""Anda meringkas ulasan SATU coffee shop secara objektif (orang ketiga).
Tulis 1 paragraf 3-4 kalimat padat berdasarkan kutipan di bawah. Jangan menyalin kata saya/aku/kami.

Syarat:
- Kalimat pertama: nama {name} + kebutuhan "{ctx}" hanya jika kutipan mendukung
- 1-2 detail konkret dari kutipan (bukan hanya nyaman/cozy)
- Jika ada keluhan di data, wajib disebut secara profesional
- Jika ada kebutuhan user yang tidak dibahas: "Belum ada ulasan yang membahas terkait [kebutuhan]."
- Hanya tutup "Sejauh ini tidak ada keluhan berarti" jika data 100% positif dan semua kebutuhan terjawab
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
{chr(10).join(quote_lines)}
{weakness_block}"""
    prompt = _compact_prompt_block(prompt, 5600)

    try:
        raw = llm_chat_completions_create(
            model=(HF_MODEL or "meta-llama/Meta-Llama-3-8B").strip(),
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'Anda merangkum SATU coffee shop dari ulasan. '
                        'Orang ketiga, 3-4 kalimat, fakta saja. '
                        'Keluhan wajib disebut. Jangan klaim fasilitas tidak ada '
                        'hanya karena belum dibahas ulasan.'
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

    Sisanya (1 - nilai ini) disumbang lapis fasilitas. Nilai 0.6 berarti toko
    yang cocok aktivitasnya tapi belum terbukti fasilitasnya tetap unggul atas
    toko yang hanya terbukti fasilitasnya (cakupan 0), sesuai niat utama user.
    """
    raw = (os.getenv('COFIND_ACTIVITY_COVERAGE_SHARE') or '').strip()
    if not raw:
        return 0.6
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        return 0.6


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


_NO_COMPLAINT_SUMMARY_TAIL_RE = re.compile(
    r'(?:namun|tapi|tetapi)?\s*,?\s*'
    r'(?:perlu diingat bahwa\s+)?'
    r'(?:'
    r'.{0,80}?(?:tidak|belum)\s+'
    r'(?:ada|menyebutkan|menemukan|menyinggung).{0,80}?'
    r'(?:keluhan|kekurangan)'
    r'|'
    r'sejauh ini tidak ada keluhan berarti'
    r'|'
    r'sampai saat ini belum ada keluhan'
    r')',
    re.IGNORECASE,
)


def _no_complaint_summary_sentence(shop_name=None):
    return 'Sejauh ini tidak ada keluhan berarti.'


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


def _rewrite_no_complaint_summary_tail(summary, shop_name=None):
    """
    Seragamkan kalimat penutup 'tidak ada keluhan' agar tidak terdengar seperti
    penyangkalan panjang ('ulasan tidak menyebutkan kekurangan...').
    """
    text = _normalize_whitespace(summary)
    if not text:
        return text
    parts = [
        part.strip()
        for part in re.split(r'(?<=[.!?])\s+', text)
        if part.strip()
    ]
    if not parts:
        return text
    last = parts[-1]
    looks_like_absence = bool(_NO_COMPLAINT_SUMMARY_TAIL_RE.search(last))
    if not looks_like_absence:
        return text
    # Jangan timpa kalimat yang justru menyebut keluhan konkret.
    if re.search(r'\b(mengeluh|keluhan tentang|kurang positif|lelet|lemot|berisik)\b', last, re.I):
        if not re.search(r'\b(tidak|belum)\s+(ada|menyebutkan)\b', last, re.I):
            return text
    parts[-1] = _no_complaint_summary_sentence(shop_name)
    return _normalize_whitespace(' '.join(parts))


def _build_review_summary_deterministic(shop, pills):
    """Fallback summary (tanpa LLM) — paragraf naratif berbasis review."""
    # Kalimat pembuka hanya boleh menyebut pill yang PUNYA bukti, supaya tidak
    # bertabrakan dengan catatan penutup soal pill yang belum terbukti.
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
    negative_quotes = evidence.get('negative_review_quotes') or []
    avg = evidence.get('avg_user_rating')
    supporting_quotes, caveat_quotes = _collect_modal_quote_groups(
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
    weak_quote = (
        (caveat_quotes[0] if caveat_quotes else None)
        or (negative_quotes[0] if negative_quotes else None)
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

    uncovered_labels = _uncovered_pill_labels_for_shop(shop)
    closing_bits = []
    if weak_quote:
        weak = _third_person_review_snippet(weak_quote.get('quote') or '', limit=100)
        if weak:
            closing_bits.append(f'Terdapat keluhan pengunjung mengenai {weak}')
    if uncovered_labels:
        missing_phrase = _join_indonesian_topics(
            [_plain_pill_label(str(label)) for label in uncovered_labels]
        )
        closing_bits.append(
            f'Belum ada ulasan yang membahas terkait {missing_phrase}'
        )
    if closing_bits:
        caveat = '. '.join(closing_bits) + '.'
    else:
        caveat = _no_complaint_summary_sentence(shop_name)

    return _join_narrative_summary_parts(intro, strength, caveat)




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


def _uncovered_pill_labels_for_shop(shop):
    """
    Label pill yang diminta user tapi TIDAK punya bukti kutipan di toko ini.

    Dipakai untuk memaksa ringkasan menutup dengan catatan jujur, mis. toko yang
    cocok aktivitasnya tetapi tidak ada ulasan yang menyinggung fasilitas yang
    diminta.
    """
    detail = shop.get('score_detail') or {}
    return [PILL_LABELS.get(p, p) for p in (detail.get('uncovered_pills') or [])]


def _ensure_uncovered_note(summary, shop):
    """
    Jamin paragraf ditutup catatan jujur soal permintaan user yang belum ada bukti
    ulasannya.

    Instruksi prompt saja tidak cukup: model 8B kadang memilih menutup dengan
    keluhan lain, atau malah mengarang bahwa fasilitasnya "tidak ada" padahal yang
    benar hanya *belum ada ulasan yang membahasnya*. Catatan ini ditambahkan hanya
    bila paragraf belum menyebutkannya secara jujur, jadi tidak dobel.
    """
    labels = [l for l in (_plain_pill_label(x) for x in _uncovered_pill_labels_for_shop(shop)) if l]
    if not labels:
        return summary
    text = _normalize_whitespace(summary or '')
    low = text.lower()
    said_honestly = bool(re.search(r'belum ada (?:ulasan|yang|yg)', low))
    needed = [
        label for label in labels
        if not (said_honestly and label.split()[0] in low)
    ]
    if not needed:
        return text
    # Buang penutup "tidak ada keluhan" bila ada: catatan di bawah ini lebih
    # informatif, dan dua kalimat "belum ada ..." berurutan terdengar berulang.
    parts = [p.strip() for p in re.split(r'(?<=[.!?])\s+', text) if p.strip()]
    if parts and re.match(
        r'(sampai saat ini belum ada keluhan|sejauh ini tidak ada keluhan)',
        parts[-1],
        re.I,
    ):
        parts.pop()
    note = (
        f"Belum ada ulasan yang membahas terkait "
        f"{_join_indonesian_topics(needed)}."
    )
    parts.append(note)
    return _normalize_whitespace(' '.join(parts))


def _build_summary_output_entry(shop, summary, pills, search_keywords):
    """Bangun entri output rekomendasi yang seragam untuk semua jalur (cache/LLM/fallback)."""
    summary = _strip_structured_summary_labels(summary or '')
    summary = _rewrite_no_complaint_summary_tail(summary, shop.get('name'))
    if summary and summary[-1] not in '.!?':
        summary += '.'
    # Dipasang di sini (bukan di jalur LLM saja) supaya catatan kejujuran ini ikut
    # muncul lewat jalur fallback deterministik maupun LLM.
    summary = _ensure_uncovered_note(summary, shop)
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
    return {
        'place_id': shop['place_id'],
        'name': shop['name'],
        'score': shop.get('score', 0),
        'final_score': shop.get('final_score', shop.get('score', 0)),
        'ranking_source': 'llm' if llm_fit else 'hybrid',
        'llm_fit': llm_fit,
        'explanation': summary,
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


def _generate_llm_review_summary(top_shops, pills, search_keywords=None):
    """
    NLP summary per shop, **selalu** dibangkitkan ulang setiap request.

    Sengaja tanpa cache: ringkasan harus menyesuaikan kombinasi pill aktivitas +
    atribut fasilitas yang dipilih user saat itu, termasuk catatan pill mana yang
    belum terbukti di ulasan. Cache per (place_id + pill) dulu membuat paragraf
    lama ikut terbawa dan sempat mengunci satu paragraf yang salah nama toko.
    Jika LLM tidak tersedia / gagal parse, pakai fallback deterministik.
    Shop tanpa kutipan relevan dibuang dari output.
    """
    if not top_shops:
        return []

    search_keywords = _light_keyword_phrase_list(search_keywords or [])

    LOG_RECOMMEND.info(f"Summary: generate={len(top_shops)} (tanpa cache)")
    generated_summary_map = _llm_summaries_for_shops(
        top_shops, pills, search_keywords,
    )

    # Rakit output sesuai urutan asli; skip shop tanpa bukti kutipan.
    output = []
    for shop in top_shops:
        summary = (
            generated_summary_map.get(shop['place_id'])
            or _build_review_summary_deterministic(shop, pills)
        )
        entry = _build_summary_output_entry(shop, summary, pills, search_keywords)
        if entry is None:
            LOG_RECOMMEND.warning(
                f"Summary: drop {shop.get('name')} — tanpa modal_display_quotes")
            continue
        output.append(entry)
    return output


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


def _invalid_llm_summary_reason(summary, shop, all_shops):
    """Alasan menolak ringkasan LLM, atau None kalau lolos jaring pengaman."""
    if not summary:
        return 'summary kosong'
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


def _shop_summary_data_block(shop, pills, search_keywords):
    """
    Blok data SATU toko untuk prompt ringkasan.

    Sengaja pendek: kutipan relevan + keluhan + permintaan yang belum terbukti.
    Korpus penuh dan tab fasilitas dulu ikut dikirim dalam batch 3 toko, dan
    justru itu yang membuat model 8B mencampur fakta antar blok.
    """
    evidence = shop.get('evidence') or {}
    supporting_quotes, caveat_quotes = _collect_modal_quote_groups(
        evidence, pills, search_keywords=search_keywords,
    )
    relevant_quote_lines = _relevant_quote_lines_for_prompt(
        {'modal_display_quotes': supporting_quotes[:4]}, limit=4, char_limit=220,
    ) or ['- (tidak ada kutipan yang cocok konteks)']
    weakness_lines = _weakness_quote_lines_for_prompt(
        {'modal_caveat_quotes': caveat_quotes[:2]}, limit=2,
    ) or ['- (tidak ada keluhan menonjol)']

    uncovered_labels = _uncovered_pill_labels_for_shop(shop)
    uncovered_line = (
        ", ".join(_plain_pill_label(label) for label in uncovered_labels)
        if uncovered_labels else "(kosong — semua permintaan punya bukti ulasan)"
    )
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
    return (
        f"Tempat: {shop_name}\n"
        f"Aktivitas yang ADA bukti ulasannya: {covered_activity_line}\n"
        f"Permintaan user yang BELUM ada bukti ulasannya: {uncovered_line}\n"
        "Kutipan relevan (bukti utama — utamakan ini untuk kalimat pembuka):\n"
        + "\n".join(relevant_quote_lines) + "\n"
        "Keluhan di ulasan:\n" + "\n".join(weakness_lines)
    )


def _single_shop_summary_prompt(shop, pills, search_keywords, intent_line):
    """Prompt ringkas: satu toko, objektif, penanganan keluhan dan info kosong yang logis."""
    shop_name = shop.get('name') or 'Coffee shop ini'
    data_block = _compact_prompt_block(
        _shop_summary_data_block(shop, pills, search_keywords), 2200,
    )
    return (
        f"Tulis 1 paragraf (3-4 kalimat padat) tentang {shop_name} berdasarkan ulasan pelanggan.\n\n"
        f"Kebutuhan user: {intent_line}.\n\n"
        f"{data_block}\n\n"
        "Aturan Penulisan:\n"
        "1. Faktual & Objektif: Gunakan sudut pandang orang ketiga. JANGAN menyalin kata 'saya' atau 'kami' dari ulasan. Parafrase pengalaman personal menjadi ringkasan umum (misal: 'Terdapat keluhan pengunjung mengenai...').\n"
        "2. Kalimat Pembuka: Sebutkan nama tempat dan hubungkan dengan kebutuhan user (hanya jika didukung fakta ulasan).\n"
        "3. Detail Konkret: Tambahkan 1-2 fasilitas atau suasana spesifik yang ada di data ulasan (bukan klaim sepihak).\n"
        "4. Kalimat Penutup (Kekurangan & Info Kosong):\n"
        "   - Gabungkan informasi yang kurang dan/atau keluhan jika ada. \n"
        "   - Jika ada keluhan di data, WAJIB disebutkan secara profesional.\n"
        "   - Jika ada kebutuhan user yang tidak dibahas ulasan, sebutkan: 'Belum ada ulasan yang membahas terkait [kebutuhan].'\n"
        "   - HANYA gunakan penutup 'Sejauh ini tidak ada keluhan berarti' JIKA memang data 100% positif dan semua kebutuhan user terjawab.\n"
        "5. Output: Satu paragraf utuh yang mengalir, tanpa judul/label. \n\n"
        'Balas HANYA dengan JSON murni: {"summary":"..."}'
    )

def _parse_single_shop_summary(raw, shop):
    """Ambil teks summary dari JSON objek atau array 1 item."""
    parsed = _parse_llm_json_with_repair(
        raw,
        expected='any',
        model=_llm_model_id(),
    )
    if isinstance(parsed, dict):
        nested = parsed.get('recommendations') or parsed.get('items') or parsed.get('shops')
        items = nested if isinstance(nested, list) else [parsed]
    elif isinstance(parsed, list):
        items = parsed
    else:
        return ''
    assigned = _assign_llm_summaries_to_shops(items, [shop])
    return assigned.get(shop.get('place_id')) or ''


def _llm_summary_for_one_shop(shop, pills, search_keywords, intent_line, all_shops):
    """Satu panggilan LLM untuk satu toko. Kembalikan teks summary atau None."""
    prompt = _single_shop_summary_prompt(shop, pills, search_keywords, intent_line)
    LOG_RECOMMEND.info(
        f"Summary: kirim {shop.get('name')} "
        f"(prompt_chars={len(prompt)})...")
    t0 = time.perf_counter()
    try:
        raw = llm_chat_completions_create(
            model=_llm_model_id(),
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'Anda merangkum SATU coffee shop dari ulasan pelanggan. '
                        'Sudut pandang orang ketiga; jangan menyalin kata saya/aku/kami. '
                        'Satu paragraf 3-4 kalimat padat, fakta dari data saja. '
                        'Keluhan di data wajib disebut. Kebutuhan user yang tidak dibahas '
                        'ulasan disebut sebagai belum ada ulasan, bukan fasilitas tidak ada. '
                        'Jawab hanya JSON {"summary":"..."}.'
                    ),
                },
                {'role': 'user', 'content': prompt},
            ],
            max_tokens=400,
            temperature=0.2,
        )
        LOG_RECOMMEND.info(
            f"Summary: {shop.get('name')} siap "
            f"({round((time.perf_counter() - t0) * 1000, 1)} ms, "
            f"raw_chars={len(str(raw or ''))})")
        summary = _parse_single_shop_summary(raw, shop)
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


def _llm_summaries_for_shops(top_shops, pills, search_keywords=None):
    """
    Ringkasan per toko: SATU panggilan LLM per toko, dijalankan paralel.

    Satu toko per prompt menghapus risiko model mencampur nama/fakta antar
    kandidat. Aturan prompt dipangkas ke yang kritis; jaring pengaman kode
    (_ensure_uncovered_note, validasi negatif) tetap berlaku di pemanggil.
    """
    if not top_shops:
        return {}

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
    search_keywords = _light_keyword_phrase_list(search_keywords or [])

    if not llm_is_available():
        if COFIND_DEV_LLM_STRICT:
            raise RuntimeError('LLM strict mode aktif: summary butuh LLM tersedia.')
        LOG_RECOMMEND.warning("Summary: LLM tidak tersedia, pakai fallback deterministik")
        return {
            s['place_id']: _build_review_summary_deterministic(s, pills)
            for s in top_shops
        }

    workers = min(3, len(top_shops))
    LOG_RECOMMEND.info(
        f"Summary: {len(top_shops)} toko, 1 panggilan/toko, "
        f"paralel={workers}")

    generated = {}
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                _llm_summary_for_one_shop,
                shop,
                pills,
                search_keywords,
                intent_line,
                top_shops,
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
            summary = _build_review_summary_deterministic(shop, pills)
        result_map[shop['place_id']] = summary
    if skipped:
        LOG_RECOMMEND.warning(
            f"Summary: {len(top_shops) - skipped} LLM / {skipped} fallback "
            f"dari {len(top_shops)} toko")
    return result_map


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
            if len(text) < 12:
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


def _quote_texts_for_coverage(shop):
    evidence = shop.get('evidence') or {}
    display = evidence.get('modal_display_quotes') or []
    rows = display if display else (evidence.get('review_quotes') or [])
    texts = []
    for row in rows:
        if isinstance(row, dict):
            texts.append(row.get('quote') or '')
        else:
            texts.append(str(row or ''))
    fit = shop.get('llm_fit') if isinstance(shop.get('llm_fit'), dict) else {}
    if fit.get('evidence_quote'):
        texts.append(fit.get('evidence_quote'))
    return texts


def _attach_pill_coverage(shop, pills):
    """Set covered/uncovered dari teks kutipan yang benar-benar dikirim ke UI/LLM."""
    covered, uncovered = compute_pill_coverage(
        _quote_texts_for_coverage(shop),
        pills,
        pill_labels=PILL_LABELS,
        pill_mapping=PILL_MAPPING,
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


def _shop_has_activity_evidence(shop, activity_tokens):
    if not activity_tokens:
        return True
    fit = shop.get('llm_fit') if isinstance(shop.get('llm_fit'), dict) else {}
    if text_matches_tokens(str(fit.get('evidence_quote') or ''), activity_tokens):
        return True
    evidence = shop.get('evidence') or {}
    for key in ('modal_display_quotes', 'review_quotes'):
        for row in evidence.get(key) or []:
            quote = row.get('quote') if isinstance(row, dict) else str(row or '')
            if text_matches_tokens(quote or '', activity_tokens):
                return True
    return False


def _activity_quote_rows(evidence, pills, activity_tokens, *, limit=3):
    """Kutipan yang membahas aktivitas, urutan sudah dari rank_reviews_for_query."""
    pill = pills[0] if pills else ''
    rows = []
    seen = set()
    for row in (evidence or {}).get('review_quotes') or []:
        if not isinstance(row, dict):
            continue
        quote = (row.get('quote') or '').strip()
        if len(quote) < 12:
            continue
        if activity_tokens and not text_matches_tokens(quote, activity_tokens):
            continue
        marker = quote.lower()[:120]
        if marker in seen:
            continue
        seen.add(marker)
        item = dict(row)
        item['pill'] = pill
        item['pill_label'] = PILL_LABELS.get(pill, pill) if pill else 'Ulasan pengunjung'
        rows.append(item)
        if len(rows) >= limit:
            break
    return rows


def _build_retrieval_evidence(
    profile,
    pills,
    query_text='',
    query_tokens=None,
    activity_tokens=None,
    activity_query_text='',
    attribute_tokens=None,
):
    """Cuplikan review paling relevan; sinyal aktivitas diutamakan."""
    ranked = rank_reviews_for_query(
        profile.get('reviews') or [],
        query_text=query_text or '',
        query_tokens=query_tokens or [],
        activity_tokens=activity_tokens or [],
        activity_query_text=activity_query_text or '',
        attribute_tokens=attribute_tokens or [],
    )
    excerpts = []
    pill = pills[0] if pills else ''
    for review in ranked:
        if not isinstance(review, dict):
            continue
        text = _normalize_whitespace(review.get('text') or '')
        if len(text) < 15:
            continue
        excerpts.append({
            'pill': pill,
            'pill_label': PILL_LABELS.get(pill, pill) if pill else 'Ulasan pengunjung',
            'quote': _truncate_evidence_text(text, 400),
            'reason': 'ulasan relevan',
            'rating': review.get('rating'),
            'username': review.get('username') or review.get('full_name'),
            **_review_quote_detail_fields(review),
        })
    ev = _build_empty_supporting_evidence()
    ev.update({
        'review_quotes': excerpts,
        'category_ratings': profile.get('avg_category_ratings') or ev['category_ratings'],
        'avg_user_rating': profile.get('avg_user_rating'),
        'review_count': profile.get('review_count', 0),
        'google_rating': profile.get('google_rating'),
        'google_total_reviews': profile.get('google_total_reviews'),
        'community_signals': profile.get('community_signals') or {},
        'facilities_tab': profile.get('facilities_tab') or ev['facilities_tab'],
    })
    return ev


def _apply_llm_extracted_quotes(shop, pills, activity_tokens=None):
    """Isi kutipan tampilan: utamakan ulasan aktivitas, bukan wifi/parkir."""
    fit = shop.get('llm_fit') if isinstance(shop.get('llm_fit'), dict) else {}
    evidence = dict(shop.get('evidence') or _build_empty_supporting_evidence())
    supporting = str(fit.get('evidence_quote') or '').strip()
    caveat = str(fit.get('caveat_quote') or '').strip()
    reason = str(fit.get('reason') or '').strip() or 'cocok dengan preferensi'
    pill = pills[0] if pills else ''
    activity_rows = _activity_quote_rows(
        evidence, pills, activity_tokens, limit=3,
    )
    display = []
    if supporting and (
        not activity_tokens or text_matches_tokens(supporting, activity_tokens)
    ):
        display.append({
            'pill': pill,
            'pill_label': PILL_LABELS.get(pill, pill) if pill else 'Ulasan pengunjung',
            'quote': supporting,
            'reason': reason,
        })
        evidence['llm_extracted'] = True
    for row in activity_rows:
        marker = (row.get('quote') or '').strip().lower()[:120]
        if any((d.get('quote') or '').strip().lower()[:120] == marker for d in display):
            continue
        display.append(row)
        if len(display) >= 3:
            break
    if not display and supporting:
        display.append({
            'pill': pill,
            'pill_label': PILL_LABELS.get(pill, pill) if pill else 'Ulasan pengunjung',
            'quote': supporting,
            'reason': reason,
        })
        evidence['llm_extracted'] = True
    if display:
        evidence['modal_display_quotes'] = display[:3]
        evidence['llm_extracted'] = True
        if fit and display[0].get('quote'):
            fit = dict(fit)
            fit['evidence_quote'] = display[0]['quote']
            shop['llm_fit'] = fit
    if caveat:
        evidence['modal_caveat_quotes'] = [{
            'quote': caveat,
            'reason': 'catatan dari ulasan',
        }]
        evidence['llm_extracted'] = True
    shop['evidence'] = evidence
    return shop


def _select_top_shops(ranked_candidates, max_rec=3, activity_tokens=None):
    """
    Ambil 0–max_rec toko. Jangan mengisi slot dengan toko tanpa bukti aktivitas
    atau fit_score di bawah ambang.
    """
    threshold = min_fit_score()
    llm_ran = any(
        isinstance(shop.get('llm_fit'), dict) for shop in (ranked_candidates or [])
    )

    def _eligible(shop):
        if not _shop_has_activity_evidence(shop, activity_tokens):
            return False
        fit = shop.get('llm_fit') if isinstance(shop.get('llm_fit'), dict) else None
        if fit is None:
            return not llm_ran
        if llm_ran and not fit.get('selected'):
            return False
        try:
            score = float(fit.get('fit_score') or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        return score >= threshold

    picked = [shop for shop in (ranked_candidates or []) if _eligible(shop)]
    picked.sort(key=lambda item: -(item.get('final_score') or item.get('score') or 0))
    return picked[:max_rec]


def _recommendation_pipeline_events(prefs, _auth_user):
    """
    Pipeline RAG 3 fase. Input tetap pill dua lapis, tanpa teks bebas.

      Fase 1 — Hard filter: pill valid di PILL_MAPPING, exclude not_helpful,
               wajib minimal 1 review Cofind.
      Fase 2 — Hybrid retrieval: BM25 + embedding, gerbang aktivitas wajib.
               Fasilitas tambahan hanya penguat skor. Top 7 ke LLM.
      Fase 3 — LLM rerank: pilih 0–3 toko yang kutipannya mendukung aktivitas,
               ekstrak kutipan pendukung (bukan jendela ±6 token).

    Generator: yield ('progress', payload) di tiap batas tahap, lalu tepat satu
    ('result', (body_dict, status_code)) di akhir. Autentikasi dan parsing body
    dilakukan pemanggil supaya generator ini bebas dari request context Flask.
    """
    request_t0 = time.perf_counter()
    stage_t0 = request_t0
    stage_ms = {}
    semantic_budget_token = begin_semantic_encode_budget()
    try:
        if not prefs:
            yield ('result', ({
                'status': 'error',
                'message': 'Pilih minimal satu konteks aktivitas (pill).',
            }, 400))
            return

        valid_pills = [p for p in prefs if p in PILL_MAPPING]
        if not valid_pills:
            yield ('result', ({
                'status': 'error',
                'message': f'Preferensi tidak dikenali: {", ".join(prefs)}',
            }, 400))
            return

        if COFIND_DEV_LLM_STRICT and not llm_is_available():
            yield ('result', ({
                'status': 'error',
                'message': 'LLM strict mode aktif tetapi LLM tidak tersedia.',
                'recommendations': [],
            }, 503))
            return

        activity_pills, attribute_pills = _split_preference_pills(valid_pills)
        LOG_RECOMMEND.info(f"Pills: {valid_pills}")
        yield _recommendation_progress('start')

        # Soft personalization: jangan tampilkan shop yang user tandai tidak relevan
        # untuk set preferensi yang sama (feedback thumbs-down).
        excluded_place_ids = set()
        try:
            excluded_place_ids = get_not_helpful_place_ids(_auth_user.get('id'), valid_pills)
            if excluded_place_ids:
                LOG_RECOMMEND.info(
                    f"Exclude {len(excluded_place_ids)} shop dari feedback "
                    f"not_helpful user_id={_auth_user.get('id')}"
                )
        except Exception as fb_excl_err:
            LOG_RECOMMEND.warning(f"Gagal load feedback exclusion: {fb_excl_err}")

        # Konteks personalisasi (review sendiri + favorit) untuk tahap keputusan LLM.
        taste_profile = build_user_taste_profile(_auth_user.get('id'))
        user_taste_block = format_user_taste_prompt_block(taste_profile)

        all_place_ids = _load_all_place_ids()
        if not all_place_ids:
            yield ('result', ({'status': 'error', 'message': 'Data coffee shop kosong.'}, 500))
            return
        facilities_index = load_facilities_index()

        MAX_REC = 3

        # --- Fase 1: hard filter (pill valid, thumbs-down, min review) ---
        LOG_RECOMMEND.info("Fase 1: batch load profil + reviews...")
        profiles, shops_without_reviews = _build_profiles_for_recommendation(
            all_place_ids,
            facilities_index=facilities_index,
            excluded_place_ids=excluded_place_ids,
        )
        LOG_RECOMMEND.info(
            f"Fase 1 selesai: profiles={len(profiles)} "
            f"tanpa_review={len(shops_without_reviews)}")
        stage_ms['profile_load_ms'] = round((time.perf_counter() - stage_t0) * 1000, 1)
        stage_t0 = time.perf_counter()
        yield _recommendation_progress('profiles', shops_with_reviews=len(profiles))

        # --- Fase 2: Hybrid Retrieval (BM25 + dense) ---
        quality_by_place = {
            str(profile.get('place_id')): _quality_score_for_profile(profile)
            for profile in profiles
            if profile.get('place_id')
        }
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
        retrieval_telemetry = retrieval.get('telemetry') or {}
        query_tokens = retrieval.get('query_tokens') or []
        query_text = retrieval.get('query_text') or ''
        activity_tokens = retrieval.get('activity_tokens') or []
        attribute_tokens = retrieval.get('attribute_tokens') or []
        activity_query_text = retrieval.get('activity_query_text') or query_text
        search_keywords = query_tokens
        scored_candidates = []
        for item in retrieval.get('candidates') or []:
            profile = item.get('profile') or {}
            shop = {
                'place_id': item.get('place_id'),
                'name': item.get('name') or profile.get('name') or '',
                'score': item.get('score', 0),
                'profile': profile,
                'score_detail': item.get('score_detail') or {},
                'evidence': _build_retrieval_evidence(
                    profile,
                    valid_pills,
                    query_text=query_text,
                    query_tokens=query_tokens,
                    activity_tokens=activity_tokens,
                    activity_query_text=activity_query_text,
                    attribute_tokens=attribute_tokens,
                ),
            }
            _attach_pill_coverage(shop, valid_pills)
            scored_candidates.append(shop)
        stage_ms['hybrid_retrieval_ms'] = round((time.perf_counter() - stage_t0) * 1000, 1)
        stage_t0 = time.perf_counter()
        LOG_RECOMMEND.info(
            f"Fase 2 selesai: {len(scored_candidates)}/{retrieval_telemetry.get('kept_with_signal', 0)} "
            f"kandidat (gated={retrieval_telemetry.get('activity_gated')}, "
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

        # --- Fase 3: LLM rerank + ekstraksi kutipan/caveat (fallback: urutan hybrid) ---
        rerank_backend = 'hybrid'
        rerank_telemetry = {}
        ranked_candidates = scored_candidates
        keyword_line = query_text or ', '.join(query_tokens[:20])
        if scored_candidates and llm_is_available() and llm_rerank_enabled():
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
                chat_fn=_llm_chat_for_pipeline,
                parse_json_fn=_parse_llm_json_with_repair,
                user_taste_block=user_taste_block,
                keyword_line=keyword_line,
                cached_fits=cached_fits,
                max_candidates=retrieval_top_k(),
                activity_pills=activity_pills,
                activity_tokens=activity_tokens,
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
            max_rec=MAX_REC,
            activity_tokens=activity_tokens,
        )
        for shop in top_shops:
            _apply_llm_extracted_quotes(shop, valid_pills, activity_tokens=activity_tokens)
            _attach_pill_coverage(shop, valid_pills)
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
        recommendations = _generate_llm_review_summary(
            top_shops,
            valid_pills,
            search_keywords=query_tokens,
        )
        stage_ms['llm_summary_ms'] = round((time.perf_counter() - stage_t0) * 1000, 1)
        stage_ms['total_ms'] = round((time.perf_counter() - request_t0) * 1000, 1)
        LOG_METRIC.info(f"recommend_by_preferences {stage_ms}")
        LOG_RECOMMEND.info(
            f"Selesai: {len(recommendations)} rekomendasi dikirim ke client")

        yield _recommendation_progress('done', delivered=len(recommendations))
        yield ('result', ({
            'status': 'success',
            'preferences': valid_pills,
            'preference_activities': [p for p in valid_pills if p not in FACILITY_ATTRIBUTE_PILLS],
            'preference_attributes': [p for p in valid_pills if p in FACILITY_ATTRIBUTE_PILLS],
            'search_keywords': search_keywords,
            'llm_pipeline': {
                'config': llm_pipeline_config(),
                'retrieval': dict(retrieval_telemetry),
                'rerank': dict(rerank_telemetry, backend=rerank_backend),
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
        _reset_clause_verdicts(None)
        reset_semantic_encode_budget(semantic_budget_token)
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
    Normalisasi body request menjadi satu daftar pill.

    Dua lapis preferensi digabung: `preferences` (konteks aktivitas, maks 1) dan
    `attributes` (atribut fasilitas lapis 2, maks 3). Atribut yang terkirim di
    dalam `preferences` juga diterima agar klien lama/baru sama-sama jalan.
    """
    data = request.get_json(silent=True) or {}
    raw_prefs = _as_pill_list(data.get('preferences'))
    raw_attrs = _as_pill_list(data.get('attributes'))

    activities = [p for p in raw_prefs if p not in FACILITY_ATTRIBUTE_PILLS][:_MAX_ACTIVITY_PILLS]
    attributes = []
    for pill in raw_prefs + raw_attrs:
        if pill in FACILITY_ATTRIBUTE_PILLS and pill not in attributes:
            attributes.append(pill)
    return activities + attributes[:_MAX_ATTRIBUTE_PILLS]


@app.route('/api/recommend-by-preferences', methods=['POST'])
def api_recommend_by_preferences():
    """Rekomendasi pill (respons JSON sekali kirim). Progress diabaikan di sini."""
    prefs = _read_recommendation_preferences()
    auth_user, auth_error = require_authenticated_user()
    if auth_error is not None:
        return auth_error

    body, status = {'status': 'error', 'message': 'Pipeline tidak menghasilkan respons.'}, 500
    for kind, payload in _recommendation_pipeline_events(prefs, auth_user):
        if kind == 'result':
            body, status = payload
    return jsonify(body), status


def _sse_pack(event, payload):
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.route('/api/recommend-by-preferences/stream', methods=['POST'])
def api_recommend_by_preferences_stream():
    """
    Versi streaming dari rekomendasi pill: mengirim event `progress` tiap tahap
    pipeline, lalu satu event `result` berisi payload yang identik dengan endpoint
    JSON biasa. Klien memakai fetch + ReadableStream (bukan EventSource) karena
    butuh header Authorization.
    """
    prefs = _read_recommendation_preferences()
    auth_user, auth_error = require_authenticated_user()
    if auth_error is not None:
        return auth_error

    def generate():
        # Padding awal supaya proxy/browser tidak menahan byte pertama.
        yield ': cofind-stream\n\n'
        delivered_result = False
        try:
            for kind, payload in _recommendation_pipeline_events(prefs, auth_user):
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
    Simpan thumbs up/down untuk satu item rekomendasi pill.
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


@app.route('/api/preference-suggestions', methods=['POST'])
def api_create_preference_suggestion():
    """
    User login mengirim saran pill preferensi baru ke admin.
    Body: { label: string, description?: string }
    """
    try:
        auth_user, auth_error = require_authenticated_user()
        if auth_error is not None:
            return auth_error

        data = request.get_json(silent=True) or {}
        result = create_preference_suggestion(
            auth_user.get('id'),
            data.get('label'),
            description=data.get('description'),
        )
        if not result.get('success'):
            return jsonify({
                'status': 'error',
                'message': result.get('error') or 'Gagal mengirim saran preferensi',
            }), 400
        return jsonify({
            'status': 'success',
            'message': 'Saran preferensi berhasil dikirim ke admin.',
            'suggestion': result.get('suggestion'),
        }), 201
    except Exception as e:
        LOG_API.exception("api_create_preference_suggestion gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500






# Endpoint untuk cek status LLM availability (lightweight, no token usage)
@app.route('/api/llm/status', methods=['GET'])
def llm_status():
    """Check if LLM is available (HF_API_TOKEN configured)"""
    if llm_is_available():
        msg = f'LLM siap ({LLM_BACKEND})'
    else:
        msg = 'LLM nonaktif: set HF_API_TOKEN dan gunakan HF_LLM_BACKEND=inference'
    return jsonify({
        'available': llm_is_available(),
        'backend': LLM_BACKEND,
        'pipeline': llm_pipeline_config(),
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
        'llm_pipeline': llm_pipeline_config(),
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
    Kunci cache rerank: kombinasi pill + user + sidik jari kandidat.

    user_id wajib masuk kunci karena prompt rerank memuat konteks selera user
    (review sendiri + favorit). Tanpa itu, user kedua dengan pill sama akan
    memakai penilaian yang dipersonalisasi untuk user pertama.
    """
    blob = '\u241f'.join([
        _recommendation_summary_pill_key(pills),
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
    _run_port = int(os.getenv('FLASK_RUN_PORT') or os.getenv('PORT') or '5000')
    app.run(debug=False, host='0.0.0.0', port=_run_port, threaded=True)

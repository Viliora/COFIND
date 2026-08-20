from dotenv import load_dotenv

# Wajib sebelum import llm_backend: variabel HF_* dibaca saat modul dimuat.
load_dotenv()

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS
import os
import json
import re
import hashlib
import importlib
from collections import Counter
import time
from datetime import datetime
try:
    repair_json = importlib.import_module('json_repair').repair_json
except Exception:
    repair_json = None
from llm_backend import (
    HF_MODEL,
    LLM_BACKEND,
    llm_chat_completions_create,
    llm_is_available,
    llm_text_generation,
)
from auth_utils import signup, login, logout, verify_token, get_user_by_id, update_user_profile, update_password
from review_utils import (
    create_review,
    get_review,
    get_reviews_for_shop,
    get_reviews_for_recommendation_batch,
    get_user_reviews,
    get_latest_reviews,
    get_user_review_stats,
    update_review,
    delete_review,
    get_average_rating,
    toggle_review_like,
    create_review_report,
)
from vote_utils import get_user_vote, upsert_vote, get_vote_summary, migrate_review_ratings_to_votes, get_vote_summaries_batch
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
    list_preference_suggestions,
    update_preference_suggestion,
)
from slang_normalize import normalize_text_with_slang, tokenize_normalized, DOMAIN_CANONICAL_REPLACEMENTS
from bm25_utils import (
    build_query_tokens,
    build_bm25_index,
    score_shops_bm25,
    normalize_bm25_scores,
)
from llm_recommender import (
    build_user_taste_profile,
    corpus_vocabulary_from_tokens,
    expand_pill_keywords,
    format_user_taste_prompt_block,
    grounding_check_enabled as llm_grounding_check_enabled,
    llm_rerank_candidates,
    pipeline_config as llm_pipeline_config,
    rerank_enabled as llm_rerank_enabled,
    shop_corpus_text,
    ungrounded_quotes,
)
from pros_cons_utils import get_pros_cons, toggle_pros_cons_vote, maybe_refresh_pros_cons, get_top_voted_pros_batch
from favorites_utils import (
    add_favorite,
    remove_favorite,
    get_user_favorites,
    is_favorite,
    get_favorite_count,
)
from want_to_visit_utils import add_want_to_visit, remove_want_to_visit, get_user_want_to_visit, is_want_to_visit
from db_backend import dict_from_row, get_connection

# Initialize Flask app
app = Flask(__name__)

# Database: lihat db_backend.py (Supabase Postgres via DATABASE_URL / SUPABASE_DB_URL)
# Rerank: LLM menilai kandidat teratas hasil BM25 hybrid (lihat llm_recommender.py).
COFIND_RERANK_BACKEND = 'llm' if llm_rerank_enabled() else 'none'
COFIND_DEV_LLM_STRICT = os.getenv('COFIND_DEV_LLM_STRICT', 'false').strip().lower() in ('1', 'true', 'yes', 'on')
# Modal quote summary: default deterministik (tanpa LLM per toko). Set true untuk LLM.
COFIND_MODAL_QUOTE_LLM = os.getenv('COFIND_MODAL_QUOTE_LLM', 'false').strip().lower() in ('1', 'true', 'yes', 'on')
COFIND_RECOMMEND_VERBOSE = os.getenv('COFIND_RECOMMEND_VERBOSE', 'false').strip().lower() in ('1', 'true', 'yes', 'on')


try:
    _migrated_votes = migrate_review_ratings_to_votes()
    if _migrated_votes:
        print(f"[INFO] Migrasi rating review -> shop_votes: {_migrated_votes} baris diperbarui/dibuat.")
except Exception as _migrate_err:
    print(f"[WARN] Migrasi rating review -> shop_votes gagal: {_migrate_err}")

try:
    if ensure_recommendation_feedback_table():
        print("[INFO] Table recommendation_feedback siap.")
except Exception as _fb_err:
    print(f"[WARN] Inisialisasi recommendation_feedback gagal: {_fb_err}")

try:
    if ensure_preference_suggestions_table():
        print("[INFO] Table preference_suggestions siap.")
except Exception as _ps_err:
    print(f"[WARN] Inisialisasi preference_suggestions gagal: {_ps_err}")

# Konfigurasi LLM: lihat llm_backend.py (HF_LLM_BACKEND, HF_MODEL, HF_API_TOKEN, dll.)
print(f"[INFO] LLM backend aktif: {LLM_BACKEND} | model={HF_MODEL}")
print("[INFO] Database backend: postgresql (Supabase)")

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

# Root endpoint
@app.route('/')
def home():
    return jsonify({"message": "Welcome to COFIND API"})

# Test endpoint untuk debug
@app.route('/api/test', methods=['GET'])
def test_api():
    return jsonify({
        "status": "ok",
        "message": "Flask server is running",
        "timestamp": time.time(),
        "hf_client_ready": llm_is_available(),
        "llm_backend": LLM_BACKEND,
    })

# ============================================================================
# COFFEE SHOPS API ENDPOINTS
# ============================================================================

@app.route('/api/coffeeshops', methods=['GET'])
def get_coffeeshops():
    """Get all coffee shops from database (dengan jam operasional)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT c.*, COALESCE(o.hours_display, '') AS opening_hours_display
            FROM coffee_shops c
            LEFT JOIN opening_hours o ON c.place_id = o.place_id
            ORDER BY c.rating DESC
        """)
        rows = cursor.fetchall()
        
        shops = [dict_from_row(cursor, row) for row in rows]
        conn.close()
        
        return jsonify({
            'status': 'success',
            'data': shops,
            'total': len(shops)
        })
    except Exception as e:
        print(f"[ERROR] Failed to fetch coffeeshops: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/coffeeshops/<int:shop_id>', methods=['GET'])
def get_coffeeshop(shop_id):
    """Get specific coffee shop by ID (dengan jam operasional)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT c.*, COALESCE(o.hours_display, '') AS opening_hours_display
            FROM coffee_shops c
            LEFT JOIN opening_hours o ON c.place_id = o.place_id
            WHERE c.id = ?
        """, (shop_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': f'Coffee shop {shop_id} not found'
            }), 404
        data = dict_from_row(cursor, row)
        conn.close()
        return jsonify({
            'status': 'success',
            'data': data
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/coffeeshops/place/<place_id>', methods=['GET'])
def get_coffeeshop_by_place_id(place_id):
    """Get specific coffee shop by place_id (dengan jam operasional)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT c.*, COALESCE(o.hours_display, '') AS opening_hours_display
            FROM coffee_shops c
            LEFT JOIN opening_hours o ON c.place_id = o.place_id
            WHERE c.place_id = ?
        """, (place_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': f'Coffee shop {place_id} not found'
            }), 404

        data = dict_from_row(cursor, row)
        conn.close()
        return jsonify({
            'status': 'success',
            'data': data
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/coffeeshops/search', methods=['GET'])
def search_coffeeshops():
    """Search coffee shops by name"""
    query = request.args.get('q', '').strip()
    
    if not query or len(query) < 2:
        return jsonify({
            'status': 'error',
            'message': 'Search query must be at least 2 characters'
        }), 400
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        search_term = f"%{query}%"
        cursor.execute('''
            SELECT * FROM coffee_shops 
            WHERE name LIKE ? OR address LIKE ? 
            ORDER BY rating DESC
        ''', (search_term, search_term))
        
        rows = cursor.fetchall()
        shops = [dict_from_row(cursor, row) for row in rows]
        conn.close()
        
        return jsonify({
            'status': 'success',
            'data': shops,
            'total': len(shops),
            'query': query
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# ============================================================================
# AUTHENTICATION API ENDPOINTS
# ============================================================================

@app.route('/api/auth/signup', methods=['POST'])
def auth_signup():
    """Register new user"""
    try:
        data = request.get_json()
        result = signup(
            email=data.get('email'),
            username=data.get('username'),
            password=data.get('password'),
            full_name=data.get('full_name', '')
        )
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'user': result['user'],
                'token': result['token'],
                'expires_in': result['expires_in']
            }), 201
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 400
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    """Login user"""
    try:
        data = request.get_json()
        result = login(
            email=data.get('email'),
            password=data.get('password')
        )
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'user': result['user'],
                'token': result['token'],
                'expires_in': result['expires_in']
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 401
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/auth/verify', methods=['POST'])
def auth_verify():
    """Verify session token"""
    try:
        data = request.get_json()
        token = data.get('token') or request.headers.get('Authorization', '').replace('Bearer ', '')
        
        result = verify_token(token)
        
        if result['valid']:
            return jsonify({
                'status': 'success',
                'user': result['user']
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Invalid or expired token'
            }), 401
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    """Logout user"""
    try:
        data = request.get_json()
        token = data.get('token') or request.headers.get('Authorization', '').replace('Bearer ', '')
        
        result = logout(token)
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'message': 'Logged out successfully'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/auth/user', methods=['GET'])
def auth_get_user():
    """Get current user info"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            return jsonify({
                'status': 'error',
                'message': 'No token provided'
            }), 401
        
        result = verify_token(token)
        
        if not result['valid']:
            return jsonify({
                'status': 'error',
                'message': 'Invalid or expired token'
            }), 401
        
        return jsonify({
            'status': 'success',
            'user': result['user']
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/auth/update-profile', methods=['PUT'])
def auth_update_profile():
    """Update user profile"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            return jsonify({
                'status': 'error',
                'message': 'No token provided'
            }), 401
        
        result = verify_token(token)
        
        if not result['valid']:
            return jsonify({
                'status': 'error',
                'message': 'Invalid or expired token'
            }), 401
        
        user_id = result['user']['id']
        data = request.get_json()
        
        update_result = update_user_profile(
            user_id=user_id,
            full_name=data.get('full_name'),
            bio=data.get('bio'),
            avatar_url=data.get('avatar_url'),
            phone=data.get('phone')
        )
        
        if update_result['success']:
            # Get updated user
            updated_user = get_user_by_id(user_id)
            return jsonify({
                'status': 'success',
                'user': updated_user
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': update_result['error']
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/auth/update-password', methods=['PUT'])
def auth_update_password():
    """Update user password"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            return jsonify({
                'status': 'error',
                'message': 'No token provided'
            }), 401
        
        result = verify_token(token)
        
        if not result['valid']:
            return jsonify({
                'status': 'error',
                'message': 'Invalid or expired token'
            }), 401
        
        user_id = result['user']['id']
        data = request.get_json()
        
        update_result = update_password(
            user_id=user_id,
            old_password=data.get('old_password'),
            new_password=data.get('new_password')
        )
        
        if update_result['success']:
            return jsonify({
                'status': 'success',
                'message': 'Password updated successfully'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': update_result['error']
            }), 400
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# ============================================================================
# ADMIN API ENDPOINTS
# ============================================================================

def _extract_bearer_token():
    return request.headers.get('Authorization', '').replace('Bearer ', '').strip()


def _require_admin():
    token = _extract_bearer_token()
    if not token:
        return None, (jsonify({'status': 'error', 'message': 'No token provided'}), 401)

    auth_result = verify_token(token)
    if not auth_result.get('valid'):
        return None, (jsonify({'status': 'error', 'message': 'Invalid or expired token'}), 401)

    user = auth_result.get('user') or {}
    if not user.get('is_admin'):
        return None, (jsonify({'status': 'error', 'message': 'Admin access required'}), 403)

    return user, None


def _require_authenticated_user():
    """Pengguna login (bukan admin-only): token sesi valid."""
    token = _extract_bearer_token()
    if not token:
        return None, (jsonify({
            'status': 'error',
            'message': 'Login diperlukan.',
        }), 401)

    auth_result = verify_token(token)
    if not auth_result.get('valid'):
        return None, (jsonify({
            'status': 'error',
            'message': 'Sesi tidak valid atau kadaluarsa. Silakan login lagi.',
        }), 401)

    user = auth_result.get('user')
    if not user or not user.get('id'):
        return None, (jsonify({
            'status': 'error',
            'message': 'Sesi tidak valid. Silakan login lagi.',
        }), 401)

    return user, None


def _load_facilities_index():
    facilities_path = os.path.join('frontend-cofind', 'src', 'data', 'facilities.json')
    if not os.path.exists(facilities_path):
        return {}
    try:
        with open(facilities_path, 'r', encoding='utf-8') as f:
            return json.load(f).get('facilities_by_place_id', {})
    except Exception as e:
        print(f"[ADMIN] Failed to load facilities.json: {e}")
        return {}


def _save_facilities_index(facilities_index):
    facilities_path = os.path.join('frontend-cofind', 'src', 'data', 'facilities.json')
    with open(facilities_path, 'w', encoding='utf-8') as f:
        json.dump({'facilities_by_place_id': facilities_index}, f, ensure_ascii=False, indent=2)


def _default_facilities_entry(place_id, shop_name=''):
    return {
        'place_id': place_id,
        'name': shop_name or '',
        'facilities': {
            'service_options': {},
            'accessibility': {},
            'highlights': {},
            'popular_for': {},
            'atmosphere': [],
            'crowd': [],
            'dining_options': {},
            'offerings': {},
            'amenities': {},
            'planning': {},
            'parking': {},
            'payments': {},
            'meta': {
                'source': 'admin_editor',
                'last_updated': datetime.utcnow().strftime('%Y-%m-%d'),
            },
        },
    }


def _paginate_query(cursor, base_query, params, page, per_page):
    offset = (page - 1) * per_page
    rows = cursor.execute(
        f"{base_query} LIMIT ? OFFSET ?",
        [*params, per_page, offset]
    ).fetchall()
    return rows


def _count_enabled_facilities(facilities_obj):
    if not facilities_obj:
        return 0
    count = 0
    for value in facilities_obj.values():
        if isinstance(value, dict):
            count += sum(1 for item in value.values() if item is True)
        elif isinstance(value, list):
            count += len(value)
    return count


@app.route('/api/admin/dashboard', methods=['GET'])
def admin_dashboard():
    admin_user, error_response = _require_admin()
    if error_response:
        return error_response

    def _normalize_activity_created_at(value):
        """Samakan created_at ke ISO string agar aman untuk sort + JSON."""
        if value is None:
            return ''
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    def _safe_int(value, default=0):
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return default

    def _fetch_count_map(sql, params=()):
        rows = cursor.execute(sql, params).fetchall()
        result = {}
        for row in rows or []:
            rd = dict_from_row(cursor, row) or {}
            key = rd.get('key')
            if key is None and len(row) >= 2:
                key = row[0]
            result[str(key or '')] = _safe_int(rd.get('cnt') if 'cnt' in rd else (row[1] if len(row) > 1 else 0))
        return result

    try:
        conn = get_connection()
        cursor = conn.cursor()

        stats = {
            'total_users': cursor.execute('SELECT COUNT(*) FROM users').fetchone()[0],
            'total_facilities': cursor.execute('SELECT COUNT(*) FROM coffee_shops').fetchone()[0],
            'total_reviews': cursor.execute('SELECT COUNT(*) FROM reviews').fetchone()[0],
            'total_review_reports': cursor.execute('SELECT COUNT(*) FROM review_reports').fetchone()[0],
            'pending_reports': cursor.execute(
                "SELECT COUNT(*) FROM review_reports WHERE LOWER(COALESCE(status, 'pending')) = 'pending'"
            ).fetchone()[0],
        }

        # --- Feedback rekomendasi LLM (helpful / not_helpful) ---
        recommendation_feedback = {
            'helpful': 0,
            'not_helpful': 0,
            'total': 0,
            'helpful_rate': None,
            'unique_users': 0,
        }
        try:
            ensure_recommendation_feedback_table()
            vote_map = _fetch_count_map(
                '''
                SELECT vote AS key, COUNT(*) AS cnt
                FROM recommendation_feedback
                GROUP BY vote
                '''
            )
            recommendation_feedback['helpful'] = vote_map.get('helpful', 0)
            recommendation_feedback['not_helpful'] = vote_map.get('not_helpful', 0)
            recommendation_feedback['total'] = (
                recommendation_feedback['helpful'] + recommendation_feedback['not_helpful']
            )
            if recommendation_feedback['total'] > 0:
                recommendation_feedback['helpful_rate'] = round(
                    100.0 * recommendation_feedback['helpful'] / recommendation_feedback['total'],
                    1,
                )
            recommendation_feedback['unique_users'] = _safe_int(
                cursor.execute(
                    'SELECT COUNT(DISTINCT user_id) FROM recommendation_feedback'
                ).fetchone()[0]
            )
        except Exception as fb_err:
            print(f"[WARN] dashboard recommendation_feedback: {fb_err}")

        feedback_by_preference = []
        try:
            pref_rows = cursor.execute(
                '''
                SELECT preferences_key,
                       SUM(CASE WHEN vote = 'helpful' THEN 1 ELSE 0 END) AS helpful,
                       SUM(CASE WHEN vote = 'not_helpful' THEN 1 ELSE 0 END) AS not_helpful,
                       COUNT(*) AS total
                FROM recommendation_feedback
                GROUP BY preferences_key
                ORDER BY total DESC
                LIMIT 8
                '''
            ).fetchall()
            for row in pref_rows or []:
                rd = dict_from_row(cursor, row) or {}
                feedback_by_preference.append({
                    'preferences_key': rd.get('preferences_key') or '(kosong)',
                    'helpful': _safe_int(rd.get('helpful')),
                    'not_helpful': _safe_int(rd.get('not_helpful')),
                    'total': _safe_int(rd.get('total')),
                })
        except Exception as pref_err:
            print(f"[WARN] dashboard feedback_by_preference: {pref_err}")

        # --- Kontribusi user terhadap pengayaan coffee shop (review + foto) ---
        top_contributors = []
        try:
            contrib_rows = cursor.execute(
                '''
                SELECT u.id AS user_id,
                       u.username,
                       COUNT(r.id) AS review_count,
                       COALESCE(SUM(photo_counts.photo_count), 0) AS photo_count,
                       COUNT(DISTINCT r.place_id) AS shop_count
                FROM users u
                INNER JOIN reviews r ON r.user_id = u.id
                LEFT JOIN (
                    SELECT review_id, COUNT(*) AS photo_count
                    FROM review_photos
                    GROUP BY review_id
                ) photo_counts ON photo_counts.review_id = r.id
                WHERE COALESCE(u.is_admin, 0) = 0
                GROUP BY u.id, u.username
                ORDER BY review_count DESC, photo_count DESC
                LIMIT 8
                '''
            ).fetchall()
            for row in contrib_rows or []:
                rd = dict_from_row(cursor, row) or {}
                top_contributors.append({
                    'user_id': rd.get('user_id'),
                    'username': rd.get('username') or 'Anonim',
                    'review_count': _safe_int(rd.get('review_count')),
                    'photo_count': _safe_int(rd.get('photo_count')),
                    'shop_count': _safe_int(rd.get('shop_count')),
                })
        except Exception as contrib_err:
            print(f"[WARN] dashboard top_contributors: {contrib_err}")

        most_reviewed_shops = []
        try:
            shop_rows = cursor.execute(
                '''
                SELECT c.place_id,
                       c.name AS shop_name,
                       COUNT(r.id) AS review_count,
                       COUNT(DISTINCT r.user_id) AS unique_reviewers
                FROM coffee_shops c
                INNER JOIN reviews r ON r.place_id = c.place_id
                GROUP BY c.place_id, c.name
                ORDER BY review_count DESC
                LIMIT 8
                '''
            ).fetchall()
            for row in shop_rows or []:
                rd = dict_from_row(cursor, row) or {}
                most_reviewed_shops.append({
                    'place_id': rd.get('place_id'),
                    'shop_name': rd.get('shop_name') or rd.get('place_id') or 'Coffee Shop',
                    'review_count': _safe_int(rd.get('review_count')),
                    'unique_reviewers': _safe_int(rd.get('unique_reviewers')),
                })
        except Exception as shop_err:
            print(f"[WARN] dashboard most_reviewed_shops: {shop_err}")

        # --- Tren review 14 hari terakhir ---
        reviews_trend = []
        try:
            from db_backend import use_postgres
            if use_postgres():
                trend_rows = cursor.execute(
                    '''
                    SELECT TO_CHAR(DATE(created_at), 'YYYY-MM-DD') AS day_key,
                           COUNT(*) AS cnt
                    FROM reviews
                    WHERE created_at >= (CURRENT_DATE - INTERVAL '13 days')
                    GROUP BY DATE(created_at)
                    ORDER BY DATE(created_at)
                    '''
                ).fetchall()
            else:
                trend_rows = cursor.execute(
                    '''
                    SELECT date(created_at) AS day_key, COUNT(*) AS cnt
                    FROM reviews
                    WHERE date(created_at) >= date('now', '-13 days')
                    GROUP BY date(created_at)
                    ORDER BY date(created_at)
                    '''
                ).fetchall()
            trend_map = {}
            for row in trend_rows or []:
                rd = dict_from_row(cursor, row) or {}
                day_key = str(rd.get('day_key') or (row[0] if row else '') or '')[:10]
                trend_map[day_key] = _safe_int(rd.get('cnt') if 'cnt' in rd else (row[1] if len(row) > 1 else 0))

            from datetime import timedelta
            today = datetime.utcnow().date()
            for offset in range(13, -1, -1):
                day = today - timedelta(days=offset)
                key = day.isoformat()
                reviews_trend.append({
                    'date': key,
                    'label': day.strftime('%d/%m'),
                    'count': trend_map.get(key, 0),
                })
        except Exception as trend_err:
            print(f"[WARN] dashboard reviews_trend: {trend_err}")

        # --- Saran preferensi pill ---
        preference_suggestions = {
            'pending': 0,
            'reviewed': 0,
            'accepted': 0,
            'rejected': 0,
            'total': 0,
        }
        try:
            ensure_preference_suggestions_table()
            sug_map = _fetch_count_map(
                '''
                SELECT COALESCE(status, 'pending') AS key, COUNT(*) AS cnt
                FROM preference_suggestions
                GROUP BY COALESCE(status, 'pending')
                '''
            )
            for key in ('pending', 'reviewed', 'accepted', 'rejected'):
                preference_suggestions[key] = sug_map.get(key, 0)
            preference_suggestions['total'] = sum(
                preference_suggestions[k] for k in ('pending', 'reviewed', 'accepted', 'rejected')
            )
        except Exception as sug_err:
            print(f"[WARN] dashboard preference_suggestions: {sug_err}")

        # --- Ringkasan aktivitas (hanya review & laporan; user baru tidak ditonjolkan) ---
        activities = []

        recent_reviews = cursor.execute('''
            SELECT r.id, u.username, c.name AS shop_name, r.created_at
            FROM reviews r
            LEFT JOIN users u ON u.id = r.user_id
            LEFT JOIN coffee_shops c ON c.place_id = r.place_id
            ORDER BY r.created_at DESC
            LIMIT 5
        ''').fetchall()
        for row in recent_reviews:
            rd = dict_from_row(cursor, row)
            activities.append({
                'type': 'review',
                'title': f"Review baru untuk {rd['shop_name'] or 'Coffee Shop'}",
                'description': f"Oleh {rd['username'] or 'Anonim'}",
                'created_at': _normalize_activity_created_at(rd['created_at']),
            })

        recent_reports = cursor.execute('''
            SELECT rr.id, rr.report_reason, rr.status, rr.created_at, c.name AS shop_name
            FROM review_reports rr
            LEFT JOIN reviews r ON r.id = rr.review_id
            LEFT JOIN coffee_shops c ON c.place_id = r.place_id
            ORDER BY rr.created_at DESC
            LIMIT 5
        ''').fetchall()
        for row in recent_reports:
            rd = dict_from_row(cursor, row)
            activities.append({
                'type': 'report',
                'title': f"Laporan review: {rd['report_reason'] or 'Tanpa alasan'}",
                'description': f"{rd['shop_name'] or 'Coffee Shop'} • status {rd['status'] or 'pending'}",
                'created_at': _normalize_activity_created_at(rd['created_at']),
            })

        activities = sorted(
            activities,
            key=lambda item: item.get('created_at') or '',
            reverse=True
        )[:6]

        conn.close()

        return jsonify({
            'status': 'success',
            'stats': stats,
            'charts': {
                'recommendation_feedback': recommendation_feedback,
                'feedback_by_preference': feedback_by_preference,
                'top_contributors': top_contributors,
                'most_reviewed_shops': most_reviewed_shops,
                'reviews_trend': reviews_trend,
                'preference_suggestions': preference_suggestions,
            },
            'recent_activity': activities,
            'admin': {
                'id': admin_user.get('id'),
                'username': admin_user.get('username'),
            }
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/users', methods=['GET'])
def admin_get_users():
    _, error_response = _require_admin()
    if error_response:
        return error_response

    try:
        page = max(int(request.args.get('page', 1)), 1)
        per_page = min(max(int(request.args.get('per_page', 10)), 1), 100)
        search = (request.args.get('search') or '').strip().lower()
        role_filter = (request.args.get('role') or '').strip().lower()
        status_filter = (request.args.get('status') or '').strip().lower()

        conn = get_connection()
        cursor = conn.cursor()

        where_clauses = []
        params = []

        if search:
            where_clauses.append('(LOWER(u.username) LIKE ? OR LOWER(u.email) LIKE ? OR LOWER(COALESCE(p.full_name, "")) LIKE ?)')
            like = f'%{search}%'
            params.extend([like, like, like])

        if role_filter == 'admin':
            where_clauses.append('u.is_admin = 1')
        elif role_filter == 'user':
            where_clauses.append('u.is_admin = 0')

        if status_filter == 'active':
            where_clauses.append('CAST(u.is_active AS INTEGER) = 1')
        elif status_filter == 'inactive':
            where_clauses.append('CAST(u.is_active AS INTEGER) = 0')

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ''

        count_row = cursor.execute(
            f'''
            SELECT COUNT(*)
            FROM users u
            LEFT JOIN user_profiles p ON p.user_id = u.id
            {where_sql}
            ''',
            params
        ).fetchone()
        total = count_row[0] if count_row else 0

        rows = _paginate_query(
            cursor,
            f'''
            SELECT u.id, u.email, u.username, u.is_admin, u.is_active, u.created_at, u.updated_at,
                   p.full_name, p.bio, p.phone
            FROM users u
            LEFT JOIN user_profiles p ON p.user_id = u.id
            {where_sql}
            ORDER BY u.created_at DESC
            ''',
            params,
            page,
            per_page
        )
        row_dicts = [dict_from_row(cursor, row) for row in rows]

        users = []
        for rd in row_dicts:
            review_count = cursor.execute('SELECT COUNT(*) FROM reviews WHERE user_id = ?', (rd['id'],)).fetchone()[0]
            favorite_count = cursor.execute('SELECT COUNT(*) FROM favorites WHERE user_id = ?', (rd['id'],)).fetchone()[0]
            want_count = cursor.execute('SELECT COUNT(*) FROM want_to_visit WHERE user_id = ?', (rd['id'],)).fetchone()[0]
            users.append({
                'id': rd['id'],
                'email': rd['email'],
                'username': rd['username'],
                'is_admin': bool(rd['is_admin']),
                'is_active': bool(rd['is_active']),
                'created_at': rd['created_at'],
                'updated_at': rd['updated_at'],
                'full_name': rd['full_name'],
                'bio': rd['bio'],
                'phone': rd['phone'],
                'review_count': review_count,
                'favorite_count': favorite_count,
                'want_to_visit_count': want_count,
            })

        conn.close()

        return jsonify({
            'status': 'success',
            'items': users,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': max((total + per_page - 1) // per_page, 1),
            }
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/users/<int:user_id>', methods=['PUT'])
def admin_update_user(user_id):
    admin_user, error_response = _require_admin()
    if error_response:
        return error_response

    try:
        data = request.get_json() or {}

        conn = get_connection()
        cursor = conn.cursor()

        existing = cursor.execute('SELECT id FROM users WHERE id = ?', (user_id,)).fetchone()
        if not existing:
            conn.close()
            return jsonify({'status': 'error', 'message': 'User not found'}), 404

        new_username = (data.get('username') or '').strip()
        if new_username:
            cursor.execute('UPDATE users SET username = ?, updated_at = ? WHERE id = ?', (
                new_username,
                datetime.utcnow().isoformat(),
                user_id,
            ))

        if 'is_admin' in data:
            if user_id == admin_user.get('id') and not data.get('is_admin'):
                conn.close()
                return jsonify({'status': 'error', 'message': 'Anda tidak dapat mencabut role admin dari akun sendiri.'}), 400
            cursor.execute('UPDATE users SET is_admin = ?, updated_at = ? WHERE id = ?', (
                1 if data.get('is_admin') else 0,
                datetime.utcnow().isoformat(),
                user_id,
            ))

        if 'is_active' in data:
            if user_id == admin_user.get('id') and not data.get('is_active'):
                conn.close()
                return jsonify({'status': 'error', 'message': 'Anda tidak dapat menonaktifkan akun sendiri.'}), 400
            cursor.execute('UPDATE users SET is_active = ?, updated_at = ? WHERE id = ?', (
                1 if data.get('is_active') else 0,
                datetime.utcnow().isoformat(),
                user_id,
            ))

        conn.commit()
        conn.close()

        update_user_profile(
            user_id=user_id,
            full_name=data.get('full_name'),
            bio=data.get('bio'),
            avatar_url=data.get('avatar_url'),
            phone=data.get('phone'),
        )
        return jsonify({'status': 'success', 'message': 'User updated successfully'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/users', methods=['POST'])
def admin_create_user():
    from auth_utils import hash_password as _hash_password
    admin_user, error_response = _require_admin()
    if error_response:
        return error_response

    try:
        data = request.get_json() or {}
        email = (data.get('email') or '').strip().lower()
        username = (data.get('username') or '').strip()
        password = (data.get('password') or '').strip()
        full_name = (data.get('full_name') or '').strip()
        is_admin_flag = bool(data.get('is_admin', False))

        if not email or not username or not password:
            return jsonify({'status': 'error', 'message': 'Email, username, dan password wajib diisi.'}), 400
        if len(password) < 6:
            return jsonify({'status': 'error', 'message': 'Password minimal 6 karakter.'}), 400

        conn = get_connection()
        cursor = conn.cursor()

        if cursor.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone():
            conn.close()
            return jsonify({'status': 'error', 'message': 'Email sudah terdaftar.'}), 400
        if cursor.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone():
            conn.close()
            return jsonify({'status': 'error', 'message': 'Username sudah digunakan.'}), 400

        pwd_hash = _hash_password(password)
        cursor.execute(
            'INSERT INTO users (email, username, password_hash, is_admin, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, 1, ?, ?)',
            (email, username, pwd_hash, 1 if is_admin_flag else 0,
             datetime.utcnow().isoformat(), datetime.utcnow().isoformat())
        )
        user_id = cursor.lastrowid
        cursor.execute(
            'INSERT INTO user_profiles (user_id, full_name) VALUES (?, ?)',
            (user_id, full_name or username)
        )
        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'message': 'User berhasil dibuat.', 'id': user_id}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
def admin_delete_user(user_id):
    admin_user, error_response = _require_admin()
    if error_response:
        return error_response

    try:
        if user_id == admin_user.get('id'):
            return jsonify({'status': 'error', 'message': 'Anda tidak dapat menghapus akun admin sendiri.'}), 400

        conn = get_connection()
        cursor = conn.cursor()

        existing = cursor.execute('SELECT id FROM users WHERE id = ?', (user_id,)).fetchone()
        if not existing:
            conn.close()
            return jsonify({'status': 'error', 'message': 'User tidak ditemukan.'}), 404

        cursor.execute('DELETE FROM sessions WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM review_likes WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM favorites WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM want_to_visit WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM review_reports WHERE reported_by_user_id = ?', (user_id,))
        cursor.execute('DELETE FROM reviews WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM user_profiles WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'message': 'User berhasil dihapus.'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/shops', methods=['GET'])
def admin_get_shops():
    _, error_response = _require_admin()
    if error_response:
        return error_response

    try:
        page = max(int(request.args.get('page', 1)), 1)
        per_page = min(max(int(request.args.get('per_page', 10)), 1), 100)
        search = (request.args.get('search') or '').strip().lower()

        conn = get_connection()
        cursor = conn.cursor()
        facilities_index = _load_facilities_index()

        where_sql = ''
        params = []
        if search:
            where_sql = 'WHERE LOWER(c.name) LIKE ? OR LOWER(c.address) LIKE ?'
            like = f'%{search}%'
            params = [like, like]

        total = cursor.execute(
            f'''
            SELECT COUNT(*)
            FROM coffee_shops c
            {where_sql}
            ''',
            params
        ).fetchone()[0]

        rows = _paginate_query(
            cursor,
            f'''
            SELECT c.*, COALESCE(o.hours_display, '') AS opening_hours_display
            FROM coffee_shops c
            LEFT JOIN opening_hours o ON o.place_id = c.place_id
            {where_sql}
            ORDER BY c.name ASC
            ''',
            params,
            page,
            per_page
        )

        items = []
        for row in rows:
            rd = dict_from_row(cursor, row)
            facility_entry = facilities_index.get(rd['place_id'], {})
            facilities_text = _format_facilities_to_text(facility_entry)
            facilities_obj = facility_entry.get('facilities', {})
            items.append({
                'id': rd['id'],
                'place_id': rd['place_id'],
                'name': rd['name'],
                'address': rd['address'],
                'rating': rd['rating'],
                'total_reviews': rd['total_reviews'],
                'latitude': rd['latitude'],
                'longitude': rd['longitude'],
                'map_embed_url': rd['map_embed_url'],
                'opening_hours_display': rd['opening_hours_display'],
                'has_facilities': bool(facility_entry),
                'facilities_text': facilities_text,
                'facility_count': _count_enabled_facilities(facilities_obj),
            })

        conn.close()

        return jsonify({
            'status': 'success',
            'items': items,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': max((total + per_page - 1) // per_page, 1),
            }
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/facilities/<place_id>', methods=['GET'])
def admin_get_facility_entry(place_id):
    _, error_response = _require_admin()
    if error_response:
        return error_response

    try:
        facilities_index = _load_facilities_index()

        conn = get_connection()
        cursor = conn.cursor()
        shop_row = cursor.execute('SELECT name FROM coffee_shops WHERE place_id = ?', (place_id,)).fetchone()
        conn.close()

        shop_name = shop_row[0] if shop_row else ''
        entry = facilities_index.get(place_id) or _default_facilities_entry(place_id, shop_name)
        if shop_name and not entry.get('name'):
            entry['name'] = shop_name

        return jsonify({'status': 'success', 'item': entry}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/facilities/<place_id>', methods=['PUT'])
def admin_update_facility_entry(place_id):
    _, error_response = _require_admin()
    if error_response:
        return error_response

    try:
        data = request.get_json() or {}
        entry = data.get('item')
        if not isinstance(entry, dict):
            return jsonify({'status': 'error', 'message': 'item harus berupa object JSON'}), 400

        facilities_index = _load_facilities_index()

        entry['place_id'] = place_id
        entry.setdefault('name', '')
        facilities = entry.get('facilities')
        if not isinstance(facilities, dict):
            return jsonify({'status': 'error', 'message': 'facilities harus berupa object JSON'}), 400

        facilities.setdefault('meta', {})
        if not isinstance(facilities['meta'], dict):
            facilities['meta'] = {}
        facilities['meta']['last_updated'] = datetime.utcnow().strftime('%Y-%m-%d')
        facilities['meta'].setdefault('source', 'admin_editor')

        facilities_index[place_id] = entry
        _save_facilities_index(facilities_index)

        return jsonify({'status': 'success', 'message': 'Facilities JSON berhasil diperbarui'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/shops', methods=['POST'])
def admin_create_shop():
    _, error_response = _require_admin()
    if error_response:
        return error_response

    try:
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        address = (data.get('address') or '').strip()
        if not name or not address:
            return jsonify({'status': 'error', 'message': 'Name and address are required'}), 400

        place_id = (data.get('place_id') or '').strip()
        if not place_id:
            slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
            place_id = f"admin-{slug or 'coffee-shop'}-{int(time.time())}"

        conn = get_connection()
        cursor = conn.cursor()

        exists = cursor.execute('SELECT 1 FROM coffee_shops WHERE place_id = ?', (place_id,)).fetchone()
        if exists:
            conn.close()
            return jsonify({'status': 'error', 'message': 'place_id already exists'}), 400

        now = datetime.utcnow().isoformat()
        cursor.execute('''
            INSERT INTO coffee_shops (
                place_id, name, address, rating, total_reviews, created_at, updated_at,
                map_embed_url, latitude, longitude
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            place_id,
            name,
            address,
            data.get('rating', 0) or 0,
            data.get('total_reviews', 0) or 0,
            now,
            now,
            data.get('map_embed_url'),
            data.get('latitude'),
            data.get('longitude'),
        ))

        hours_display = (data.get('opening_hours_display') or '').strip()
        if hours_display:
            cursor.execute('''
                INSERT OR REPLACE INTO opening_hours (place_id, hours_display, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (place_id, hours_display, now, now))

        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'message': 'Coffee shop created successfully'}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/shops/<place_id>', methods=['PUT'])
def admin_update_shop(place_id):
    _, error_response = _require_admin()
    if error_response:
        return error_response

    try:
        data = request.get_json() or {}
        conn = get_connection()
        cursor = conn.cursor()

        existing = cursor.execute('SELECT id FROM coffee_shops WHERE place_id = ?', (place_id,)).fetchone()
        if not existing:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Coffee shop not found'}), 404

        cursor.execute('''
            UPDATE coffee_shops
            SET name = ?, address = ?, rating = ?, total_reviews = ?, map_embed_url = ?,
                latitude = ?, longitude = ?, updated_at = ?
            WHERE place_id = ?
        ''', (
            (data.get('name') or '').strip(),
            (data.get('address') or '').strip(),
            data.get('rating', 0) or 0,
            data.get('total_reviews', 0) or 0,
            data.get('map_embed_url'),
            data.get('latitude'),
            data.get('longitude'),
            datetime.utcnow().isoformat(),
            place_id,
        ))

        hours_display = (data.get('opening_hours_display') or '').strip()
        now = datetime.utcnow().isoformat()
        if hours_display:
            cursor.execute('''
                INSERT OR REPLACE INTO opening_hours (place_id, hours_display, created_at, updated_at)
                VALUES (?, ?, COALESCE((SELECT created_at FROM opening_hours WHERE place_id = ?), ?), ?)
            ''', (place_id, hours_display, place_id, now, now))
        else:
            cursor.execute('DELETE FROM opening_hours WHERE place_id = ?', (place_id,))

        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': 'Coffee shop updated successfully'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/shops/<place_id>', methods=['DELETE'])
def admin_delete_shop(place_id):
    _, error_response = _require_admin()
    if error_response:
        return error_response

    try:
        conn = get_connection()
        cursor = conn.cursor()

        review_rows = cursor.execute('SELECT id FROM reviews WHERE place_id = ?', (place_id,)).fetchall()
        review_ids = [row[0] for row in review_rows]
        if review_ids:
            placeholders = ','.join('?' * len(review_ids))
            cursor.execute(f'DELETE FROM review_likes WHERE review_id IN ({placeholders})', review_ids)
            cursor.execute(f'DELETE FROM review_photos WHERE review_id IN ({placeholders})', review_ids)
            cursor.execute(f'DELETE FROM review_reports WHERE review_id IN ({placeholders})', review_ids)
            cursor.execute(f'DELETE FROM reviews WHERE id IN ({placeholders})', review_ids)

        cursor.execute('DELETE FROM favorites WHERE place_id = ?', (place_id,))
        cursor.execute('DELETE FROM want_to_visit WHERE place_id = ?', (place_id,))
        cursor.execute('DELETE FROM opening_hours WHERE place_id = ?', (place_id,))
        cursor.execute('DELETE FROM coffee_shops WHERE place_id = ?', (place_id,))

        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': 'Coffee shop deleted successfully'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/reviews', methods=['GET'])
def admin_get_reviews():
    _, error_response = _require_admin()
    if error_response:
        return error_response

    try:
        page = max(int(request.args.get('page', 1)), 1)
        per_page = min(max(int(request.args.get('per_page', 10)), 1), 100)
        search = (request.args.get('search') or '').strip().lower()
        place_id = (request.args.get('place_id') or '').strip()

        conn = get_connection()
        cursor = conn.cursor()

        where_clauses = []
        params = []
        if search:
            where_clauses.append('('
                'LOWER(COALESCE(r.review_text, "")) LIKE ? '
                'OR LOWER(COALESCE(u.username, "")) LIKE ? '
                'OR LOWER(COALESCE(c.name, "")) LIKE ?'
            ')')
            like = f'%{search}%'
            params.extend([like, like, like])

        if place_id:
            where_clauses.append('r.place_id = ?')
            params.append(place_id)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ''

        total = cursor.execute(
            f'''
            SELECT COUNT(*)
            FROM reviews r
            LEFT JOIN users u ON u.id = r.user_id
            LEFT JOIN coffee_shops c ON c.place_id = r.place_id
            {where_sql}
            ''',
            params
        ).fetchone()[0]

        rows = _paginate_query(
            cursor,
            f'''
            SELECT r.id, r.place_id, r.rating, r.review_text, r.created_at,
                   u.username, c.name AS shop_name
            FROM reviews r
            LEFT JOIN users u ON u.id = r.user_id
            LEFT JOIN coffee_shops c ON c.place_id = r.place_id
            {where_sql}
            ORDER BY r.created_at DESC
            ''',
            params,
            page,
            per_page
        )
        row_dicts = [dict_from_row(cursor, row) for row in rows]

        items = []
        for rd in row_dicts:
            photo_count = cursor.execute('SELECT COUNT(*) FROM review_photos WHERE review_id = ?', (rd['id'],)).fetchone()[0]
            like_count = cursor.execute('SELECT COUNT(*) FROM review_likes WHERE review_id = ?', (rd['id'],)).fetchone()[0]
            items.append({
                'id': rd['id'],
                'place_id': rd['place_id'],
                'shop_name': rd['shop_name'],
                'username': rd['username'],
                'rating': rd['rating'],
                'text': rd['review_text'],
                'created_at': rd['created_at'],
                'photo_count': photo_count,
                'like_count': like_count,
            })

        conn.close()

        return jsonify({
            'status': 'success',
            'items': items,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': max((total + per_page - 1) // per_page, 1),
            }
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/review-reports', methods=['GET'])
def admin_get_review_reports():
    _, error_response = _require_admin()
    if error_response:
        return error_response

    try:
        page = max(int(request.args.get('page', 1)), 1)
        per_page = min(max(int(request.args.get('per_page', 10)), 1), 100)
        search = (request.args.get('search') or '').strip().lower()
        status_filter = (request.args.get('status') or '').strip().lower()

        conn = get_connection()
        cursor = conn.cursor()

        where_clauses = []
        params = []

        if search:
            where_clauses.append('('
                                 'LOWER(COALESCE(rr.report_reason, "")) LIKE ? OR '
                                 'LOWER(COALESCE(rr.report_text, "")) LIKE ? OR '
                                 'LOWER(COALESCE(u.username, "")) LIKE ? OR '
                                 'LOWER(COALESCE(c.name, "")) LIKE ?'
                                 ')')
            like = f'%{search}%'
            params.extend([like, like, like, like])

        if status_filter:
            where_clauses.append('LOWER(COALESCE(rr.status, "pending")) = ?')
            params.append(status_filter)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ''

        total = cursor.execute(
            f'''
            SELECT COUNT(*)
            FROM review_reports rr
            LEFT JOIN reviews r ON r.id = rr.review_id
            LEFT JOIN users u ON u.id = rr.reported_by_user_id
            LEFT JOIN coffee_shops c ON c.place_id = r.place_id
            {where_sql}
            ''',
            params
        ).fetchone()[0]

        rows = _paginate_query(
            cursor,
            f'''
            SELECT rr.id, rr.review_id, rr.report_reason, rr.report_text, rr.reported_by_user_id,
                   COALESCE(rr.status, 'pending') AS status, rr.admin_notes, rr.created_at, rr.resolved_at,
                   u.username AS reported_by_username,
                   r.review_text, r.rating, r.place_id,
                   c.name AS shop_name
            FROM review_reports rr
            LEFT JOIN reviews r ON r.id = rr.review_id
            LEFT JOIN users u ON u.id = rr.reported_by_user_id
            LEFT JOIN coffee_shops c ON c.place_id = r.place_id
            {where_sql}
            ORDER BY rr.created_at DESC
            ''',
            params,
            page,
            per_page
        )

        items = [dict_from_row(cursor, row) for row in rows]
        conn.close()

        return jsonify({
            'status': 'success',
            'items': items,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': max((total + per_page - 1) // per_page, 1),
            }
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/review-reports/<int:report_id>', methods=['PUT'])
def admin_update_review_report(report_id):
    _, error_response = _require_admin()
    if error_response:
        return error_response

    try:
        data = request.get_json() or {}
        status = (data.get('status') or 'pending').strip()
        admin_notes = (data.get('admin_notes') or '').strip()

        conn = get_connection()
        cursor = conn.cursor()

        existing = cursor.execute('SELECT id FROM review_reports WHERE id = ?', (report_id,)).fetchone()
        if not existing:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Review report not found'}), 404

        resolved_at = datetime.utcnow().isoformat() if status in ['resolved', 'dismissed', 'reviewed'] else None
        cursor.execute('''
            UPDATE review_reports
            SET status = ?, admin_notes = ?, resolved_at = ?
            WHERE id = ?
        ''', (status, admin_notes or None, resolved_at, report_id))
        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'message': 'Review report berhasil diperbarui'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/reviews/<int:review_id>', methods=['DELETE'])
def admin_delete_review(review_id):
    _, error_response = _require_admin()
    if error_response:
        return error_response

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM review_likes WHERE review_id = ?', (review_id,))
        cursor.execute('DELETE FROM review_photos WHERE review_id = ?', (review_id,))
        cursor.execute('DELETE FROM review_reports WHERE review_id = ?', (review_id,))
        cursor.execute('DELETE FROM reviews WHERE id = ?', (review_id,))

        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': 'Review deleted successfully'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/ai/cache', methods=['GET'])
def admin_get_ai_cache():
    _, error_response = _require_admin()
    if error_response:
        return error_response

    try:
        sentiment_cache = load_sentiment_cache()
        conn = get_connection()
        cursor = conn.cursor()

        shop_lookup = {}
        for row in cursor.execute('SELECT place_id, name FROM coffee_shops').fetchall():
            rd = dict_from_row(cursor, row)
            shop_lookup[rd['place_id']] = rd['name']
        conn.close()

        items = []
        for place_id, entry in sentiment_cache.items():
            items.append({
                'place_id': place_id,
                'shop_name': shop_lookup.get(place_id, place_id),
                'review_count': entry.get('review_count', 0),
                'timestamp': entry.get('timestamp', 0),
                'data': entry.get('data', {}),
            })

        items.sort(key=lambda item: item.get('timestamp', 0), reverse=True)

        return jsonify({'status': 'success', 'items': items}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/ai/cache/<place_id>', methods=['DELETE'])
def admin_delete_ai_cache_entry(place_id):
    _, error_response = _require_admin()
    if error_response:
        return error_response

    try:
        sentiment_cache = load_sentiment_cache()
        if place_id in sentiment_cache:
            del sentiment_cache[place_id]
            save_sentiment_cache(sentiment_cache)
        return jsonify({'status': 'success', 'message': 'Cache entry deleted successfully'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/settings', methods=['GET'])
def admin_get_settings_summary():
    _, error_response = _require_admin()
    if error_response:
        return error_response

    try:
        return jsonify({
            'status': 'success',
            'settings': {
                'llm_available': llm_is_available(),
                'llm_model': HF_MODEL,
                'api_base_note': 'Frontend memakai VITE_API_BASE untuk mengakses Flask API',
                'cache_expiry_days': CACHE_EXPIRY_DAYS,
            }
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================================================
# REVIEWS API ENDPOINTS
# ============================================================================

@app.route('/api/reviews/latest', methods=['GET'])
@app.route('/api/reviews', methods=['GET'])
def api_latest_reviews():
    """Ulasan terbaru untuk tampilan publik (About / beranda / koleksi)."""
    result = get_latest_reviews(request.args.get('limit', 10))
    if not result.get('success'):
        return jsonify({'status': 'error', 'message': result.get('error', 'Gagal memuat ulasan')}), 500
    return jsonify({'status': 'success', 'items': result.get('items') or []}), 200


@app.route('/api/reviews', methods=['POST'])
def api_create_review():
    """Create a new review (rating tempat + text + photos)."""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        place_id = data.get('place_id')
        rating = data.get('rating')
        text = data.get('text', '')
        photos = data.get('photos') or []
        
        if not user_id or not place_id or rating is None:
            return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400
        
        result = create_review(
            user_id, place_id, rating, text,
            photos=photos,
        )
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'review': result['review']
            }), 201
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/reviews/<int:review_id>', methods=['GET'])
def api_get_review(review_id):
    """Get a single review"""
    try:
        result = get_review(review_id)
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'review': result['review']
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/reviews/<int:review_id>', methods=['PUT'])
def api_update_review(review_id):
    """Update a review"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'status': 'error', 'message': 'user_id required'}), 400
        
        result = update_review(
            review_id,
            user_id,
            rating=data.get('rating'),
            text=data.get('text'),
            photos=data.get('photos'),
        )
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'review': result['review']
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/reviews/<int:review_id>', methods=['DELETE'])
def api_delete_review(review_id):
    """Delete a review"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'status': 'error', 'message': 'user_id required'}), 400
        
        result = delete_review(review_id, user_id)
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'message': result['message']
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/reviews/<int:review_id>/like', methods=['POST'])
def api_toggle_review_like(review_id):
    """Toggle like on a review. Body: { user_id }."""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({'status': 'error', 'message': 'user_id required'}), 400
        result = toggle_review_like(user_id, review_id)
        if result['success']:
            return jsonify({
                'status': 'success',
                'liked': result['liked'],
                'like_count': result['like_count']
            }), 200
        return jsonify({'status': 'error', 'message': result.get('error', 'Failed')}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/reviews/<int:review_id>/report', methods=['POST'])
def api_report_review(review_id):
    """Laporkan review. Body opsional: { report_reason, report_text }. Wajib login."""
    token = _extract_bearer_token()
    if not token:
        return jsonify({
            'status': 'error',
            'message': 'Login diperlukan untuk melaporkan ulasan.',
        }), 401

    auth_result = verify_token(token)
    if not auth_result.get('valid'):
        return jsonify({
            'status': 'error',
            'message': 'Sesi tidak valid atau kadaluarsa. Silakan login lagi.',
        }), 401

    auth_user = auth_result.get('user') or {}
    if not auth_user.get('id'):
        return jsonify({
            'status': 'error',
            'message': 'Sesi tidak valid. Silakan login lagi.',
        }), 401

    try:
        data = request.get_json() or {}
        result = create_review_report(
            review_id=review_id,
            reported_by_user_id=auth_user['id'],
            report_reason=data.get('report_reason'),
            report_text=data.get('report_text'),
        )
        if result.get('success'):
            return jsonify({
                'status': 'success',
                'message': 'Laporan berhasil dikirim. Tim kami akan meninjau ulasan ini.',
                'report_id': result.get('report_id'),
            }), 201

        code = result.get('code')
        status_code = 400
        if code == 'NOT_FOUND':
            status_code = 404
        elif code == 'ALREADY_REPORTED':
            status_code = 409
        return jsonify({
            'status': 'error',
            'message': result.get('error', 'Gagal mengirim laporan'),
            'code': code,
        }), status_code
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/coffeeshops/<place_id>/reviews', methods=['GET'])
def api_get_shop_reviews(place_id):
    """Get all reviews for a coffee shop. Optional query: user_id to include user_has_liked."""
    try:
        limit = request.args.get('limit', 50, type=int)
        current_user_id = request.args.get('user_id', type=int)
        result = get_reviews_for_shop(place_id, limit, current_user_id=current_user_id)
        
        if result['success']:
            # Also get average rating
            rating_result = get_average_rating(place_id)
            return jsonify({
                'status': 'success',
                'reviews': result['reviews'],
                'average_rating': rating_result.get('average_rating', 0),
                'review_count': rating_result.get('review_count', 0)
            }), 200
        else:
            # Return empty array instead of error if no reviews found
            return jsonify({
                'status': 'success',
                'reviews': [],
                'average_rating': 0,
                'review_count': 0
            }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/users/<int:user_id>/profile', methods=['GET'])
def api_get_user_public_profile(user_id):
    """Get public profile for a user (no email). Includes review stats."""
    try:
        user = get_user_by_id(user_id)
        if not user:
            return jsonify({'status': 'error', 'message': 'User not found'}), 404
        stats = get_user_review_stats(user_id)
        if not stats.get('success'):
            review_count, average_rating = 0, 0
        else:
            review_count = stats.get('review_count', 0)
            average_rating = stats.get('average_rating', 0)
        return jsonify({
            'status': 'success',
            'profile': {
                'id': user['id'],
                'username': user.get('username'),
                'full_name': user.get('full_name') or user.get('username'),
                'avatar_url': user.get('avatar_url'),
                'bio': user.get('bio'),
                'review_count': review_count,
                'average_rating': average_rating
            }
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/users/<int:user_id>/reviews', methods=['GET'])
def api_get_user_reviews(user_id):
    """Get all reviews by a user"""
    try:
        limit = request.args.get('limit', 50, type=int)
        result = get_user_reviews(user_id, limit)
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'reviews': result['reviews']
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================================================
# FAVORITES API ENDPOINTS
# ============================================================================

@app.route('/api/favorites', methods=['POST'])
def api_add_favorite():
    """Add a coffee shop to favorites"""
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get('user_id')
        place_id = (data.get('place_id') or '').strip() if data.get('place_id') is not None else ''

        if user_id is None or user_id == '' or not place_id:
            return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

        result = add_favorite(user_id, place_id)
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'favorite_id': result['favorite_id'],
                'message': result['message']
            }), 201
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/favorites/<place_id>', methods=['DELETE'])
def api_remove_favorite(place_id):
    """Remove a coffee shop from favorites"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'status': 'error', 'message': 'user_id required'}), 400
        
        result = remove_favorite(user_id, place_id)
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'message': result['message']
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/users/<int:user_id>/favorites', methods=['GET'])
def api_get_user_favorites(user_id):
    """Get all favorites for a user"""
    try:
        limit = request.args.get('limit', 100, type=int)
        result = get_user_favorites(user_id, limit)
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'favorites': result['favorites']
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/coffeeshops/<place_id>/favorite-status', methods=['GET'])
def api_check_favorite(place_id):
    """Check if a coffee shop is in user's favorites"""
    try:
        user_id = request.args.get('user_id', type=int)
        
        if not user_id:
            return jsonify({'status': 'error', 'message': 'user_id required'}), 400
        
        result = is_favorite(user_id, place_id)
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'is_favorite': result['is_favorite']
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/coffeeshops/<place_id>/favorite-count', methods=['GET'])
def api_get_favorite_count(place_id):
    """Get number of times a coffee shop is favorited"""
    try:
        result = get_favorite_count(place_id)
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'count': result['count']
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================================================
# SHOP VOTES API ENDPOINTS
# ============================================================================

@app.route('/api/coffeeshops/<place_id>/votes/summary', methods=['GET'])
def api_get_vote_summary(place_id):
    """Aggregated vote summary (presence, rating, best_for, slider averages) for a coffee shop."""
    try:
        result = get_vote_summary(place_id)
        if result['success']:
            return jsonify({'status': 'success', **result}), 200
        return jsonify({'status': 'error', 'message': result['error']}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/coffeeshops/<place_id>/votes/me', methods=['GET'])
def api_get_my_vote(place_id):
    """Current user's vote for a coffee shop."""
    try:
        user_id = request.args.get('user_id', type=int)
        if not user_id:
            return jsonify({'status': 'error', 'message': 'user_id required'}), 400
        vote = get_user_vote(user_id, place_id)
        return jsonify({'status': 'success', 'vote': vote}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/coffeeshops/<place_id>/votes', methods=['POST'])
def api_upsert_vote(place_id):
    """Create or update the current user's vote for a coffee shop."""
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({'status': 'error', 'message': 'user_id required'}), 400

        result = upsert_vote(
            user_id,
            place_id,
            presence=data.get('presence'),
            rating=data.get('rating'),
            best_for=data.get('best_for'),
            pelayanan=data.get('pelayanan'),
            kebersihan=data.get('kebersihan'),
            kenyamanan=data.get('kenyamanan'),
            harga=data.get('harga'),
        )
        if result['success']:
            return jsonify({'status': 'success'}), 200
        return jsonify({'status': 'error', 'message': result['error']}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================================================
# PROS & CONS ("What People Say") API ENDPOINTS
# ============================================================================

@app.route('/api/coffeeshops/<place_id>/pros-cons', methods=['GET'])
def api_get_pros_cons(place_id):
    """
    Ambil poin pros & cons (hasil ekstraksi AI) untuk satu coffee shop.
    Batch job ekstraksi AI hanya dijalankan (lazy trigger) jika sudah waktunya
    (>=7 hari) atau sudah ada >=5 review baru sejak pembaruan terakhir.
    Selain itu, hanya membaca hasil yang sudah tersimpan di database.
    """
    try:
        user_id = request.args.get('user_id', type=int)

        conn = get_connection()
        cursor = conn.cursor()
        shop_row = cursor.execute('SELECT name FROM coffee_shops WHERE place_id = ?', (place_id,)).fetchone()
        conn.close()
        shop_name = shop_row[0] if shop_row else place_id

        maybe_refresh_pros_cons(place_id, shop_name)

        result = get_pros_cons(place_id, user_id=user_id)
        if result['success']:
            return jsonify({
                'status': 'success',
                'pros': result['pros'],
                'cons': result['cons'],
                'last_generated_at': result.get('last_generated_at'),
            }), 200
        return jsonify({'status': 'error', 'message': result['error']}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/coffeeshops/<place_id>/pros-cons/<int:point_id>/vote', methods=['POST'])
def api_vote_pros_cons(place_id, point_id):
    """Upvote/downvote satu poin pro/con. Body: { user_id, vote_type: 'up'|'down' }."""
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get('user_id')
        vote_type = data.get('vote_type')
        if not user_id:
            return jsonify({'status': 'error', 'message': 'user_id required'}), 400
        if vote_type not in ('up', 'down'):
            return jsonify({'status': 'error', 'message': "vote_type harus 'up' atau 'down'"}), 400

        result = toggle_pros_cons_vote(user_id, point_id, vote_type)
        if result['success']:
            return jsonify({
                'status': 'success',
                'upvotes': result['upvotes'],
                'downvotes': result['downvotes'],
                'user_vote': result['user_vote'],
            }), 200
        return jsonify({'status': 'error', 'message': result['error']}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================================================
# WANT TO VISIT API ENDPOINTS
# ============================================================================

@app.route('/api/want-to-visit', methods=['POST'])
def api_add_want_to_visit():
    """Add a coffee shop to want_to_visit"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        place_id = data.get('place_id')

        if not user_id or not place_id:
            return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

        result = add_want_to_visit(user_id, place_id)

        if result['success']:
            return jsonify({
                'status': 'success',
                'want_to_visit_id': result['want_to_visit_id'],
                'message': result['message']
            }), 201
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/want-to-visit/<place_id>', methods=['DELETE'])
def api_remove_want_to_visit(place_id):
    """Remove a coffee shop from want_to_visit"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({'status': 'error', 'message': 'user_id required'}), 400

        result = remove_want_to_visit(user_id, place_id)

        if result['success']:
            return jsonify({
                'status': 'success',
                'message': result['message']
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/users/<int:user_id>/want-to-visit', methods=['GET'])
def api_get_user_want_to_visit(user_id):
    """Get all want_to_visit for a user"""
    try:
        limit = request.args.get('limit', 100, type=int)
        result = get_user_want_to_visit(user_id, limit)

        if result['success']:
            return jsonify({
                'status': 'success',
                'want_to_visit': result['want_to_visit']
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/coffeeshops/<place_id>/want-to-visit-status', methods=['GET'])
def api_check_want_to_visit(place_id):
    """Check if a coffee shop is in user's want_to_visit"""
    try:
        user_id = request.args.get('user_id', type=int)

        if not user_id:
            return jsonify({'status': 'error', 'message': 'user_id required'}), 400

        result = is_want_to_visit(user_id, place_id)

        if result['success']:
            return jsonify({
                'status': 'success',
                'is_want_to_visit': result['is_want_to_visit']
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def _format_facilities_to_text(shop_facilities):
    """Mengubah data facilities JSON menjadi teks deskriptif terstruktur."""
    facilities = shop_facilities.get('facilities', {})
    if not facilities:
        return ""
    
    parts = []
    
    # Highlights
    highlights = facilities.get('highlights', {})
    active_highlights = [k.replace('_', ' ') for k, v in highlights.items() if v]
    if active_highlights:
        parts.append(f"Memiliki keunggulan: {', '.join(active_highlights)}.")
        
    # Popular For
    popular = facilities.get('popular_for', {})
    active_popular = [k.replace('_', ' ') for k, v in popular.items() if v]
    if active_popular:
        parts.append(f"Populer untuk: {', '.join(active_popular)}.")
        
    # Atmosphere
    atmosphere = facilities.get('atmosphere', [])
    if atmosphere:
        parts.append(f"Suasana: {', '.join(atmosphere)}.")
        
    # Amenities
    amenities = facilities.get('amenities', {})
    active_amenities = [k.replace('_', ' ') for k, v in amenities.items() if v]
    if active_amenities:
        parts.append(f"Fasilitas tersedia: {', '.join(active_amenities)}.")

    return " ".join(parts)


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


def _compact_prompt_text(text, max_chars=1200):
    """
    Kompres input prompt agar token lebih hemat:
    - normalisasi whitespace
    - batasi panjang karakter dengan ellipsis
    """
    cleaned = _normalize_whitespace(text)
    if max_chars <= 0 or len(cleaned) <= max_chars:
        return cleaned
    if max_chars <= 3:
        return cleaned[:max_chars]
    return cleaned[: max_chars - 3].rstrip() + "..."


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


def _extract_json_block(text):
    if not text:
        return None
    cleaned = str(text).strip()
    if '```' in cleaned:
        for part in cleaned.split('```'):
            part = part.strip()
            if part.startswith('json'):
                part = part[4:].strip()
            if part.startswith('{') and part.endswith('}'):
                return part
    match = re.search(r'\{[\s\S]*\}', cleaned)
    return match.group(0) if match else None


def _is_low_quality_review_text(text):
    text = _normalize_whitespace(text)
    if len(text) < 20:
        return True, 'too_short'

    if re.search(r'(.)\1{6,}', text.lower()):
        return True, 'excessive_character_repeat'

    letters = len(re.findall(r'[A-Za-zÀ-ÿ]', text))
    alnum = len(re.findall(r'[A-Za-zÀ-ÿ0-9]', text))
    if alnum > 0 and (letters / alnum) < 0.5:
        return True, 'too_many_non_letters'

    lower = text.lower()
    if 'http://' in lower or 'https://' in lower or 'www.' in lower:
        return True, 'contains_link'

    tokens = re.findall(r'[A-Za-zÀ-ÿ0-9]+', lower)
    if len(tokens) < 4:
        return True, 'too_few_words'

    unique_tokens = set(tokens)
    if len(unique_tokens) < 3:
        return True, 'too_few_unique_words'

    token_counts = Counter(tokens)
    top_token, top_count = token_counts.most_common(1)[0]
    if top_count >= 4 and (top_count / max(len(tokens), 1)) >= 0.45:
        return True, f'repetitive_token:{top_token}'

    return False, None


def _extract_review_analysis_features(review_items, max_reviews=10):
    prepared_reviews = []
    seen_texts = set()
    rejected_reasons = Counter()
    aspect_counts = {aspect: 0 for aspect in REVIEW_ANALYSIS_ASPECT_KEYWORDS}
    aspect_keyword_hits = {aspect: Counter() for aspect in REVIEW_ANALYSIS_ASPECT_KEYWORDS}
    term_counter = Counter()

    for original_index, review in enumerate(review_items or []):
        if isinstance(review, dict):
            text = _normalize_whitespace(review.get('text', ''))
            rating = review.get('rating', 0) or 0
            author = review.get('author_name') or review.get('username') or 'Anonim'
        else:
            text = _normalize_whitespace(review)
            rating = 0
            author = 'Anonim'

        if not text:
            rejected_reasons['empty'] += 1
            continue

        normalized_text = _normalize_match_text(text)
        if normalized_text in seen_texts:
            rejected_reasons['duplicate'] += 1
            continue

        is_low_quality, reason = _is_low_quality_review_text(text)
        if is_low_quality:
            rejected_reasons[reason or 'low_quality'] += 1
            continue

        seen_texts.add(normalized_text)
        token_set = set(re.findall(r'[A-Za-zÀ-ÿ0-9]+', normalized_text))

        for token in token_set:
            if len(token) < 3 or token.isdigit() or token in REVIEW_ANALYSIS_STOPWORDS:
                continue
            term_counter[token] += 1

        for aspect, keywords in REVIEW_ANALYSIS_ASPECT_KEYWORDS.items():
            matched = [keyword for keyword in keywords if keyword in normalized_text]
            if matched:
                aspect_counts[aspect] += 1
                for keyword in matched:
                    aspect_keyword_hits[aspect][keyword] += 1

        prepared_reviews.append({
            'index': original_index,
            'text': text,
            'rating': rating,
            'author': author,
        })

    prepared_reviews = prepared_reviews[:max_reviews]
    top_terms = [
        {'term': term, 'count': count}
        for term, count in term_counter.most_common(8)
        if count >= 2
    ]
    aspect_keywords = {
        aspect: [term for term, _count in counter.most_common(5)]
        for aspect, counter in aspect_keyword_hits.items()
    }

    return {
        'total_reviews': len(review_items or []),
        'used_reviews': len(prepared_reviews),
        'prepared_reviews': prepared_reviews,
        'rejected_reasons': dict(rejected_reasons),
        'aspect_counts': aspect_counts,
        'aspect_keywords': aspect_keywords,
        'top_terms': top_terms,
    }


def _extract_facilities_popular_keywords(facilities_text):
    if not facilities_text:
        return []
    lowered = facilities_text.lower()
    keyword_map = {
        'wifi': 'WiFi', 'wi-fi': 'WiFi', 'internet': 'WiFi',
        'parkir': 'parkir luas', 'colokan': 'colokan', 'stopkontak': 'colokan',
        'musholla': 'musholla', 'toilet': 'toilet', 'ac': 'ruangan sejuk',
        'outdoor': 'area outdoor', 'indoor': 'area indoor',
        'live music': 'live music', 'musik': 'live music',
        'sofa': 'sofa nyaman',
        'dine in': 'dine in', 'takeaway': 'takeaway', 'delivery': 'delivery',
        'cozy': 'suasana cozy', 'nyaman': 'suasana nyaman', 'tenang': 'suasana tenang',
        'aesthetic': 'aesthetic',
    }
    found = []
    seen = set()
    for token, label in keyword_map.items():
        if token in lowered and label.lower() not in seen:
            found.append(label)
            seen.add(label.lower())
    return found


def _pick_review_keywords(prepared, facilities_text='', target=3):
    reviews = prepared.get('prepared_reviews', [])
    aspect_keywords = prepared.get('aspect_keywords', {})
    top_terms = prepared.get('top_terms', [])

    all_aspect_kws = []
    for aspect in ['suasana', 'makanan_minuman', 'fasilitas', 'pelayanan', 'harga', 'lokasi']:
        for kw in aspect_keywords.get(aspect, []):
            if kw and kw not in all_aspect_kws:
                all_aspect_kws.append(kw)

    keywords_from_reviews = []
    seen = set()

    if len(reviews) == 1:
        for kw in all_aspect_kws:
            if kw.lower() not in seen:
                keywords_from_reviews.append(kw)
                seen.add(kw.lower())
            if len(keywords_from_reviews) >= target:
                break
    elif len(reviews) >= 2:
        per_review_tokens = []
        for review in reviews:
            text_lower = _normalize_match_text(review.get('text', ''))
            tokens = set(re.findall(r'[A-Za-z\u00C0-\u024F0-9]+', text_lower))
            per_review_tokens.append(tokens)

        for review_tokens in per_review_tokens:
            picked = False
            for kw in all_aspect_kws:
                if kw.lower() in review_tokens and kw.lower() not in seen:
                    keywords_from_reviews.append(kw)
                    seen.add(kw.lower())
                    picked = True
                    break
            if not picked:
                for item in top_terms:
                    term = item.get('term', '')
                    if term.lower() in review_tokens and term.lower() not in seen:
                        keywords_from_reviews.append(term)
                        seen.add(term.lower())
                        break
            if len(keywords_from_reviews) >= target:
                break

    if len(keywords_from_reviews) < target:
        for item in top_terms:
            term = item.get('term', '')
            if term and term.lower() not in seen:
                keywords_from_reviews.append(term)
                seen.add(term.lower())
            if len(keywords_from_reviews) >= target:
                break

    if len(keywords_from_reviews) < target:
        facility_kws = _extract_facilities_popular_keywords(facilities_text)
        for kw in facility_kws:
            if kw.lower() not in seen:
                keywords_from_reviews.append(kw)
                seen.add(kw.lower())
            if len(keywords_from_reviews) >= target:
                break

    return keywords_from_reviews[:target]


def _detect_review_keyword_aspect(keyword):
    normalized = _normalize_match_text(keyword)
    for aspect, keywords in REVIEW_ANALYSIS_ASPECT_KEYWORDS.items():
        if normalized in {_normalize_match_text(item) for item in keywords}:
            return aspect
    return None


def _humanize_summary_keyword(keyword):
    keyword = _normalize_whitespace(keyword)
    if not keyword:
        return ""

    normalized = _normalize_match_text(keyword)
    direct_phrases = {
        'kopi': 'kopi yang disukai pengunjung',
        'coffee': 'kopi yang disukai pengunjung',
        'espresso': 'racikan espresso yang enak',
        'latte': 'latte yang terasa nikmat',
        'americano': 'americano yang terasa pas',
        'matcha': 'matcha yang cukup digemari',
        'makanan': 'makanan yang cukup variatif',
        'minuman': 'minuman yang cukup variatif',
        'snack': 'snack yang cocok menemani nongkrong',
        'croffle': 'croffle yang banyak disukai',
        'dessert': 'dessert yang cukup menarik',
        'menu': 'pilihan menu yang beragam',
        'nyaman': 'suasana yang terasa nyaman',
        'cozy': 'suasana yang terasa cozy',
        'tenang': 'suasana yang cenderung tenang',
        'ramai': 'suasana yang hidup',
        'berisik': 'suasana yang cukup ramai',
        'aesthetic': 'tempat yang terlihat aesthetic',
        'estetik': 'tempat yang terlihat estetik',
        'adem': 'ruangan yang terasa adem',
        'dingin': 'ruangan yang terasa sejuk',
        'luas': 'tempat yang terasa luas',
        'sempit': 'area duduk yang cukup terbatas',
        'outdoor': 'area outdoor yang nyaman',
        'indoor': 'area indoor yang nyaman',
        'wifi': 'WiFi yang cukup membantu',
        'wi fi': 'WiFi yang cukup membantu',
        'internet': 'internet yang cukup mendukung',
        'colokan': 'colokan yang mudah dijangkau',
        'stopkontak': 'stopkontak yang tersedia',
        'ac': 'ruangan ber-AC yang nyaman',
        'parkir': 'area parkir yang memadai',
        'toilet': 'toilet yang tersedia',
        'musholla': 'musholla yang tersedia',
        'sofa': 'sofa yang nyaman dipakai duduk lama',
        'smoking': 'area smoking yang tersedia',
        'outlet': 'banyak outlet yang tersedia',
        'harga': 'harga yang terasa pas',
        'murah': 'harga yang cukup terjangkau',
        'mahal': 'harga yang cenderung premium',
        'worth': 'harga yang terasa worth it',
        'terjangkau': 'harga yang cukup terjangkau',
        'pelayanan': 'pelayanan yang cukup baik',
        'service': 'service yang cukup baik',
        'ramah': 'pelayanan yang terasa ramah',
        'kasir': 'pelayanan kasir yang cukup baik',
        'barista': 'barista yang ramah',
        'cepat': 'pelayanan yang cukup cepat',
        'lama': 'pelayanan yang kadang terasa lama',
        'slow': 'pelayanan yang kadang terasa lambat',
        'lokasi': 'lokasi yang mudah dijangkau',
        'jalan': 'akses jalan yang cukup mudah',
        'akses': 'akses yang cukup mudah',
        'strategis': 'lokasi yang cukup strategis',
        'pusat': 'lokasi yang dekat area pusat',
        'pinggir': 'lokasi yang cukup mudah ditemukan',
        'dekat': 'lokasi yang terasa dekat dijangkau',
        'parkir luas': 'area parkir yang cukup luas',
        'suasana nyaman': 'suasana yang terasa nyaman',
        'suasana tenang': 'suasana yang cenderung tenang',
        'suasana cozy': 'suasana yang terasa cozy',
        'ruangan sejuk': 'ruangan yang terasa sejuk',
        'sofa nyaman': 'sofa yang nyaman dipakai duduk lama',
        'live music': 'live music yang menambah suasana',
        'area outdoor': 'area outdoor yang nyaman',
        'area indoor': 'area indoor yang nyaman',
        'dine in': 'area dine in yang nyaman',
        'takeaway': 'layanan takeaway yang tersedia',
        'delivery': 'layanan delivery yang tersedia',
    }
    if normalized in direct_phrases:
        return direct_phrases[normalized]

    aspect = _detect_review_keyword_aspect(keyword)
    if aspect == 'suasana':
        return f"suasana dengan nuansa {keyword.lower()}"
    if aspect == 'fasilitas':
        return f"fasilitas {keyword.lower()} yang tersedia"
    if aspect == 'makanan_minuman':
        return f"{keyword.lower()} yang cukup disukai"
    if aspect == 'harga':
        return f"harga yang terasa {keyword.lower()}"
    if aspect == 'pelayanan':
        return f"pelayanan yang terasa {keyword.lower()}"
    if aspect == 'lokasi':
        return f"lokasi yang {keyword.lower()}"
    return keyword.lower()


def _build_ideal_ai_summary(prepared=None, facilities_text='', **_kwargs):
    prepared = prepared or {}
    keywords = _pick_review_keywords(prepared, facilities_text=facilities_text, target=3)
    phrases = []
    seen = set()
    for keyword in keywords:
        phrase = _humanize_summary_keyword(keyword)
        normalized = _normalize_match_text(phrase)
        if phrase and normalized and normalized not in seen:
            phrases.append(phrase)
            seen.add(normalized)

    if not phrases:
        return "Belum cukup data review untuk ringkasan AI."
    if len(phrases) == 1:
        return f"Coffee shop ini dikenal dengan {phrases[0]}."
    if len(phrases) == 2:
        return f"Coffee shop ini dikenal dengan {phrases[0]} dan {phrases[1]}."
    return f"Coffee shop ini dikenal dengan {phrases[0]}, {phrases[1]}, dan {phrases[2]}."


def _fallback_review_analysis(shop_name, prepared, facilities_text=''):
    top_terms = prepared.get('top_terms', [])
    aspect_counts = prepared.get('aspect_counts', {})
    highlights = [item['term'] for item in top_terms[:3]]
    aspects = {}
    for aspect in REVIEW_ANALYSIS_ASPECT_KEYWORDS:
        if aspect_counts.get(aspect, 0) > 0:
            aspects[aspect] = {
                'sentiment': 'netral',
                'summary': f"Aspek {aspect.replace('_', ' ')} sering muncul di review.",
                'evidence': None,
            }
        else:
            aspects[aspect] = None

    summary = _build_ideal_ai_summary(prepared=prepared, facilities_text=facilities_text)

    return {
        'review_relevance': [
            {'index': review['index'], 'relevant': True}
            for review in prepared.get('prepared_reviews', [])
        ],
        'aspects': aspects,
        'overall_sentiment': 'netral',
        'highlights': highlights,
        'warnings': [],
        'cocok_untuk': [],
        'summary': summary[:220],
        'top_terms': top_terms,
        'aspect_counts': aspect_counts,
        'aspect_keywords': prepared.get('aspect_keywords', {}),
        'quality': {
            'total_reviews': prepared.get('total_reviews', 0),
            'used_reviews': prepared.get('used_reviews', 0),
            'rejected_reasons': prepared.get('rejected_reasons', {}),
        },
    }


def _sanitize_structured_review_analysis(result, prepared, facilities_text=''):
    fallback = _fallback_review_analysis('Coffee Shop', prepared, facilities_text=facilities_text)
    allowed_sentiments = {'positif', 'negatif', 'netral'}
    raw_aspects = result.get('aspects', {}) if isinstance(result.get('aspects'), dict) else {}

    sanitized_aspects = {}
    for aspect in REVIEW_ANALYSIS_ASPECT_KEYWORDS:
        value = raw_aspects.get(aspect)
        if not isinstance(value, dict):
            sanitized_aspects[aspect] = None
            continue

        sentiment = str(value.get('sentiment', 'netral')).strip().lower()
        if sentiment not in allowed_sentiments:
            sentiment = 'netral'

        summary = _normalize_whitespace(value.get('summary', ''))[:180]
        evidence = _normalize_whitespace(value.get('evidence', ''))[:180] or None
        if not summary:
            sanitized_aspects[aspect] = None
            continue

        sanitized_aspects[aspect] = {
            'sentiment': sentiment,
            'summary': summary,
            'evidence': evidence,
        }

    overall_sentiment = str(result.get('overall_sentiment', 'netral')).strip().lower()
    if overall_sentiment not in allowed_sentiments:
        overall_sentiment = fallback['overall_sentiment']

    def _sanitize_list(key, limit):
        raw = result.get(key, [])
        if not isinstance(raw, list):
            return []
        items = []
        for item in raw:
            text = _normalize_whitespace(item)
            if text and text not in items:
                items.append(text[:80])
        return items[:limit]

    summary = _build_ideal_ai_summary(prepared=prepared, facilities_text=facilities_text)
    if not summary:
        summary = fallback['summary']

    review_relevance = []
    raw_relevance = result.get('review_relevance', [])
    if isinstance(raw_relevance, list):
        for entry in raw_relevance[: len(prepared.get('prepared_reviews', []))]:
            if not isinstance(entry, dict):
                continue
            try:
                review_index = int(entry.get('index'))
            except (TypeError, ValueError):
                continue
            review_relevance.append({
                'index': review_index,
                'relevant': bool(entry.get('relevant', True)),
                'reason': _normalize_whitespace(entry.get('reason', ''))[:120] or None,
            })
    if not review_relevance:
        review_relevance = fallback['review_relevance']

    return {
        'review_relevance': review_relevance,
        'aspects': sanitized_aspects,
        'overall_sentiment': overall_sentiment,
        'highlights': _sanitize_list('highlights', 3) or fallback['highlights'],
        'warnings': _sanitize_list('warnings', 2),
        'cocok_untuk': _sanitize_list('cocok_untuk', 4),
        'summary': summary,
        'top_terms': prepared.get('top_terms', []),
        'aspect_counts': prepared.get('aspect_counts', {}),
        'aspect_keywords': prepared.get('aspect_keywords', {}),
        'quality': {
            'total_reviews': prepared.get('total_reviews', 0),
            'used_reviews': prepared.get('used_reviews', 0),
            'rejected_reasons': prepared.get('rejected_reasons', {}),
        },
    }


def _get_structured_review_analysis(place_id, shop_name, review_items, facilities_text='', use_cache=True):
    current_review_count = len(review_items or [])
    cache_age_days = None

    if use_cache and place_id:
        try:
            sentiment_cache = load_sentiment_cache()
            cache_entry = sentiment_cache.get(place_id)
            if (
                is_cache_valid(cache_entry, current_review_count)
                and cache_entry.get('analysis_version') == REVIEW_ANALYSIS_CACHE_VERSION
                and isinstance(cache_entry.get('data'), dict)
                and cache_entry['data'].get('summary')
            ):
                cache_age_days = (time.time() - cache_entry.get('timestamp', 0)) / (60 * 60 * 24)
                cached = dict(cache_entry['data'])
                cached['_from_cache'] = True
                cached['_cache_age_days'] = round(cache_age_days, 1)
                return cached
        except Exception as cache_err:
            print(f"[REVIEW ANALYSIS] Cache read error: {cache_err}")

    prepared = _extract_review_analysis_features(review_items, max_reviews=10)
    fallback = _fallback_review_analysis(shop_name, prepared, facilities_text=facilities_text)

    if prepared.get('used_reviews', 0) == 0 or not llm_is_available():
        fallback['_from_cache'] = False
        fallback['_cache_age_days'] = None
        return fallback

    review_lines = []
    for review in prepared['prepared_reviews']:
        review_lines.append(
            f"[{review['index']}] ({review['rating']}⭐) {review['author']}: \"{review['text']}\""
        )

    aspect_lines = []
    for aspect, count in prepared['aspect_counts'].items():
        keywords = prepared['aspect_keywords'].get(aspect, [])
        keyword_text = ", ".join(keywords[:5]) if keywords else "-"
        aspect_lines.append(f"- {aspect}: {count} mention | keyword dominan: {keyword_text}")

    top_terms_text = ", ".join(
        f"{item['term']} ({item['count']}x)"
        for item in prepared['top_terms']
    ) or "-"

    rejected_text = ", ".join(
        f"{reason}: {count}"
        for reason, count in prepared['rejected_reasons'].items()
    ) or "-"

    system_prompt = """Anda adalah analis review coffee shop. Tugas Anda adalah membuat analisis TERSTRUKTUR dalam JSON VALID.

ATURAN KETAT:
- Gunakan HANYA informasi yang benar-benar ada di review dan data pendukung.
- Jika sebuah aspek tidak punya bukti yang cukup, isi null.
- Untuk setiap aspek yang diisi, evidence harus berupa kutipan atau frasa yang benar-benar muncul di review.
- Jangan menambah fakta baru, jangan mengarang fasilitas yang tidak disebut.
- Review yang tidak relevan/spam harus ditandai relevant=false.
- Output HANYA JSON object, tanpa markdown, tanpa penjelasan tambahan.

SCHEMA JSON:
{
  "review_relevance": [
    {"index": 0, "relevant": true, "reason": "opsional"}
  ],
  "aspects": {
    "suasana": {"sentiment": "positif|negatif|netral", "summary": "...", "evidence": "..."} atau null,
    "fasilitas": {"sentiment": "positif|negatif|netral", "summary": "...", "evidence": "..."} atau null,
    "makanan_minuman": {"sentiment": "positif|negatif|netral", "summary": "...", "evidence": "..."} atau null,
    "harga": {"sentiment": "positif|negatif|netral", "summary": "...", "evidence": "..."} atau null,
    "pelayanan": {"sentiment": "positif|negatif|netral", "summary": "...", "evidence": "..."} atau null,
    "lokasi": {"sentiment": "positif|negatif|netral", "summary": "...", "evidence": "..."} atau null
  },
  "overall_sentiment": "positif|negatif|netral",
  "highlights": ["maks 3 poin kuat, 2-5 kata"],
  "warnings": ["maks 2 poin lemah, 2-6 kata"],
  "cocok_untuk": ["maks 4 aktivitas"],
  "summary": "3 kata kunci utama dipisah koma, contoh: kopi enak, suasana nyaman, WiFi"
}"""

    user_prompt = f"""Coffee shop: {shop_name}
Place ID: {place_id or '-'}

STATISTIK REVIEW:
- total_review_masuk: {prepared['total_reviews']}
- total_review_lolos_filter: {prepared['used_reviews']}
- review_ditolak: {rejected_text}

TOP KATA PENGUNJUNG:
{top_terms_text}

ASPEK TERDETEKSI:
{chr(10).join(aspect_lines)}

DATA FASILITAS TAMBAHAN:
{facilities_text or '-'}

REVIEW TERFILTER:
{chr(10).join(review_lines)}

Buat JSON sesuai schema. Jika summary akhir terlalu umum atau tidak punya bukti, gunakan kata/istilah yang paling sering muncul di review."""

    full_prompt = f"""{system_prompt}

{user_prompt}

Output JSON:"""

    generated_text = None
    last_error = None
    for attempt in range(3):
        try:
            generated_text = llm_text_generation(
                full_prompt,
                model=(HF_MODEL or "meta-llama/Meta-Llama-3-8B").strip(),
                max_new_tokens=2048,
                temperature=0.2,
                return_full_text=False,
            )
            generated_text = (generated_text or '').strip()
            break
        except Exception as api_err:
            last_error = api_err
            print(f"[REVIEW ANALYSIS] Attempt {attempt + 1}/3 failed: {api_err}")
            if attempt < 2:
                time.sleep(2 * (attempt + 1))

    if generated_text is None:
        print(f"[REVIEW ANALYSIS] All attempts failed: {last_error}")
        fallback['_from_cache'] = False
        fallback['_cache_age_days'] = None
        return fallback

    try:
        json_block = _extract_json_block(generated_text)
        if not json_block:
            raise ValueError('No JSON object found in LLM response')
        parsed = json.loads(json_block)
        sanitized = _sanitize_structured_review_analysis(parsed, prepared, facilities_text=facilities_text)
    except Exception as parse_err:
        print(f"[REVIEW ANALYSIS] Parse error: {parse_err}")
        print(f"[REVIEW ANALYSIS] Raw response: {generated_text[:400]}")
        sanitized = fallback

    sanitized['_from_cache'] = False
    sanitized['_cache_age_days'] = None

    if use_cache and place_id:
        try:
            sentiment_cache = load_sentiment_cache()
            sentiment_cache[place_id] = {
                'data': {k: v for k, v in sanitized.items() if not k.startswith('_')},
                'timestamp': time.time(),
                'review_count': current_review_count,
                'shop_name': shop_name,
                'analysis_version': REVIEW_ANALYSIS_CACHE_VERSION,
            }
            save_sentiment_cache(sentiment_cache)
        except Exception as cache_err:
            print(f"[REVIEW ANALYSIS] Cache save error: {cache_err}")

    return sanitized


def _summarize_reviews_with_llm(review_texts, place_id=None, shop_name='Coffee Shop', facilities_text=''):
    review_items = [{'text': text, 'rating': 0, 'author_name': 'Anonim'} for text in review_texts]
    analysis = _get_structured_review_analysis(
        place_id,
        shop_name,
        review_items,
        facilities_text=facilities_text,
        use_cache=bool(place_id),
    )
    return analysis.get('summary', '')


def _normalize_match_text(value):
    return str(value or '').strip().lower()


def _get_shop_rating_value(shop):
    rating = shop.get('rating', 0)
    if isinstance(rating, str):
        try:
            rating = float(rating)
        except (ValueError, TypeError):
            rating = 0
    elif rating is None:
        rating = 0
    return rating


def _get_shop_review_count_value(shop):
    total_ratings = shop.get('total_reviews', shop.get('user_ratings_total', 0))
    if isinstance(total_ratings, str):
        try:
            total_ratings = int(float(total_ratings))
        except (ValueError, TypeError):
            total_ratings = 0
    elif total_ratings is None:
        total_ratings = 0
    return total_ratings





# Helper function untuk fetch coffee shops dengan REVIEWS dari file JSON lokal

def _fetch_coffeeshops_with_reviews_from_db(location_str, max_shops=15, keywords=None, return_metadata=False):
    """
    Fetch coffee shops DENGAN REVIEWS dari database (tabel coffee_shops + reviews) untuk LLM context.
    Reviews digunakan sebagai bukti/evidence dalam rekomendasi.
    Coffee shops diurutkan berdasarkan rating dan jumlah review untuk mendapatkan yang terbaik.
    JIKA ADA KEYWORDS: Prioritaskan coffee shop yang memiliki review relevan dengan keywords.
    
    Args:
        location_str: Nama lokasi untuk filter (e.g., "Pontianak") - saat ini tidak digunakan karena semua data dari Pontianak
        max_shops: Maksimal jumlah coffee shops yang di-fetch (default: 15)
        keywords: List of keywords untuk pre-filter coffee shops yang relevan (optional)
    
    Returns:
        String berisi daftar coffee shops dengan reviews untuk LLM context
    """
    try:
        print(f"[DB+REVIEWS] Loading coffee shops with reviews from database")

        conn = get_connection()
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT c.*, COALESCE(o.hours_display, '') AS opening_hours_display
            FROM coffee_shops c
            LEFT JOIN opening_hours o ON c.place_id = o.place_id
            ORDER BY c.rating DESC
        """).fetchall()
        coffee_shops = [dict_from_row(cursor, row) for row in rows]
        conn.close()
        print(f"[DB+REVIEWS] Loaded {len(coffee_shops)} shops dari tabel coffee_shops")

        if not coffee_shops:
            print(f"[DB+REVIEWS] Error: Tidak ada data coffee shop di database")
            if return_metadata:
                return "Tidak ada data coffee shop yang ditemukan.", []
            return "Tidak ada data coffee shop yang ditemukan."
        
        # Load facilities sekali untuk fallback saat tidak ada review
        facilities_by_place_id = {}
        facilities_path = os.path.join('frontend-cofind', 'src', 'data', 'facilities.json')
        if os.path.exists(facilities_path):
            try:
                with open(facilities_path, 'r', encoding='utf-8') as f:
                    facilities_by_place_id = json.load(f).get('facilities_by_place_id', {})
            except Exception as e:
                print(f"[DB+REVIEWS] Warning: could not load facilities: {e}")

        prepared_shops = []
        if keywords and len(keywords) > 0:
            print(f"[DB+REVIEWS] Pre-filtering coffee shops dengan keywords: {keywords[:10]}... (total: {len(keywords)})")

        for shop in coffee_shops:
            place_id = shop.get('place_id', '')
            reviews_result = get_reviews_for_shop(place_id, limit=10)
            reviews = reviews_result.get('reviews', []) if reviews_result.get('success') else []
            review_texts = [
                (r.get('text') or '').strip()
                for r in reviews
                if (r.get('text') or '').strip() and len((r.get('text') or '').strip()) > 20
            ]

            shop_fac = facilities_by_place_id.get(place_id, {})
            facilities_text = _format_facilities_to_text(shop_fac)

            keyword_result = _score_shop_for_keywords(review_texts, facilities_text, keywords, review_items=reviews)
            prepared_shops.append({
                **shop,
                '_reviews': reviews,
                '_review_texts': review_texts,
                '_facilities_text': facilities_text,
                '_keyword_score': keyword_result['score'],
                '_matched_keywords': keyword_result['matched_keywords'],
                '_matched_source': keyword_result['matched_source'],
                '_relevant_review_count': keyword_result['relevant_review_count'],
            })

        relevant_shops = [shop for shop in prepared_shops if shop.get('_keyword_score', 0) > 0]
        other_shops = [shop for shop in prepared_shops if shop.get('_keyword_score', 0) == 0]

        def base_sort_key(shop):
            return (-_get_shop_rating_value(shop), -_get_shop_review_count_value(shop))

        def relevant_sort_key(shop):
            has_review_evidence = 1 if shop.get('_review_texts') else 0
            return (
                -float(shop.get('_keyword_score', 0) or 0),
                -has_review_evidence,
                -_get_shop_rating_value(shop),
                -_get_shop_review_count_value(shop),
            )

        relevant_shops_sorted = sorted(relevant_shops, key=relevant_sort_key)
        other_shops_sorted = sorted(other_shops, key=base_sort_key)
        
        # Gabungkan: relevant shops di depan, lalu top other shops
        # Prioritaskan relevant shops, tapi tetap ambil top other shops untuk konteks lengkap
        selected_relevant_shops = relevant_shops_sorted[:max_shops]
        other_count = max(0, max_shops - len(selected_relevant_shops))
        
        coffee_shops = selected_relevant_shops + other_shops_sorted[:other_count]
        
        if keywords and len(keywords) > 0:
            print(f"[DB+REVIEWS] Final selection: {len(selected_relevant_shops)} relevant shops + {other_count} top-rated shops = {len(coffee_shops)} total")
        else:
            print(f"[DB+REVIEWS] Selected top {len(coffee_shops)} coffee shops (sorted by rating & review count), preparing context...")
        
        # Format context: utamakan REVIEW; jika tidak ada review gunakan DATA FASILITAS (seperti di FacilitiesTab)
        context_lines = [
            f"DAFTAR COFFEE SHOP DI {location_str.upper()}",
            f"Setiap toko punya sumber: 'Review pengunjung' (prioritas) atau 'Data fasilitas' (jika tidak ada review).",
            f"Total: {len(coffee_shops)} coffee shop\n"
        ]
        
        for i, shop in enumerate(coffee_shops, 1):
            place_id = shop.get('place_id', '')
            name = shop.get('name', 'Unknown')
            rating = shop.get('rating', 'N/A')
            total_ratings = shop.get('user_ratings_total', 0)
            
            maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
            address = _get_shop_address(shop)
            
            context_lines.append(f"{i}. {name}")
            context_lines.append(f"   • Place ID: {place_id}")
            context_lines.append(f"   • Rating: {rating}/5.0 ({total_ratings} reviews)")
            context_lines.append(f"   • Alamat: {address}")
            context_lines.append(f"   • Google Maps: {maps_url}")

            if shop.get('_keyword_score', 0) > 0:
                matched_keywords = ", ".join(shop.get('_matched_keywords', [])[:8])
                context_lines.append(f"   • Keyword relevan terdeteksi: {matched_keywords}")

            review_texts = shop.get('_review_texts', [])
            relevant_reviews = _pick_relevant_reviews_for_keywords(shop.get('_reviews', []), keywords, limit=2)
            facilities_text = shop.get('_facilities_text', '')
            if review_texts:
                if len(review_texts) >= 2 or sum(len(t) for t in review_texts) > 400:
                    evidence_label = 'Review pengunjung'
                    evidence_text = _summarize_reviews_with_llm(
                        review_texts,
                        place_id=place_id,
                        shop_name=name,
                        facilities_text=facilities_text,
                    )
                    suffix = " (ringkasan)"
                else:
                    evidence_label = 'Review pengunjung'
                    single = review_texts[0]
                    evidence_text = single[:400] + ("..." if len(single) > 400 else "")
                    suffix = ""
            elif facilities_text:
                evidence_label = 'Data fasilitas'
                evidence_text = facilities_text
                suffix = ""
            else:
                evidence_label = 'Tidak ada data'
                evidence_text = ''
                suffix = ""

            shop['_relevant_reviews'] = relevant_reviews
            shop['_maps_url'] = maps_url
            shop['_address'] = address
            shop['_evidence_label'] = evidence_label
            shop['_evidence_text'] = evidence_text

            if evidence_text:
                context_lines.append(f"   • Sumber: {evidence_label}{suffix}: {evidence_text}")
            else:
                context_lines.append(f"   • Sumber: (Tidak ada review maupun data fasilitas)")

            context_lines.append("")  # Separator
        
        context = "\n".join(context_lines)
        
        print(f"[DB+REVIEWS] Context prepared: {len(coffee_shops)} shops, {len(context)} characters (sumber: review atau data fasilitas)")
        print(f"[DB+REVIEWS] SUMMARY: {len(coffee_shops)} coffee shops akan dianalisis oleh LLM")
        if keywords and len(keywords) > 0:
            print(f"[DB+REVIEWS] Pre-filtered: {len(selected_relevant_shops)} relevant shops + {len(other_shops_sorted[:other_count])} top-rated shops")
        if return_metadata:
            selected_shops = [
                {
                    'place_id': shop.get('place_id', ''),
                    'name': shop.get('name', 'Unknown'),
                    'address': shop.get('_address', ''),
                    'maps_url': shop.get('_maps_url', ''),
                    'rating': _get_shop_rating_value(shop),
                    'matched_keywords': shop.get('_matched_keywords', []),
                    'evidence_label': shop.get('_evidence_label', ''),
                    'evidence_text': shop.get('_evidence_text', ''),
                    'keyword_score': shop.get('_keyword_score', 0),
                    'reviews': shop.get('_reviews', [])[:5],
                    'relevant_reviews': shop.get('_relevant_reviews', [])[:2],
                    'facilities_text': shop.get('_facilities_text', ''),
                }
                for shop in coffee_shops
            ]
            return context, selected_shops
        return context
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[DB+REVIEWS] Error: {str(e)}")
        print(f"[DB+REVIEWS] Traceback: {error_detail}")
        if return_metadata:
            return f"Error mengambil data coffee shop dengan review dari JSON: {str(e)}", []
        return f"Error mengambil data coffee shop dengan review dari JSON: {str(e)}"

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
            'kerja', 'wfc', 'work from cafe', 'laptop', 'zoom', 'meeting online',
            'ngantor', 'produktif', 'deadline', 'presentasi', 'dokumen', 'ngerjain kerjaan',
            'bisnis', 'kantor',
        ],
    },
    'bermain game': {
        'facility_fields': {
            'popular_for': ['good_for_groups'],
        },
        'review_keywords': [
            'main game', 'gaming', 'game', 'ngegame', 'mobile legends', 'ml', 'pubg',
            'valorant', 'mabar', 'gas game', 'turnamen', 'push rank', 'wifi', 'jaringan', 'jaringan lancar', 'internet'
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
            'catch up', 'ruang meeting', 'ruang rapat', 'meeting room',
            'private room', 'ruang privat', 'ruang diskusi', 'untuk meeting',
            'buat rapat', 'untuk rapat', 'pertemuan bisnis', 'pertemuan kerja',
            'meeting kantor', 'kumpul kerja', 'kumpul kantor', 'kumpul tim',
        ],
    },
    'bersantai': {
        'facility_fields': {
            'atmosphere': ['nyaman', 'santai', 'tenang', 'cozy', 'hangat'],
            'popular_for': ['solo_dining'],
        },
        'review_keywords': [
            'santai', 'nongkrong', 'chill', 'rileks', 'healing', 'tenang', 'adem',
            'nyaman', 'cozy', 'hangout', 'me time', 'sambil ngopi', 'obrol santai',
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
        ],
    },
    'instagrammable': {
        'facility_fields': {
            'atmosphere': ['trendi', 'artistic'],
        },
        'review_keywords': [
            'instagrammable', 'instagramable', 'instagenic', 'aesthetic', 'estetik',
            'foto', 'foto-foto', 'fotogenik', 'spot foto', 'konten', 'content',
            'feed', 'story', 'instagram', 'kekinian',
            'pict', 'photo spot', 'banyak spot foto',
        ],
    },
}

PILL_LABELS = {
    'belajar': 'Belajar',
    'kerja': 'Kerja',
    'bermain game': 'Bermain game',
    'meeting_sosialisasi': 'Meeting/sosialisasi',
    'bersantai': 'Bersantai',
    'keluarga': 'Keluarga',
    'instagrammable': 'Instagrammable',
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
    'kerja': 'kerja',
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


def _llm_max_reviews_per_shop_summary():
    """Batas ulasan per toko di prompt ringkasan rekomendasi. 0 / negatif / tidak di-set = semua ulasan di profil."""
    raw = (os.environ.get('COFIND_LLM_SUMMARY_MAX_REVIEWS_PER_SHOP') or '0').strip()
    try:
        v = int(raw)
    except ValueError:
        return None
    return None if v <= 0 else v


def _format_all_reviews_for_llm_prompt(reviews, *, per_review_chars, max_reviews=None):
    """
    Satu baris per ulasan untuk prompt LLM (isi teks dipotong per_review_chars).
    Mengikuti urutan `reviews` (dari DB: terbaru dulu).
    Return: (lines, n_lines_in_prompt, n_reviews_in_input_list sebelum slice)
    """
    revs_all = [r for r in (reviews or []) if isinstance(r, dict)]
    total_list = len(revs_all)
    revs = revs_all
    if max_reviews is not None and len(revs) > max_reviews:
        revs = revs[:max_reviews]
    lines = []
    idx = 0
    for r in revs:
        text = (r.get('text') or '').strip()
        if len(text) < 2:
            continue
        idx += 1
        body = _truncate_evidence_text(text, per_review_chars)
        un = (str(r.get('username') or r.get('full_name') or '').strip() or 'Anonim')
        rt = r.get('rating')
        rt_s = str(rt) if rt is not None and rt != '' else '?'
        lines.append(f'  [{idx}] {un} (rating {rt_s}): "{body}"')
    return lines, len(lines), total_list


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
        'llm_preference_keywords': [],
        'search_keyword_matches': [],
        'llm_keyword_matches': [],
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
    'bersantai': 'rating_suasana',
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


def _build_review_only_profile(place_id, facilities_index=None):
    """
    Bangun profil toko dari data reviews pengguna di database (Supabase/PostgreSQL).
    Returns:
        {
            'place_id', 'name',
            'reviews': [...],              # user reviews
            'review_count': int,
            'avg_user_rating': float|None, # rata-rata rating user (BUKAN Google)
            'avg_category_ratings': {
                'makanan': float|None,
                'layanan': float|None,
                'suasana': float|None,
            },
            'google_rating': float,        # display only
            'google_total_reviews': int,   # display only
        }
    Returns None jika toko tidak ditemukan sama sekali.
    """
    shop_data = {}
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT place_id, name, rating, total_reviews FROM coffee_shops WHERE place_id = ?",
            (place_id,),
        )
        row = cur.fetchone()
        if row:
            shop_data = dict_from_row(cur, row)
    finally:
        conn.close()

    if not shop_data:
        return None

    if facilities_index is None:
        facilities_index = _load_facilities_index()
    facility_entry = (facilities_index or {}).get(place_id) or {}
    facilities_tab = _format_facilities_tab_signals(facility_entry)

    # Semua ulasan di DB untuk skor + konteks LLM (ringkasan / rerank) menganalisis corpus penuh.
    reviews_result = get_reviews_for_shop(place_id, limit=None)
    reviews = reviews_result.get('reviews', []) if reviews_result.get('success') else []

    user_ratings = []
    makanan_ratings = []
    layanan_ratings = []
    suasana_ratings = []
    for r in reviews:
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
        'reviews': reviews,
        'review_count': len(reviews),
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
        facilities_index = _load_facilities_index()

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
        print(
            f"[RECOMMEND] Batch reviews gagal: {reviews_result.get('error')}; "
            "fallback per-shop get_reviews_for_shop",
            flush=True,
        )
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
    except Exception:
        pass
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


# Normalisasi frasa: domain coffee shop + kamus slang (slang_normalize.py).
# Alias tetap ada agar referensi lama tidak putus.
_TEXT_CANONICAL_REPLACEMENTS = DOMAIN_CANONICAL_REPLACEMENTS

_MANUAL_UNCLEAR_MESSAGE = (
    'Belum ada coffee shop yang cukup relevan dengan konteks yang dipilih. '
    'Coba pilih kombinasi konteks lain.'
)


def _normalize_keyword_phrase(value):
    """Normalisasi + slang map (bgt→banget, jgn→jangan, dll.) untuk matching/BM25."""
    return normalize_text_with_slang(value)


def _stem_indonesian_text(value):
    """Alias ke _normalize_keyword_phrase (stemming dinonaktifkan)."""
    return _normalize_keyword_phrase(value)


def _keyword_variants(value):
    normalized = _normalize_keyword_phrase(value)
    if not normalized:
        return []
    variants = [normalized]
    stemmed = _stem_indonesian_text(normalized)
    if stemmed and stemmed not in variants:
        variants.append(stemmed)
    return variants


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
    Berlaku untuk semua konteks pill, bukan hanya keluarga.
    """
    normalized_text = _normalize_keyword_phrase(text)
    if not normalized_text:
        return False
    tokens = normalized_text.split()
    stemmed_text = _stem_indonesian_text(normalized_text)
    stem_tokens = stemmed_text.split() if stemmed_text else []
    for variant in _keyword_variants(keyword):
        if not variant:
            continue
        if _find_keyword_token_spans(tokens, variant):
            return True
        if stem_tokens and _find_keyword_token_spans(stem_tokens, variant):
            return True
    return False


# Tokens stopword sederhana untuk text-overlap / keyword expansion.
_TEXT_OVERLAP_STOP = frozenset({
    'dan', 'atau', 'yang', 'dengan', 'untuk', 'di', 'ke', 'dari', 'pada', 'ini', 'itu',
    'ada', 'tidak', 'juga', 'lebih', 'sangat', 'banget', 'saja', 'akan', 'sudah', 'bisa', 'agar',
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'to', 'of', 'in', 'on', 'for', 'and', 'or', 'with', 'as', 'by',
})
# None = tidak membatasi jumlah frasa hasil sanitasi (tetap ada aturan panjang/token per frasa).
_SEARCH_KEYWORD_MAX = None
_PROMPT_EVIDENCE_CHAR_LIMIT = 600

# Token sampah dari jawaban LLM (instruksi / boilerplate). Dibuang per-token,
# bukan membuang seluruh frasa — supaya "wifi untuk review" -> "wifi".
_LLM_PREF_STRIP_TOKENS = frozenset({
    'output', 'format', 'json', 'assistant', 'system', 'markdown',
    'keyword', 'keywords', 'kata', 'kunci', 'user', 'preferensi',
    'berikut', 'adalah', 'contoh', 'misalnya', 'jawaban', 'jawab',
    'hanya', 'baris', 'bisakah', 'please', 'list', 'daftar',
    'review', 'reviews', 'ulasan', 'database', 'coffee', 'shop', 'cafe', 'kafe',
    'indonesia', 'pengunjung', 'pengguna',
})
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
    """Span anchor di satu ruang token (normalized atau stem), tidak dicampur."""
    found = set()
    if not line or not tokens or not preference_keywords:
        return found

    for kw in preference_keywords:
        for variant in _keyword_variants(kw):
            if not variant:
                continue
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


def _line_has_weakness_near_anchors(tokens, spans, line, stem_tokens, stem_spans, stem_line, preference_keywords, window):
    """True jika ada fragmen kelemahan dalam ±window token dari blok keyword preferensi."""
    if not preference_keywords:
        return False
    anchors_norm = _collect_preference_anchor_spans_for_line(tokens, spans, line, preference_keywords)
    weak_norm = _collect_weakness_token_spans(tokens, spans, line)
    n = len(tokens)
    for anchor in anchors_norm:
        for wsp in weak_norm:
            if _weakness_overlaps_anchor_window(wsp, anchor, n, window):
                return True
    if stem_line and stem_tokens:
        anchors_stem = _collect_preference_anchor_spans_for_line(
            stem_tokens, stem_spans, stem_line, preference_keywords
        )
        weak_stem = _collect_weakness_token_spans(stem_tokens, stem_spans, stem_line)
        n_st = len(stem_tokens)
        for anchor in anchors_stem:
            for wsp in weak_stem:
                if _weakness_overlaps_anchor_window(wsp, anchor, n_st, window):
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
    stem_line = _stem_indonesian_text(normalized_line)
    tokens, spans = _split_tokens_with_spans(normalized_line)
    stem_tokens, stem_spans = _split_tokens_with_spans(stem_line) if stem_line else ([], [])
    return _line_has_weakness_near_anchors(
        tokens, spans, normalized_line,
        stem_tokens, stem_spans, stem_line,
        preference_keywords, window,
    )


def _expand_pill_to_keywords(pill):
    """Gabungan keyword dari PILL_MAPPING + pill itu sendiri (lowercase)."""
    mapping = PILL_MAPPING.get(pill, {}) or {}
    out = [pill.lower()]
    out.extend([kw.lower() for kw in mapping.get('review_keywords', [])])
    return list(dict.fromkeys(out))


# Helper legacy keyword-expansion LLM dihapus.

def _sanitize_search_keywords(values, max_items=_SEARCH_KEYWORD_MAX):
    """Bersihkan output keyword expansion agar aman dipakai untuk matching review.
    max_items None = tidak memotong jumlah frasa (selain aturan per-frasa)."""
    chunks = []
    if isinstance(values, (list, tuple, set)):
        for value in values:
            chunks.extend(str(value or '').split(','))
    else:
        chunks = re.split(r'[,;\n]+', str(values or ''))

    keywords = []
    seen = set()
    banned_tokens = {
        'output', 'format', 'keyword', 'keywords', 'kata', 'kunci', 'user',
        'preferensi', 'database', 'ulasan', 'review', 'reviews', 'coffee', 'shop',
        'cafe', 'kafe', 'daftar',
    }

    for chunk in chunks:
        item = re.sub(r'^\s*[-*\d.)]+', '', str(chunk or '')).strip()
        if ':' in item and len(item.split(':', 1)[0].split()) <= 3:
            item = item.split(':', 1)[1].strip()
        normalized = _normalize_keyword_phrase(item)
        if not normalized:
            continue
        tokens = normalized.split()
        if len(normalized) < 2 or len(normalized) > 40 or len(tokens) > 4:
            continue
        if normalized in _TEXT_OVERLAP_STOP:
            continue
        if any(token in banned_tokens for token in tokens):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        keywords.append(normalized)
        if max_items is not None and len(keywords) >= max_items:
            break
    return keywords


def _flatten_llm_keyword_response(raw: str) -> str:
    """
    Ubah jawaban LLM (paragraf, bullet, baris terpisah) menjadi satu string
    yang bisa dipotong _sanitize_search_keywords seperti daftar koma.
    """
    blob = str(raw or '').strip()
    if not blob:
        return ''
    blob = re.sub(r'^```[\w\-]*\s*', '', blob.strip(), flags=re.IGNORECASE)
    blob = re.sub(r'\s*```\s*$', '', blob)
    blob = blob.replace('\r', '\n')
    lines_out = []
    for line in blob.split('\n'):
        line = line.strip()
        if not line:
            continue
        line = re.sub(r'^[-*•]\s+', '', line)
        line = re.sub(r'^\d+[\.)]\s+', '', line)
        if ':' in line and len(line.split(':', 1)[0].split()) <= 4:
            line = line.split(':', 1)[1].strip()
        if line:
            lines_out.append(line)
    merged = ', '.join(lines_out)
    merged = re.sub(r'\s*;\s*', ', ', merged)
    merged = re.sub(r'\s{2,}', ' ', merged)
    return merged.strip()


def _keyword_candidates_from_prose_fallback(blob: str, *, max_phrases=24) -> list:
    """
    Jika model mengembalikan prosa tanpa pemisah yang lolos sanitasi, geser jendela
    1–4 token pada awal teks saja (batas token) dan ambil frasa yang lolos sanitasi.
    """
    norm = _normalize_keyword_phrase(blob)
    if not norm:
        return []
    tokens = [t for t in norm.split() if t][:28]
    if not tokens:
        return []
    collected = []
    seen = set()
    n = len(tokens)
    for i in range(n):
        for length in range(1, 5):
            if i + length > n:
                break
            phrase = ' '.join(tokens[i : i + length])
            for kw in _sanitize_search_keywords(phrase):
                if kw not in seen:
                    seen.add(kw)
                    collected.append(kw)
                    if len(collected) >= max_phrases:
                        return collected
    return collected


def _normalize_llm_preference_chunk(item: str):
    """Satu potongan teks dari LLM → frasa preferensi (buang token instruktif)."""
    item = re.sub(r'^\s*[-*\d.)]+', '', str(item or '')).strip()
    if ':' in item and len(item.split(':', 1)[0].split()) <= 4:
        item = item.split(':', 1)[1].strip()
    normalized = _normalize_keyword_phrase(item)
    if not normalized:
        return None
    tokens = [t for t in normalized.split() if t and t not in _LLM_PREF_STRIP_TOKENS]
    if not tokens:
        return None
    out = ' '.join(tokens[:4])
    if len(out) < 2 or len(out) > 40:
        return None
    if out in _TEXT_OVERLAP_STOP:
        return None
    return out


def _normalize_llm_output_separators(text: str) -> str:
    """Samakan pemisah koma/baris ke ASCII agar split tidak gagal (LLM kadang Unicode)."""
    s = str(text or '')
    for ch in ('\uff0c', '\u3001', '\ufe50', '\ufe51', '\u060c', '\u066b'):
        s = s.replace(ch, ',')
    return s


def _llm_preference_phrases_from_raw(raw: str, *, max_items=64) -> list:
    """Frasa dari jawaban LLM untuk observabilitas + pemakaian di pencarian review."""
    blob = _normalize_llm_output_separators(str(raw or '').strip())
    if not blob:
        return []
    flat = _normalize_llm_output_separators(_flatten_llm_keyword_response(blob) or blob)
    chunks = re.split(r'[,;\n]+', flat)
    out = []
    seen = set()
    for chunk in chunks:
        n = _normalize_llm_preference_chunk(chunk)
        if not n or n in seen:
            continue
        seen.add(n)
        out.append(n)
        if len(out) >= max_items:
            return out
    if out:
        return out
    norm = _normalize_keyword_phrase(flat)
    if not norm:
        return []
    tokens = [t for t in norm.split() if t][:36]
    if not tokens:
        return []
    ntok = len(tokens)
    for i in range(min(ntok, 28)):
        for length in range(1, 5):
            if i + length > ntok:
                break
            phrase = ' '.join(tokens[i : i + length])
            kw = _normalize_llm_preference_chunk(phrase)
            if not kw or kw in seen:
                continue
            seen.add(kw)
            out.append(kw)
            if len(out) >= max_items:
                return out
    # Masih kosong: pecah koma + normalisasi ringan (tanpa strip token agresif)
    if not out and flat:
        alt = _filter_negative_search_keywords(
            _light_keyword_phrase_list(re.split(r'[,;\n]+', flat)),
        )
        for a in alt:
            if a in seen:
                continue
            seen.add(a)
            out.append(a)
            if len(out) >= max_items:
                return out
    return out


def _search_keywords_from_llm_raw_output(raw: str) -> list:
    """Pipeline: sanitize mentah → flatten (bullet/line) → prosa n-gram fallback."""
    if not str(raw or '').strip():
        return []
    direct = _sanitize_search_keywords(raw)
    if direct:
        return direct
    flat = _flatten_llm_keyword_response(raw)
    from_flat = _sanitize_search_keywords(flat) if flat else []
    if from_flat:
        return from_flat
    return _keyword_candidates_from_prose_fallback(flat or raw)


def _looks_negative_keyword(keyword):
    normalized = _normalize_keyword_phrase(keyword)
    if not normalized:
        return False
    for fragment in _NEGATIVE_KEYWORD_FRAGMENTS:
        if fragment in normalized:
            return True
    return False


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


def _filter_negative_search_keywords(keywords):
    """Filter lokal untuk menahan keyword bernada negatif/keluhan."""
    if isinstance(keywords, (list, tuple, set)):
        cleaned = _light_keyword_phrase_list(keywords)
    else:
        cleaned = _sanitize_search_keywords(keywords)
    output = []
    for keyword in cleaned:
        if _looks_negative_keyword(keyword):
            continue
        output.append(keyword)
    return output


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
    """Buang kata longgar meeting kecuali pill lain (keluarga/bersantai) membutuhkannya."""
    pill_set = {str(p).strip().lower() for p in (pills or []) if str(p).strip()}
    cleaned = list(keywords or [])
    if 'meeting_sosialisasi' not in pill_set:
        return cleaned
    if pill_set & {'keluarga', 'bersantai'}:
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
    """Keyword preferensi (leksikon pill + ekspansi) untuk mendeteksi keluhan pada kutipan."""
    out = []
    for pill in pills or []:
        out.extend(_expand_pill_to_keywords(pill))
    out.extend(_light_keyword_phrase_list(search_keywords or []))
    return _filter_overbroad_meeting_keywords(list(dict.fromkeys(out)), pills)


def _quote_is_caveat(quote_text, preference_keywords):
    """
    True bila kutipan mengandung keluhan yang menempel pada konteks preferensi.
    Kutipan seperti ini tidak boleh dipakai sebagai bukti kecocokan, tapi tetap
    layak ditampilkan sebagai catatan jujur.
    """
    text = str(quote_text or '')
    if len(text.strip()) < 10:
        return False
    normalized = _normalize_keyword_phrase(text)
    # "kurang cocok / tidak disarankan" tidak pernah jadi bukti pendukung,
    # meski keyword pill tidak ada di kalimat yang sama.
    if normalized and any(phrase in normalized for phrase in _UNSUITABILITY_PHRASES):
        return True
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
                or pill == 'llm_preference'
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
    if ctx:
        return (
            f'Untuk kebutuhan {ctx}, {name} paling banyak dibahas pengunjung terkait {themes}.'
            f'{detail_line}'
        )
    return f'Pengunjung menyoroti {themes} tentang {name}.{detail_line}'


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
    lalu match keyword pencarian/LLM, lalu kutipan positif umum.
    """
    ev = evidence or {}
    lines = []
    seen = set()
    for key in (
        'modal_display_quotes',
        'search_keyword_matches',
        'llm_keyword_matches',
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


def _community_score_from_signals(signals, pills):
    """Skor 0..1 dari agregat vote/overall/best-for/pros. None jika tidak ada data."""
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

    slider_vals = []
    sliders = vote.get('slider_averages') or {}
    for field in ('pelayanan', 'kebersihan', 'kenyamanan', 'harga'):
        val = sliders.get(field)
        if val is not None:
            try:
                slider_vals.append(max(0.0, min(1.0, (float(val) - 1.0) / 4.0)))
            except (TypeError, ValueError):
                pass
    if slider_vals:
        parts.append(sum(slider_vals) / len(slider_vals))
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
        print(f"[RECOMMEND] Modal quote summary: LLM off, fallback ({name})", flush=True)
        return fallback_summary

    print(f"[RECOMMEND] Modal quote summary: panggil LLM untuk '{name}'...", flush=True)
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
            '\nCatatan kurang positif dari ulasan (pakai hanya bila benar-benar relevan '
            'dengan konteks, tulis sebagai catatan jujur di kalimat terakhir):\n'
            + '\n'.join(weakness_lines)
            + '\n'
        )

    prompt = f"""Anda meringkas ulasan pengguna sebuah coffee shop untuk menjawab satu kebutuhan spesifik: {ctx}.
Tulis ringkasan yang membuat pembaca paham kenapa tempat ini cocok untuk kebutuhan itu, berdasarkan apa yang benar-benar dikatakan pengunjung.

Syarat ketat:
- 2-3 kalimat, satu paragraf mengalir, tanpa judul, label, heading, atau bullet
- Kalimat pertama harus mengaitkan {name} dengan kebutuhan "{ctx}" secara konkret
- Sebut minimal satu detail spesifik yang muncul di kutipan ulasan (misal kondisi ruang, colokan, wifi, keramaian, menu, harga, jam buka) — jangan hanya menyebut kata sifat umum seperti "nyaman" atau "cozy"
- Boleh menyebut angka rating atau jumlah ulasan bila memperkuat, tapi jangan menyalin daftar angka mentah
- Parafrase ulasan, jangan menyalin kutipan panjang kata per kata
- Hanya gunakan fakta dari data di bawah, dilarang mengarang fasilitas atau klaim yang tidak ada di data
- Jangan gunakan markdown apapun dan jangan awali dengan "Berikut", "Berdasarkan data", atau menyebut kata "ulasan relevan"
- Bahasa Indonesia santai tapi informatif, seperti rekomendasi dari teman yang pernah ke sana
- Sinyal penilaian, pengalaman, dan keunggulan pengunjung adalah fakta pendukung; jangan sebut kata vote, survei, atau slider, dan jangan ubah gaya paragraf.

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
                        'Anda adalah analis ulasan coffee shop berbahasa Indonesia. '
                        'Tulis ringkasan naratif singkat yang menjawab kebutuhan user, '
                        'selalu bersandar pada detail konkret dari kutipan ulasan yang diberikan, '
                        'dan tidak pernah menambah fakta di luar data.'
                    ),
                },
                {'role': 'user', 'content': prompt},
            ],
            max_tokens=220,
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
        print(
            f"[RECOMMEND] Modal quote summary: OK '{name}' "
            f"({round((time.perf_counter() - modal_t0) * 1000, 1)} ms)",
            flush=True,
        )
        return summary
    except Exception as err:
        print(
            f"[RECOMMEND] Modal quote summary LLM fallback triggered ({name}): {err}",
            flush=True,
        )
        return fallback_summary


def _attach_modal_evidence_to_supporting(evidence, shop_name, pills, search_keywords=None):
    """Salin evidence dan tambah modal_display_quotes, modal_caveat_quotes, modal_quote_summary."""
    ev = dict(evidence or {})
    supporting, caveats = _collect_modal_quote_groups(
        ev, pills, search_keywords=search_keywords,
    )
    quotes = supporting[:3]
    pill_labels = [PILL_LABELS.get(p, p) for p in (pills or [])]
    intent_phrase = ' dan '.join(pill_labels[:3]) if pill_labels else ''
    ev['modal_display_quotes'] = quotes
    # Catatan jujur: relevan dengan preferensi tapi memuat keluhan, jadi tidak
    # dihitung sebagai bukti kecocokan.
    ev['modal_caveat_quotes'] = caveats[:2]
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


def _seed_search_keywords(valid_pills):
    """Fallback non-LLM dari pill mapping."""
    seeds = []
    for pill in valid_pills or []:
        seeds.extend(_expand_pill_to_keywords(pill))
    return _filter_overbroad_meeting_keywords(
        _filter_negative_search_keywords(seeds),
        valid_pills,
    )


def _pick_keyword_matched_reviews(reviews, search_keywords, limit=3):
    """Pilih review paling kuat berdasarkan search_keywords hasil ekspansi."""
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
    llm_preference_keywords=None,
    bm25_norm=None,
    bm25_raw=None,
):
    """
    Scoring berbasis user review, dengan boost komunitas bila ada data:
        70% BM25 relevansi query vs korpus review toko
        20% alignment rating kategori (rating_suasana/makanan/layanan)
        10% rata-rata rating user (dari review, bukan Google)
    Jika toko punya sinyal komunitas (vote/overall/best-for/pros):
        62% BM25 + 16% kategori + 8% rating + 14% komunitas.
    Toko tanpa data komunitas tidak dihukum: bobot lama 70/20/10 tetap.

    Keyword match per-pill tetap dihitung untuk evidence/UI (sample quotes),
    tetapi bobot utama ranking memakai skor BM25 yang dinormalisasi (0..1).

    llm_preference_keywords: frasa Bucket B dari ekspansi LLM (tidak overlap leksikon pill,
    sudah divalidasi ada di korpus review). Di fungsi ini hanya dipakai untuk
    llm_evidence_matches (kutipan UI); pengaruh ranking-nya lewat token query BM25.
    """
    reviews = profile.get('reviews') or []
    review_count = len(reviews)
    search_keywords = _filter_overbroad_meeting_keywords(
        _light_keyword_phrase_list(search_keywords or []),
        pills,
    )
    llm_preference_keywords = _filter_overbroad_meeting_keywords(
        _filter_negative_search_keywords(llm_preference_keywords or []),
        pills,
    )
    if review_count == 0 or not pills:
        return {
            'total_score': 0.0,
            'keyword_score': 0.0,
            'bm25_score': 0.0,
            'bm25_raw': 0.0,
            'expanded_keyword_score': 0.0,
            'category_score': 0.0,
            'rating_score': 0.0,
            'per_pill_stats': {},
            'expanded_keyword_matches': [],
            'llm_evidence_matches': [],
            'llm_preference_keywords': llm_preference_keywords,
            'search_keywords': search_keywords,
            'category_detail': {},
            'review_count': review_count,
            'avg_user_rating': profile.get('avg_user_rating'),
            'has_quote_evidence': False,
            'community_score': None,
        }

    avg_user_rating = profile.get('avg_user_rating')
    rating_score = 0.0
    if avg_user_rating is not None:
        rating_score = max(0.0, min(1.0, (float(avg_user_rating) - 3.0) / 2.0))

    per_pill_stats = {}
    keyword_scores = []

    for pill in pills:
        keywords = _expand_pill_to_keywords(pill)
        keyword_review_hits = 0
        sample_quotes = []

        for review in reviews:
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
    category_score_avg, category_detail = _review_rating_category_scores(reviews, pills)

    expanded_keyword_matches = _pick_keyword_matched_reviews(reviews, search_keywords, limit=3)
    llm_evidence_matches = (
        _pick_keyword_matched_reviews(reviews, llm_preference_keywords, limit=5)
        if llm_preference_keywords
        else []
    )
    expanded_keyword_hits = 0
    if search_keywords:
        for review in reviews:
            text = (review.get('text') or '').strip()
            if text and any(_matches_keyword_phrase(text, kw) for kw in search_keywords):
                expanded_keyword_hits += 1
        expanded_keyword_score = min(1.0, expanded_keyword_hits / max(1, min(review_count, 5)))
    else:
        expanded_keyword_score = 0.0

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
        # Fallback lokal (tanpa indeks korpus): rata keyword + ekspansi
        text_relevance = keyword_score_avg
        if search_keywords:
            text_relevance = (keyword_score_avg + expanded_keyword_score) / 2.0
        bm25_norm_val = text_relevance
        bm25_raw_val = text_relevance
    else:
        bm25_norm_val = max(0.0, min(1.0, bm25_norm_val))

    community_score = _community_score_from_signals(profile.get('community_signals'), pills)
    if community_score is not None:
        W_BM25, W_CATEGORY, W_RATING, W_COMMUNITY = 0.62, 0.16, 0.08, 0.14
        total = (
            bm25_norm_val * W_BM25
            + category_score_avg * W_CATEGORY
            + rating_score * W_RATING
            + community_score * W_COMMUNITY
        )
    else:
        W_BM25, W_CATEGORY, W_RATING = 0.70, 0.20, 0.10
        total = (
            bm25_norm_val * W_BM25
            + category_score_avg * W_CATEGORY
            + rating_score * W_RATING
        )

    # Wajib ada bukti kutipan PENDUKUNG (keyword match TANPA keluhan pada aspek
    # preferensi). Kutipan yang hanya mengeluh soal konteks yang sama tidak cukup
    # untuk merekomendasikan toko.
    pref_kws = _preference_keywords_for_evidence(
        pills,
        list(search_keywords) + list(llm_preference_keywords),
    )

    def _is_supporting_quote(row):
        text = str((row or {}).get('quote') or '')
        return len(text.strip()) >= 10 and not _quote_is_caveat(text, pref_kws)

    has_quote_evidence = (
        any(
            _is_supporting_quote(sq)
            for p in pills
            for sq in ((per_pill_stats.get(p) or {}).get('sample_quotes') or [])
        )
        or any(_is_supporting_quote(m) for m in expanded_keyword_matches)
        or any(_is_supporting_quote(m) for m in llm_evidence_matches)
    )
    if not has_quote_evidence:
        total = 0.0

    return {
        'total_score': round(total, 4),
        'keyword_score': round(keyword_score_avg, 4),
        'bm25_score': round(bm25_norm_val, 4),
        'bm25_raw': round(bm25_raw_val, 4),
        'expanded_keyword_score': round(expanded_keyword_score, 4),
        'category_score': round(category_score_avg, 4),
        'rating_score': round(rating_score, 4),
        'per_pill_stats': per_pill_stats,
        'expanded_keyword_matches': expanded_keyword_matches,
        'llm_evidence_matches': llm_evidence_matches,
        'llm_preference_keywords': llm_preference_keywords,
        'search_keywords': search_keywords,
        'category_detail': category_detail,
        'review_count': review_count,
        'avg_user_rating': avg_user_rating,
        'has_quote_evidence': has_quote_evidence,
        'community_score': community_score,
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
    llm_evidence_matches = (score_detail or {}).get('llm_evidence_matches') or []
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

    llm_keyword_matches_out = []
    for match in llm_evidence_matches[:5]:
        quote_text = match.get('quote')
        matched_terms = [str(t).strip() for t in (match.get('matched_terms') or []) if str(t).strip()]
        if not quote_text or not matched_terms:
            continue
        key = _normalize_whitespace(quote_text).lower()[:120]
        if key not in seen_quote_keys:
            seen_quote_keys.add(key)
            review_quotes_out.append({
                'pill': 'llm_preference',
                'pill_label': 'Konteks AI',
                'quote': quote_text,
                'reason': ', '.join(matched_terms[:6]),
                'rating': match.get('rating'),
                'username': match.get('username'),
                **_quote_ui_extras(match),
            })
        llm_keyword_matches_out.append({
            'matched_terms': matched_terms[:8],
            'quote': quote_text,
            'rating': match.get('rating'),
            'username': match.get('username'),
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
        'llm_preference_keywords': (score_detail or {}).get('llm_preference_keywords') or [],
        'search_keyword_matches': search_keyword_matches_out,
        'llm_keyword_matches': llm_keyword_matches_out,
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
    return [PILL_LABELS.get(p, p).lower() for p in ordered_pills]


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
    r'.{0,80}?(?:tidak|belum)\s+'
    r'(?:ada|menyebutkan|menemukan|menyinggung).{0,80}?'
    r'(?:keluhan|kekurangan)',
    re.IGNORECASE,
)


def _no_complaint_summary_sentence(shop_name=None):
    name = str(shop_name or '').strip() or 'coffee shop ini'
    return f'Sampai saat ini belum ada keluhan yang berarti dari {name}.'


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
    pill_labels = [PILL_LABELS.get(p, p).lower() for p in pills]
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
    quote_body = (first_quote.get('quote') if first_quote else None) or ''
    quote_blob_for_topics = ' '.join(
        (q.get('quote') or '').strip()
        for q in (review_quotes or [])[:3]
        if (q.get('quote') or '').strip()
    )
    topics_phrase = _join_indonesian_topics(
        _topic_labels_for_shop_summary(pills, pill_stats, quote_blob_for_topics)
    )
    if not topics_phrase and top_signal:
        topics_phrase = top_signal['pill_label'].lower()
    if not topics_phrase and pill_labels:
        topics_phrase = _join_indonesian_topics(pill_labels)

    shop_name = shop.get('name') or 'Coffee shop ini'
    if topics_phrase:
        intro = f"{shop_name} paling terasa cocok untuk {topics_phrase}"
    else:
        intro = f"{shop_name} layak dipertimbangkan berdasarkan pola ulasan pengguna"
    if avg is not None:
        intro += f", dengan rata-rata rating {avg:.1f}/5"
    elif review_count:
        intro += f" dari {review_count} ulasan pengguna"
    intro += '.'

    if first_quote:
        strength = (
            f'Pengunjung menonjolkan pengalaman positif, misalnya: '
            f'"{first_quote["quote"]}".'
        )
    elif top_signal:
        strength = (
            f'Ulasan pengguna cukup sering membahas aspek {top_signal["pill_label"].lower()}.'
        )
    else:
        strength = 'Sinyal rating dan ulasan pengguna masih memberi dasar positif untuk rekomendasi ini.'

    if weak_quote:
        caveat = (
            f'Ada catatan kurang positif seperti "{weak_quote["quote"]}", '
            f'meski gambaran utamanya tetap ditopang ulasan positif.'
        )
    elif review_count and review_count < 3:
        caveat = (
            f'Jumlah ulasan masih terbatas. '
            f'{_no_complaint_summary_sentence(shop_name)}'
        )
    else:
        caveat = _no_complaint_summary_sentence(shop_name)

    return _join_narrative_summary_parts(intro, strength, caveat)


def _summary_review_count_for_shop(shop):
    return (shop.get('evidence') or {}).get('review_count', 0)


def _build_summary_output_entry(shop, summary, pills, search_keywords):
    """Bangun entri output rekomendasi yang seragam untuk semua jalur (cache/LLM/fallback)."""
    summary = _strip_structured_summary_labels(summary or '')
    summary = _rewrite_no_complaint_summary_tail(summary, shop.get('name'))
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
    return {
        'place_id': shop['place_id'],
        'name': shop['name'],
        'score': shop.get('score', 0),
        'final_score': shop.get('final_score', shop.get('score', 0)),
        'ranking_source': 'llm' if llm_fit else 'hybrid',
        'llm_fit': llm_fit,
        'explanation': summary,
        'supporting_evidence': evidence_out,
        'review_count': evidence_out.get('review_count', 0),
        'avg_user_rating': evidence_out.get('avg_user_rating'),
        'is_low_confidence': evidence_out.get('is_low_confidence', False),
    }


def _generate_llm_review_summary(top_shops, pills, search_keywords=None):
    """
    NLP summary per shop dengan cache per (place_id + kombinasi pill + keyword ekspansi).
    Ringkasan ter-cache dipakai ulang (summary yang sama) sampai jumlah review
    coffee shop berubah atau keyword intent berbeda. Hanya shop tanpa cache valid
    yang dikirim ke LLM.
    Jika LLM tidak tersedia / gagal parse, pakai fallback deterministik.
    Shop tanpa kutipan relevan dibuang dari output.
    """
    if not top_shops:
        return []

    search_keywords = _light_keyword_phrase_list(search_keywords or [])

    # 1) Pakai ulang ringkasan ter-cache (invalidasi otomatis saat review_count berubah).
    cached_summary_map = {}
    shops_to_generate = []
    for shop in top_shops:
        cached = _get_cached_recommendation_summary(
            shop['place_id'], pills, _summary_review_count_for_shop(shop),
            search_keywords=search_keywords,
        )
        if cached:
            cached_summary_map[shop['place_id']] = cached
        else:
            shops_to_generate.append(shop)

    print(
        f"[RECOMMEND] Summary: cache_hit={len(cached_summary_map)} "
        f"generate={len(shops_to_generate)}",
        flush=True,
    )
    generated_summary_map = _llm_summaries_for_shops(
        shops_to_generate, pills, search_keywords,
    )

    # 3) Simpan ringkasan baru ke cache (per place_id + pill + keyword ekspansi).
    _store_recommendation_summaries(
        [
            (
                s['place_id'],
                pills,
                generated_summary_map.get(s['place_id']),
                _summary_review_count_for_shop(s),
                s.get('name') or '',
            )
            for s in shops_to_generate
            if generated_summary_map.get(s['place_id'])
        ],
        search_keywords=search_keywords,
    )

    # 4) Rakit output sesuai urutan asli; skip shop tanpa bukti kutipan.
    output = []
    for shop in top_shops:
        summary = (
            cached_summary_map.get(shop['place_id'])
            or generated_summary_map.get(shop['place_id'])
            or _build_review_summary_deterministic(shop, pills)
        )
        entry = _build_summary_output_entry(shop, summary, pills, search_keywords)
        if entry is None:
            print(
                f"[RECOMMEND] Summary: drop {shop.get('name')} — tanpa modal_display_quotes",
                flush=True,
            )
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
            print(
                f"[RECOMMEND] Summary: match {via} → {shop.get('name')} ({pid})",
                flush=True,
            )
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


def _llm_summaries_for_shops(top_shops, pills, search_keywords=None):
    """Kembalikan {place_id: summary} untuk shop yang diberikan (LLM atau fallback deterministik per toko)."""
    if not top_shops:
        return {}

    pill_labels = [PILL_LABELS.get(p, p) for p in pills]
    intent_line = " | ".join(pill_labels) if pill_labels else "preferensi umum"
    search_keywords = _light_keyword_phrase_list(search_keywords or [])
    keyword_line = ", ".join(search_keywords) if search_keywords else "tidak ada"

    if not llm_is_available():
        if COFIND_DEV_LLM_STRICT:
            raise RuntimeError('LLM strict mode aktif: summary butuh LLM tersedia.')
        print("[RECOMMEND] Summary: LLM tidak tersedia, pakai fallback deterministik", flush=True)
        return {
            s['place_id']: _build_review_summary_deterministic(s, pills)
            for s in top_shops
        }

    shop_blocks = []
    summary_cap = _llm_max_reviews_per_shop_summary()
    print(
        f"[RECOMMEND] Summary: bangun prompt untuk {len(top_shops)} shop "
        f"(max_reviews_per_shop={summary_cap})",
        flush=True,
    )
    for idx, shop in enumerate(top_shops, 1):
        evidence = shop.get('evidence') or {}
        profile = shop.get('profile') or {}
        pill_stats = evidence.get('pill_stats') or []
        facilities_tab = (
            evidence.get('facilities_tab_intent')
            or evidence.get('facilities_tab')
            or {}
        )
        review_count = evidence.get('review_count', 0)

        stats_lines = []
        for s in pill_stats:
            stats_lines.append(
                f"  - {s['pill_label']}: {s['keyword_review_hits']} review menyebut kata terkait"
                + (f", rata-rata {s['category_field']}={s['category_avg']}" if s.get('category_avg') is not None else '')
            )
        if not stats_lines:
            stats_lines.append('  - (tidak ada sinyal pill yang cocok)')

        profile_lines = _shop_profile_lines_for_prompt(profile, evidence, pills=pills) or [
            '  - (tidak ada data rating)'
        ]

        # Kutipan yang sudah tersaring relevansi konteks jadi jangkar utama ringkasan,
        # sedangkan korpus penuh di bawahnya hanya konteks tambahan.
        supporting_quotes, caveat_quotes = _collect_modal_quote_groups(
            evidence, pills, search_keywords=search_keywords,
        )
        # Hanya kutipan pendukung yang boleh jadi bahan klaim "cocok"; keluhan
        # dikirim terpisah agar tidak dipakai sebagai alasan merekomendasikan.
        relevant_quote_lines = _relevant_quote_lines_for_prompt(
            {'modal_display_quotes': supporting_quotes[:6]}, limit=6, char_limit=280,
        ) or ['  - (tidak ada kutipan yang cocok konteks)']
        weakness_lines = _weakness_quote_lines_for_prompt(
            {'modal_caveat_quotes': caveat_quotes[:2]}, limit=2,
        ) or ['  - (tidak ada keluhan menonjol pada konteks ini)']

        corpus = profile.get('reviews') or []
        review_lines, n_prompt, total_in_profile = _format_all_reviews_for_llm_prompt(
            corpus,
            per_review_chars=380,
            max_reviews=summary_cap,
        )
        if not review_lines:
            review_lines = ['  - (tidak ada teks ulasan)']
        corpus_note = ''
        if summary_cap is not None and total_in_profile > summary_cap:
            corpus_note = (
                f"\n  (Catatan: {n_prompt} ulasan terbaru di prompt dari {total_in_profile} di profil; "
                'set COFIND_LLM_SUMMARY_MAX_REVIEWS_PER_SHOP=0 untuk tanpa batas.)'
            )
        elif review_count and n_prompt < review_count:
            corpus_note = (
                f'\n  (Catatan: {n_prompt} baris teks dari {review_count} ulasan — beberapa baris mungkin tanpa teks.)'
            )

        facility_lines = []
        if facilities_tab.get('popular_for'):
            facility_lines.append("  - Populer untuk: " + ", ".join(facilities_tab.get('popular_for')[:5]))
        if facilities_tab.get('highlights'):
            facility_lines.append("  - Keunggulan: " + ", ".join(facilities_tab.get('highlights')[:5]))
        if facilities_tab.get('atmosphere'):
            facility_lines.append("  - Suasana: " + ", ".join(facilities_tab.get('atmosphere')[:5]))
        if not facility_lines:
            facility_lines.append("  - (tidak ada data fasilitas tab)")

        shop_blocks.append(
            f"{idx}. {shop['name']} (place_id: {shop['place_id']})\n"
            f"  Profil dari database:\n" + "\n".join(profile_lines) + "\n"
            f"  Sinyal fasilitas tab:\n" + "\n".join(facility_lines) + "\n"
            f"  Seberapa sering konteks ini dibahas di ulasan:\n" + "\n".join(stats_lines) + "\n"
            f"  KUTIPAN PALING RELEVAN dengan preferensi user (pakai ini sebagai bukti utama):\n"
            + "\n".join(relevant_quote_lines) + "\n"
            f"  Keluhan/catatan dari ulasan:\n" + "\n".join(weakness_lines) + "\n"
            f"  Konteks tambahan — ulasan lain ({n_prompt} baris, terbaru dulu, isi dipotong):{corpus_note}\n"
            + "\n".join(review_lines)
        )

    blocks_text = _compact_prompt_block("\n\n".join(shop_blocks), 7200)

    prompt = (
        "Tugas: untuk setiap kandidat coffee shop, tulis satu ringkasan naratif singkat "
        "(2-3 kalimat dalam satu paragraf mengalir) yang menjawab apakah tempat itu cocok "
        "untuk kebutuhan user.\n"
        f"Kebutuhan user: {intent_line}\n"
        f"Keyword intent: {keyword_line}\n\n"
        "Cara menulis tiap ringkasan:\n"
        "- Satu paragraf utuh, tanpa judul, label, heading, atau bullet.\n"
        "- DILARANG memakai label eksplisit seperti 'Kesimpulan:', 'Kelebihannya,', "
        "'Catatan:', atau 'Kekurangannya:'.\n"
        "- Kalimat pertama kaitkan nama tempat dengan kebutuhan user dan alasan utamanya "
        "menurut ulasan.\n"
        "- Kalimat berikutnya sebut 1-2 detail konkret dari kutipan relevan (kondisi ruang, "
        "colokan, wifi, keramaian, menu, harga, jam operasional, pelayanan). Jangan berhenti "
        "di kata sifat umum seperti 'nyaman' atau 'cozy' tanpa detail pendukung.\n"
        "- Akhiri dengan catatan jujur bila ada keluhan relevan pada bagian "
        "'Keluhan/catatan dari ulasan'.\n"
        "- Bila tidak ada keluhan menonjol, AKHIRI dengan kalimat ini (ganti nama tempat): "
        "'Sampai saat ini belum ada keluhan yang berarti dari {nama coffee shop}.'\n"
        "- DILARANG menulis penyangkalan panjang seperti 'ulasan lainnya tidak menyebutkan "
        "tentang kekurangan atau keluhan yang signifikan'.\n\n"
        "Aturan isi:\n"
        "- Hanya gunakan fakta dari data yang disediakan; dilarang mengarang fasilitas, "
        "lokasi, harga, atau angka apa pun.\n"
        "- Parafrase ulasan dengan bahasa sendiri, jangan menyalin kutipan panjang kata per kata.\n"
        "- Prioritaskan kutipan pada bagian 'KUTIPAN PALING RELEVAN'; ulasan lain hanya pendukung.\n"
        "- Sinyal penilaian, pengalaman, dan keunggulan pengunjung adalah fakta pendukung; "
        "jangan sebut kata vote, survei, atau slider, dan jangan ubah gaya paragraf.\n"
        "- Ringkasan tiap tempat harus berbeda satu sama lain, jangan memakai kalimat template.\n"
        "- Bahasa Indonesia natural, tanpa markdown.\n\n"
        "Kandidat dan data:\n"
        + blocks_text
        + "\n\nAturan output:\n"
        "- JSON array valid saja, tanpa markdown/teks lain.\n"
        f"- Wajib persis {len(top_shops)} objek, satu untuk setiap toko, jangan ada yang dilewati.\n"
        "- place_id harus copy-paste sama persis dari daftar ini: "
        + ", ".join(str(s.get('place_id') or '') for s in top_shops)
        + "\n"
        "- summary adalah satu string paragraf naratif (bukan objek terpisah).\n"
        'Format: [{"place_id":"...","name":"...","summary":"..."}]'
    )
    prompt = _compact_prompt_block(prompt, 0)
    print(
        f"[RECOMMEND] Summary: kirim request LLM (prompt_chars={len(prompt)})...",
        flush=True,
    )
    llm_t0 = time.perf_counter()

    try:
        raw = llm_chat_completions_create(
            model=(HF_MODEL or "meta-llama/Meta-Llama-3-8B").strip(),
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'Anda adalah Cofind Assistant, analis ulasan coffee shop berbahasa Indonesia. '
                        'Jawab hanya JSON array valid. Setiap summary adalah satu paragraf naratif '
                        '2-3 kalimat tanpa label Kesimpulan/Kelebihan/Catatan, bersandar pada detail '
                        'konkret dari kutipan ulasan yang relevan dengan kebutuhan user, tanpa '
                        'menambah fakta di luar data.'
                    ),
                },
                {'role': 'user', 'content': prompt},
            ],
            max_tokens=900,
            temperature=0.2,
        )
        print(
            f"[RECOMMEND] Summary: LLM response diterima "
            f"({round((time.perf_counter() - llm_t0) * 1000, 1)} ms, "
            f"raw_chars={len(str(raw or ''))})",
            flush=True,
        )
        parsed = _parse_llm_json_with_repair(
            raw,
            expected='array',
            model=(HF_MODEL or "meta-llama/Meta-Llama-3-8B").strip(),
        )
        if isinstance(parsed, dict):
            parsed = parsed.get('recommendations') or parsed.get('items') or parsed.get('shops') or []
        if not isinstance(parsed, list):
            raise ValueError("summary: not a list")

        summary_map = _assign_llm_summaries_to_shops(parsed, top_shops)
        result_map = {}
        skipped = []
        for shop in top_shops:
            summary = summary_map.get(shop['place_id'])
            invalid_reason = None
            if not summary:
                invalid_reason = 'summary kosong'
            elif any(bad in summary.lower() for bad in ['place_id', '[fasilitas]', '[review]', 'json']):
                invalid_reason = 'summary mengandung artefak prompt'
            else:
                unverified = _unverified_summary_quotes(summary, shop)
                if unverified:
                    invalid_reason = f'kutipan tidak ada di review: {unverified[0][:60]}'
            if invalid_reason:
                skipped.append((shop, invalid_reason))
                prefix = '[STRICT] ' if COFIND_DEV_LLM_STRICT else ''
                print(
                    f"[RECOMMEND] {prefix}Summary fallback deterministik untuk "
                    f"{shop.get('name')} ({shop.get('place_id')}): {invalid_reason}",
                    flush=True,
                )
                summary = _build_review_summary_deterministic(shop, pills)
            result_map[shop['place_id']] = summary
        if skipped:
            print(
                f"[RECOMMEND] Summary: {len(summary_map)} LLM / {len(skipped)} fallback "
                f"dari {len(top_shops)} toko — batch tetap dikirim",
                flush=True,
            )
        return result_map
    except Exception as e:
        prefix = '[STRICT] ' if COFIND_DEV_LLM_STRICT else ''
        print(
            f"[RECOMMEND] {prefix}LLM summary error: {e}. "
            "Fallback deterministik untuk semua toko, rekomendasi tetap dikirim.",
            flush=True,
        )
        return {
            s['place_id']: _build_review_summary_deterministic(s, pills)
            for s in top_shops
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
    ('start', 4, 'Memahami konteks Anda'),
    ('profiles', 16, 'Mengumpulkan ulasan pengunjung'),
    ('keyword_expansion', 30, 'Mencari kata kunci yang relevan'),
    ('scoring', 48, 'Membandingkan tempat-tempat kandidat'),
    ('rerank', 68, 'Memilih yang paling cocok'),
    ('summary', 78, 'Menyusun rekomendasi untuk Anda'),
    ('done', 100, 'Rekomendasi siap'),
)
_RECOMMENDATION_PROGRESS_BY_STAGE = _build_recommendation_progress_map(
    _RECOMMENDATION_PROGRESS_STAGES
)


def _recommendation_progress(stage, **extra):
    payload = dict(
        _RECOMMENDATION_PROGRESS_BY_STAGE.get(stage)
        or {'stage': stage, 'percent': 0, 'next_percent': 100, 'label': ''}
    )
    payload.update(extra)
    return ('progress', payload)


def _recommendation_pipeline_events(prefs, _auth_user):
    """
    Rekomendasi 100% berbasis user review dengan LLM sebagai pengambil keputusan.
    Input tetap pill (tidak ada teks bebas dari user).
    Pipeline:
      1. Build profil review-only tiap toko (hanya reviews dari tabel `reviews`)
      2. Query: seed keyword PILL_MAPPING + ekspansi LLM yang tervalidasi kosakata korpus
      3. BM25 scoring korpus review (70%) + kategori rating (20%) + avg rating (10%)
      4. LLM rerank kandidat teratas (fit score + alasan + kutipan bukti tervalidasi),
         skor akhir = campuran fit LLM dan skor statistik; fallback ke urutan hybrid
      5. Hanya kembalikan toko yang memang lolos evidensi review
      6. LLM NLP summary merupakan ringkasan review user, kutipannya diverifikasi
         terhadap korpus review toko tersebut

    Generator: yield ('progress', payload) di tiap batas tahap, lalu tepat satu
    ('result', (body_dict, status_code)) di akhir. Autentikasi dan parsing body
    dilakukan pemanggil supaya generator ini bebas dari request context Flask.
    """
    request_t0 = time.perf_counter()
    stage_t0 = request_t0
    stage_ms = {}
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

        print(f"[RECOMMEND] Pills: {valid_pills}")
        yield _recommendation_progress('start')

        # Soft personalization: jangan tampilkan shop yang user tandai tidak relevan
        # untuk set preferensi yang sama (feedback thumbs-down).
        excluded_place_ids = set()
        try:
            excluded_place_ids = get_not_helpful_place_ids(_auth_user.get('id'), valid_pills)
            if excluded_place_ids:
                print(
                    f"[RECOMMEND] Exclude {len(excluded_place_ids)} shop dari feedback "
                    f"not_helpful user_id={_auth_user.get('id')}"
                )
        except Exception as fb_excl_err:
            print(f"[RECOMMEND] Gagal load feedback exclusion: {fb_excl_err}")

        # Konteks personalisasi (review sendiri + favorit) untuk tahap keputusan LLM.
        taste_profile = build_user_taste_profile(_auth_user.get('id'))
        user_taste_block = format_user_taste_prompt_block(taste_profile)

        # Query keywords: seed PILL_MAPPING; ekspansi LLM ditambahkan setelah korpus siap.
        search_keywords = _seed_search_keywords(valid_pills)
        llm_preference_keywords = []
        expansion_info = {}
        stage_ms['keyword_seed_ms'] = round((time.perf_counter() - stage_t0) * 1000, 1)
        stage_t0 = time.perf_counter()
        print(f"[RECOMMEND] Search keywords (seed pill): {search_keywords}")

        all_place_ids = _load_all_place_ids()
        if not all_place_ids:
            yield ('result', ({'status': 'error', 'message': 'Data coffee shop kosong.'}, 500))
            return
        facilities_index = _load_facilities_index()

        MAX_REC = 3
        THRESHOLD = 0.05  # ambang minimal skor review-based

        # --- Step 1: Build profiles (batch DB) ---
        print("[RECOMMEND] Step 1: batch load profil + reviews...", flush=True)
        profiles, shops_without_reviews = _build_profiles_for_recommendation(
            all_place_ids,
            facilities_index=facilities_index,
            excluded_place_ids=excluded_place_ids,
        )
        print(
            f"[RECOMMEND] Step 1 selesai: profiles={len(profiles)} "
            f"tanpa_review={len(shops_without_reviews)}",
            flush=True,
        )
        stage_ms['profile_load_ms'] = round((time.perf_counter() - stage_t0) * 1000, 1)
        stage_t0 = time.perf_counter()
        yield _recommendation_progress('profiles', shops_with_reviews=len(profiles))

        # --- Step 2: BM25 index + ekspansi keyword LLM yang tervalidasi korpus ---
        bm25_raw_by_place = {}
        bm25_norm_by_place = {}
        bm25_place_ids, bm25_model, corpus_tokens = [], None, []
        try:
            bm25_place_ids, bm25_model, corpus_tokens = build_bm25_index(
                profiles,
                tokenize_fn=tokenize_normalized,
            )
        except Exception as bm25_err:
            print(f"[RECOMMEND] BM25 gagal, fallback keyword scoring: {bm25_err}", flush=True)

        if llm_is_available():
            expansion_info = expand_pill_keywords(
                valid_pills,
                pill_labels=PILL_LABELS,
                pill_lexicon=search_keywords,
                chat_fn=_llm_chat_for_pipeline,
                sanitize_keywords=_filter_negative_search_keywords,
                corpus_vocabulary=corpus_vocabulary_from_tokens(corpus_tokens),
                parse_json_fn=_parse_llm_json_with_repair,
            )
            llm_preference_keywords = _filter_overbroad_meeting_keywords(
                expansion_info.get('keywords') or [],
                valid_pills,
            )
            print(
                f"[RECOMMEND] Ekspansi keyword LLM ({expansion_info.get('source')}): "
                f"{llm_preference_keywords} "
                f"(ditolak leksikon={expansion_info.get('rejected_lexicon')}, "
                f"ditolak korpus={expansion_info.get('rejected_vocabulary')} "
                f"contoh={expansion_info.get('rejected_vocabulary_sample')})",
                flush=True,
            )
        stage_ms['llm_keyword_expansion_ms'] = round((time.perf_counter() - stage_t0) * 1000, 1)
        stage_t0 = time.perf_counter()
        yield _recommendation_progress(
            'keyword_expansion', keywords_added=len(llm_preference_keywords)
        )

        query_keywords = list(dict.fromkeys(list(search_keywords) + list(llm_preference_keywords)))
        query_tokens = build_query_tokens(
            valid_pills,
            _expand_pill_to_keywords,
            search_keywords=query_keywords,
            tokenize_fn=tokenize_normalized,
        )
        if bm25_model is not None:
            bm25_raw_by_place = score_shops_bm25(bm25_place_ids, bm25_model, query_tokens)
            bm25_norm_by_place = normalize_bm25_scores(bm25_raw_by_place)
            print(
                f"[RECOMMEND] BM25 index: shops={len(bm25_place_ids)} "
                f"query_tokens={len(query_tokens)} "
                f"nonzero={sum(1 for v in bm25_raw_by_place.values() if v > 0)}",
                flush=True,
            )

        # --- Step 3: Hybrid scoring (70% BM25 + 20% kategori + 10% rating) ---
        print(
            f"[RECOMMEND] Step 3: hybrid scoring ({len(profiles)} profil)...",
            flush=True,
        )
        scored_candidates = []
        for profile in profiles:
            pid = profile.get('place_id')
            score_detail = _score_shop_by_user_reviews(
                profile,
                valid_pills,
                search_keywords=search_keywords,
                llm_preference_keywords=llm_preference_keywords,
                bm25_norm=bm25_norm_by_place.get(pid),
                bm25_raw=bm25_raw_by_place.get(pid),
            )
            total = score_detail['total_score']

            if total < THRESHOLD:
                if COFIND_RECOMMEND_VERBOSE:
                    print(
                        f"[RECOMMEND]   skip {profile.get('name')}: score={total:.4f}",
                        flush=True,
                    )
                continue

            evidence = _build_review_based_evidence(
                profile,
                score_detail,
                valid_pills,
                search_keywords=search_keywords,
            )
            # Tolak kandidat tanpa kutipan PENDUKUNG. Hanya caveat (keluhan pada
            # konteks yang sama) tidak cukup untuk merekomendasikan toko.
            if not _evidence_has_relevant_quotes(
                evidence, valid_pills, search_keywords=query_keywords,
            ):
                if COFIND_RECOMMEND_VERBOSE:
                    print(
                        f"[RECOMMEND]   skip {profile.get('name')}: score={total:.4f} tanpa kutipan relevan",
                        flush=True,
                    )
                continue

            scored_candidates.append({
                'place_id': pid,
                'name': profile.get('name', ''),
                'score': round(total, 4),
                'profile': profile,
                'score_detail': score_detail,
                'evidence': evidence,
            })
            if COFIND_RECOMMEND_VERBOSE:
                print(
                    f"[RECOMMEND]   keep {profile.get('name')}: score={total:.4f}",
                    flush=True,
                )

        scored_candidates.sort(key=lambda x: -x['score'])
        stage_ms['review_scoring_ms'] = round((time.perf_counter() - stage_t0) * 1000, 1)
        stage_t0 = time.perf_counter()
        print(
            f"[RECOMMEND] Step 3 selesai: {len(scored_candidates)} kandidat berbukti di atas ambang "
            f"(shops with reviews: {len(profiles)}) "
            f"scoring_ms={stage_ms['review_scoring_ms']}",
            flush=True,
        )
        yield _recommendation_progress('scoring', candidates=len(scored_candidates))

        # --- Step 4: LLM rerank kandidat teratas (fallback: urutan skor hybrid) ---
        rerank_backend = 'hybrid'
        rerank_telemetry = {}
        ranked_candidates = scored_candidates
        if scored_candidates and llm_is_available() and llm_rerank_enabled():
            rerank_result = llm_rerank_candidates(
                scored_candidates,
                valid_pills,
                pill_labels=PILL_LABELS,
                chat_fn=_llm_chat_for_pipeline,
                parse_json_fn=_parse_llm_json_with_repair,
                user_taste_block=user_taste_block,
                keyword_line=", ".join(query_keywords[:20]),
            ) or {}
            rerank_telemetry = rerank_result.get('telemetry') or {}
            if rerank_result.get('ranked'):
                ranked_candidates = rerank_result['ranked']
                rerank_backend = 'llm'
            else:
                print(
                    f"[RECOMMEND] Step 4: LLM rerank tidak dipakai "
                    f"({rerank_telemetry.get('backend')}: {rerank_telemetry.get('error')})",
                    flush=True,
                )
                if COFIND_DEV_LLM_STRICT:
                    raise RuntimeError(
                        f"LLM strict mode aktif: rerank gagal ({rerank_telemetry.get('error')})"
                    )

        # Ambil hingga MAX_REC, hanya yang masih punya bukti kutipan relevan.
        # Tidak memaksa 3 hasil jika hanya 1–2 toko yang berbukti.
        top_shops = []
        for shop in ranked_candidates:
            if len(top_shops) >= MAX_REC:
                break
            evidence = shop.get('evidence') or {}
            if not _evidence_has_relevant_quotes(
                evidence, valid_pills, search_keywords=query_keywords,
            ):
                print(
                    f"[RECOMMEND]   drop {shop.get('name')}: tanpa kutipan relevan setelah rerank",
                    flush=True,
                )
                continue
            top_shops.append(shop)
        stage_ms['rerank_ms'] = round((time.perf_counter() - stage_t0) * 1000, 1)
        stage_ms['rerank_backend'] = rerank_backend
        stage_t0 = time.perf_counter()
        print(
            f"[RECOMMEND] Step 4: {len(top_shops)}/{MAX_REC} toko berbukti dari rerank={rerank_backend} "
            f"(kandidat dinilai LLM={rerank_telemetry.get('scored_by_llm', 0)}, "
            f"kutipan tidak tergrounding={rerank_telemetry.get('ungrounded_quotes', 0)})",
            flush=True,
        )
        for rank, shop in enumerate(top_shops, 1):
            fit = shop.get('llm_fit') or {}
            print(
                f"[RECOMMEND]   #{rank} {shop.get('name')} score={shop.get('score')} "
                f"final={shop.get('final_score', shop.get('score'))} "
                f"llm_fit={fit.get('fit_score')}",
                flush=True,
            )

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
        print(
            f"[RECOMMEND] Step 5: generate summary untuk {len(top_shops)} shop...",
            flush=True,
        )
        yield _recommendation_progress('summary', shortlisted=len(top_shops))
        recommendations = _generate_llm_review_summary(
            top_shops,
            valid_pills,
            search_keywords=query_keywords,
        )
        stage_ms['llm_summary_ms'] = round((time.perf_counter() - stage_t0) * 1000, 1)
        stage_ms['total_ms'] = round((time.perf_counter() - request_t0) * 1000, 1)
        print(f"[METRIC] recommend_by_preferences {stage_ms}", flush=True)
        print(
            f"[RECOMMEND] Selesai: {len(recommendations)} rekomendasi dikirim ke client",
            flush=True,
        )

        yield _recommendation_progress('done', delivered=len(recommendations))
        yield ('result', ({
            'status': 'success',
            'preferences': valid_pills,
            'search_keywords': search_keywords,
            'llm_preference_keywords': llm_preference_keywords,
            'llm_pipeline': {
                'config': llm_pipeline_config(),
                'keyword_expansion': {
                    'source': expansion_info.get('source', 'disabled'),
                    'accepted': len(llm_preference_keywords),
                    'rejected_lexicon': expansion_info.get('rejected_lexicon', 0),
                    'rejected_vocabulary': expansion_info.get('rejected_vocabulary', 0),
                },
                'rerank': dict(rerank_telemetry, backend=rerank_backend),
                'personalization_used': bool(user_taste_block),
            },
            'recommendations': recommendations,
        }, 200))

    except Exception as e:
        import traceback
        print(f"[recommend-by-preferences] Error: {e}")
        print(traceback.format_exc())
        yield ('result', ({'status': 'error', 'message': str(e), 'recommendations': []}, 500))
    finally:
        try:
            if 'total_ms' not in stage_ms:
                stage_ms['total_ms'] = round((time.perf_counter() - request_t0) * 1000, 1)
            stage_ms.setdefault('rerank_backend', 'none')
            print(f"[METRIC] recommend_by_preferences_final {stage_ms}")
        except Exception:
            pass


def _read_recommendation_preferences():
    """Normalisasi body request menjadi daftar pill (maksimal 3)."""
    data = request.get_json(silent=True) or {}
    prefs = data.get('preferences') or []
    if not isinstance(prefs, list):
        prefs = [prefs] if prefs else []
    return [str(p).strip().lower() for p in prefs if str(p).strip()][:3]


@app.route('/api/recommend-by-preferences', methods=['POST'])
def api_recommend_by_preferences():
    """Rekomendasi pill (respons JSON sekali kirim). Progress diabaikan di sini."""
    prefs = _read_recommendation_preferences()
    auth_user, auth_error = _require_authenticated_user()
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
    auth_user, auth_error = _require_authenticated_user()
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
            print(f"[recommend-by-preferences/stream] Error: {stream_err}", flush=True)
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
        auth_user, auth_error = _require_authenticated_user()
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
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/recommend-by-preferences/feedback', methods=['GET'])
def api_recommend_feedback_get():
    """
    Ambil feedback user untuk set preferensi (+ opsional filter place_ids).
    Query: preferences=belajar,kerja & place_ids=id1,id2
    """
    try:
        auth_user, auth_error = _require_authenticated_user()
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
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/recommend-by-preferences/feedback/summary', methods=['GET'])
def api_recommend_feedback_summary():
    """
    Ringkasan evaluasi feedback (helpful vs not_helpful).
    Query opsional: preferences=belajar
    Membutuhkan login (dipakai evaluasi/admin tooling).
    """
    try:
        _auth_user, auth_error = _require_authenticated_user()
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
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/preference-suggestions', methods=['POST'])
def api_create_preference_suggestion():
    """
    User login mengirim saran pill preferensi baru ke admin.
    Body: { label: string, description?: string }
    """
    try:
        auth_user, auth_error = _require_authenticated_user()
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
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/preference-suggestions', methods=['GET'])
def admin_list_preference_suggestions():
    """Daftar saran preferensi pill untuk admin."""
    _, error_response = _require_admin()
    if error_response:
        return error_response

    try:
        page = max(int(request.args.get('page', 1)), 1)
        per_page = min(max(int(request.args.get('per_page', 10)), 1), 100)
        search = (request.args.get('search') or '').strip()
        status_filter = (request.args.get('status') or '').strip()

        result = list_preference_suggestions(
            page=page,
            per_page=per_page,
            search=search,
            status_filter=status_filter,
        )
        if not result.get('success'):
            return jsonify({
                'status': 'error',
                'message': result.get('error') or 'Gagal mengambil saran preferensi',
            }), 400
        return jsonify({
            'status': 'success',
            'items': result.get('items') or [],
            'pagination': result.get('pagination') or {},
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/preference-suggestions/<int:suggestion_id>', methods=['PUT'])
def admin_update_preference_suggestion(suggestion_id):
    """Perbarui status/catatan saran preferensi (admin)."""
    _, error_response = _require_admin()
    if error_response:
        return error_response

    try:
        data = request.get_json(silent=True) or {}
        result = update_preference_suggestion(
            suggestion_id,
            status=data.get('status') or 'pending',
            admin_notes=data.get('admin_notes'),
        )
        if not result.get('success'):
            status_code = 404 if 'tidak ditemukan' in (result.get('error') or '').lower() else 400
            return jsonify({
                'status': 'error',
                'message': result.get('error') or 'Gagal memperbarui saran',
            }), status_code
        return jsonify({
            'status': 'success',
            'message': 'Saran preferensi berhasil diperbarui',
        }), 200
    except Exception as e:
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

# Path untuk cache sentiment analysis
# Cache runtime disimpan di folder cache/ (di-gitignore), terpisah dari source tree frontend.
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
SENTIMENT_CACHE_PATH = os.path.join(CACHE_DIR, 'sentiment_cache.json')
CACHE_EXPIRY_DAYS = 7  # Cache berlaku 7 hari

def load_sentiment_cache():
    """Load sentiment cache dari file"""
    if os.path.exists(SENTIMENT_CACHE_PATH):
        try:
            with open(SENTIMENT_CACHE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_sentiment_cache(cache):
    """Save sentiment cache ke file"""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(SENTIMENT_CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[CACHE] Error saving cache: {e}")

# Path untuk cache ringkasan rekomendasi LLM (folder cache/ di-gitignore, sama seperti sentiment).
RECOMMENDATION_SUMMARY_CACHE_PATH = os.path.join(CACHE_DIR, 'recommendation_summary_cache.json')
RECOMMENDATION_SUMMARY_CACHE_VERSION = 'v5'

def load_recommendation_summary_cache():
    """Load cache ringkasan rekomendasi dari file."""
    if os.path.exists(RECOMMENDATION_SUMMARY_CACHE_PATH):
        try:
            with open(RECOMMENDATION_SUMMARY_CACHE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_recommendation_summary_cache(cache):
    """Save cache ringkasan rekomendasi ke file."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(RECOMMENDATION_SUMMARY_CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[CACHE] Error saving recommendation summary cache: {e}")

def _recommendation_summary_pill_key(pills):
    return '+'.join(sorted(str(p).strip().lower() for p in (pills or []) if str(p).strip()))

def _recommendation_summary_keyword_digest(search_keywords):
    """Hash stabil dari keyword intent (seed pill + ekspansi LLM)."""
    terms = _light_keyword_phrase_list(search_keywords or [])
    if not terms:
        return ''
    blob = '\n'.join(sorted(terms))
    return hashlib.sha1(blob.encode('utf-8')).hexdigest()[:12]

def _recommendation_summary_cache_key(place_id, pills, search_keywords=None):
    pill_part = _recommendation_summary_pill_key(pills)
    kw_digest = _recommendation_summary_keyword_digest(search_keywords)
    if kw_digest:
        return f"{str(place_id).strip()}::{pill_part}::{kw_digest}"
    return f"{str(place_id).strip()}::{pill_part}"

def _get_cached_recommendation_summary(place_id, pills, current_review_count, search_keywords=None):
    """Kembalikan ringkasan ter-cache jika masih valid (review_count sama, keyword sama, versi cocok, belum kedaluwarsa)."""
    try:
        cache = load_recommendation_summary_cache()
    except Exception:
        return None
    entry = cache.get(_recommendation_summary_cache_key(place_id, pills, search_keywords))
    if not isinstance(entry, dict):
        return None
    if entry.get('version') != RECOMMENDATION_SUMMARY_CACHE_VERSION:
        return None
    if entry.get('review_count') != current_review_count:
        return None
    if (time.time() - entry.get('timestamp', 0)) / (60 * 60 * 24) > CACHE_EXPIRY_DAYS:
        return None
    summary = entry.get('summary')
    return summary if summary else None

def _store_recommendation_summaries(entries, search_keywords=None):
    """entries: list of (place_id, pills, summary, review_count, shop_name)."""
    if not entries:
        return
    try:
        cache = load_recommendation_summary_cache()
    except Exception:
        cache = {}
    if not isinstance(cache, dict):
        cache = {}
    keyword_list = _light_keyword_phrase_list(search_keywords or [])
    for place_id, pills, summary, review_count, shop_name in entries:
        if not summary:
            continue
        cache[_recommendation_summary_cache_key(place_id, pills, search_keywords)] = {
            'version': RECOMMENDATION_SUMMARY_CACHE_VERSION,
            'timestamp': time.time(),
            'place_id': str(place_id).strip(),
            'pills': sorted(str(p).strip().lower() for p in (pills or []) if str(p).strip()),
            'search_keywords': keyword_list,
            'shop_name': shop_name or '',
            'review_count': review_count,
            'summary': summary,
        }
    try:
        save_recommendation_summary_cache(cache)
    except Exception as e:
        print(f"[CACHE] Error storing recommendation summaries: {e}")



def is_cache_valid(cache_entry, current_review_count):
    """Cek apakah cache masih valid"""
    if not cache_entry:
        return False
    
    # Cek apakah jumlah review berubah
    cached_review_count = cache_entry.get('review_count', 0)
    if cached_review_count != current_review_count:
        print(f"[CACHE] Review count changed: {cached_review_count} -> {current_review_count}")
        return False
    
    # Cek apakah cache sudah expired (> 7 hari)
    cached_timestamp = cache_entry.get('timestamp', 0)
    current_time = time.time()
    cache_age_days = (current_time - cached_timestamp) / (60 * 60 * 24)
    
    if cache_age_days > CACHE_EXPIRY_DAYS:
        print(f"[CACHE] Cache expired: {cache_age_days:.1f} days old")
        return False
    
    return True

# Endpoint untuk analisis sentimen review coffee shop
@app.route('/api/llm/analyze-sentiment', methods=['POST'])
def analyze_sentiment():
    """
    Endpoint untuk analisis sentimen review coffee shop berdasarkan place_id
    Menggunakan LLM untuk memahami konteks dan mengekstrak insight terstruktur
    
    FITUR CACHING:
    - Cache hasil analisis selama 7 hari
    - Auto-refresh jika ada review baru (jumlah review berubah)
    - Hemat token LLM dengan menghindari request berulang
    
    Request JSON:
    {
        "place_id": "ChIJ...",
        "shop_name": "Nama Coffee Shop",
        "reviews": [...] (optional, jika tidak ada akan dibaca dari database)
    }
    
    Response JSON:
    {
        "status": "success",
        "data": {
            "positif": ["WiFi kencang", "Suasana nyaman"],
            "negatif": ["Parkir terbatas"],
            "fasilitas": ["WiFi", "AC", "Colokan"],
            "cocok_untuk": ["Kerja remote", "Belajar"],
            "ringkasan": "Coffee shop dengan suasana cozy..."
        },
        "from_cache": true/false,
        "cache_age_days": 2.5
    }
    """
    try:
        data = request.get_json()
        if not data or 'place_id' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing required field: place_id'
            }), 400
        
        place_id = data.get('place_id', '').strip()
        shop_name = data.get('shop_name', 'Coffee Shop')
        provided_reviews = data.get('reviews', None)
        
        if not place_id:
            return jsonify({
                'status': 'error',
                'message': 'place_id cannot be empty'
            }), 400
        
        # Gunakan reviews dari request atau baca dari database
        if provided_reviews and len(provided_reviews) > 0:
            shop_reviews = provided_reviews
        else:
            # Baca reviews dari database
            reviews_result = get_reviews_for_shop(place_id, limit=50)
            reviews_list = reviews_result.get('reviews', []) if reviews_result.get('success') else []
            
            # Convert format dari database ke format yang diharapkan
            shop_reviews = []
            for r in reviews_list:
                shop_reviews.append({
                    'text': r.get('text', ''),
                    'rating': r.get('rating', 0),
                    'author_name': r.get('username', 'Anonim')
                })
            
            if not shop_reviews:
                return jsonify({
                    'status': 'error',
                    'message': 'Tidak ada review untuk coffee shop ini di database'
                }), 404
        
        if not shop_reviews or len(shop_reviews) == 0:
            return jsonify({
                'status': 'error',
                'message': 'Tidak ada review untuk coffee shop ini'
            }), 404

        facilities_text = ""
        facilities_path = os.path.join('frontend-cofind', 'src', 'data', 'facilities.json')
        try:
            if os.path.exists(facilities_path):
                with open(facilities_path, 'r', encoding='utf-8') as f:
                    facilities_data = json.load(f)
                    shop_fac = facilities_data.get('facilities_by_place_id', {}).get(place_id, {})
                    facilities_text = _format_facilities_to_text(shop_fac)
        except Exception as facilities_err:
            print(f"[SENTIMENT] Failed to load facilities fallback: {facilities_err}")

        analysis = _get_structured_review_analysis(
            place_id,
            shop_name,
            shop_reviews,
            facilities_text=facilities_text,
            use_cache=True,
        )
        legacy_data = {
            'positif': analysis.get('highlights', [])[:5],
            'negatif': analysis.get('warnings', [])[:3],
            'fasilitas': analysis.get('aspect_keywords', {}).get('fasilitas', [])[:6],
            'cocok_untuk': analysis.get('cocok_untuk', [])[:4],
            'ringkasan': analysis.get('summary', ''),
            'multi_aspect': analysis.get('aspects', {}),
            'overall_sentiment': analysis.get('overall_sentiment', 'netral'),
            'top_terms': analysis.get('top_terms', []),
            'quality': analysis.get('quality', {}),
        }
        return jsonify({
            'status': 'success',
            'data': legacy_data,
            'structured': analysis,
            'from_cache': analysis.get('_from_cache', False),
            'cache_age_days': analysis.get('_cache_age_days'),
            'reviews_analyzed': analysis.get('quality', {}).get('used_reviews', 0),
        })
            
    except Exception as e:
        print(f"[SENTIMENT] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


if __name__ == '__main__':
    # Jalankan app secara langsung untuk pengembangan
    # Gunakan host 0.0.0.0 untuk bind ke semua interface; port default 5000 (override lewat FLASK_RUN_PORT / PORT untuk E2E)
    # Debug False untuk menghindari restart cycle saat development
    _run_port = int(os.getenv('FLASK_RUN_PORT') or os.getenv('PORT') or '5000')
    app.run(debug=False, host='0.0.0.0', port=_run_port, threaded=True)

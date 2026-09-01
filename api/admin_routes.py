"""Endpoint panel admin: dashboard, user, coffee shop, review, dan pengaturan."""

from __future__ import annotations

import re
import time
from datetime import datetime

from flask import Blueprint, jsonify, request

from auth_guards import require_admin
from auth_utils import hash_password, update_user_profile
from db_backend import dict_from_row, get_connection
from db_helpers import paginate_query
from facilities_store import (
    count_enabled_facilities,
    default_facilities_entry,
    format_facilities_to_text,
    load_facilities_index,
    save_facilities_index,
)
from llm_backend import HF_MODEL, llm_is_available
from logging_config import get_logger
from preference_suggestion_utils import (
    ensure_preference_suggestions_table,
    list_preference_suggestions,
    update_preference_suggestion,
)
from cache_paths import RERANK_CACHE_EXPIRY_DAYS
from recommendation_feedback_utils import ensure_recommendation_feedback_table

bp = Blueprint('admin', __name__)
LOG_API = get_logger('api')
LOG_ADMIN = get_logger('admin')

@bp.route('/api/admin/dashboard', methods=['GET'])
def admin_dashboard():
    admin_user, error_response = require_admin()
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
            LOG_API.exception("admin_dashboard gagal")
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
            LOG_ADMIN.warning(f"dashboard recommendation_feedback: {fb_err}")

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
                LIMIT 24
                '''
            ).fetchall()
            retired_pills = frozenset({'bersantai'})
            for row in pref_rows or []:
                rd = dict_from_row(cursor, row) or {}
                preferences_key = rd.get('preferences_key') or '(kosong)'
                key_pills = {
                    part.strip().lower()
                    for part in str(preferences_key).split('+')
                    if part.strip()
                }
                if key_pills & retired_pills:
                    continue
                feedback_by_preference.append({
                    'preferences_key': preferences_key,
                    'helpful': _safe_int(rd.get('helpful')),
                    'not_helpful': _safe_int(rd.get('not_helpful')),
                    'total': _safe_int(rd.get('total')),
                })
                if len(feedback_by_preference) >= 8:
                    break
        except Exception as pref_err:
            LOG_ADMIN.warning(f"dashboard feedback_by_preference: {pref_err}")

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
            LOG_ADMIN.warning(f"dashboard top_contributors: {contrib_err}")

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
            LOG_ADMIN.warning(f"dashboard most_reviewed_shops: {shop_err}")

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
            LOG_ADMIN.warning(f"dashboard reviews_trend: {trend_err}")

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
            LOG_ADMIN.warning(f"dashboard preference_suggestions: {sug_err}")

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
        LOG_API.exception("admin_dashboard gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/admin/users', methods=['GET'])
def admin_get_users():
    _, error_response = require_admin()
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

        rows = paginate_query(
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
        LOG_API.exception("admin_get_users gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/admin/users/<int:user_id>', methods=['PUT'])
def admin_update_user(user_id):
    admin_user, error_response = require_admin()
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

        new_password = (data.get('password') or '').strip()
        if new_password:
            if len(new_password) < 6:
                conn.close()
                return jsonify({'status': 'error', 'message': 'Password minimal 6 karakter.'}), 400
            cursor.execute(
                'UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?',
                (hash_password(new_password), datetime.utcnow().isoformat(), user_id),
            )
            if user_id != admin_user.get('id'):
                cursor.execute('DELETE FROM sessions WHERE user_id = ?', (user_id,))

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
        LOG_API.exception("admin_update_user gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/admin/users', methods=['POST'])
def admin_create_user():
    from auth_utils import hash_password as _hash_password
    admin_user, error_response = require_admin()
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
        LOG_API.exception("admin_create_user gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
def admin_delete_user(user_id):
    admin_user, error_response = require_admin()
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
        LOG_API.exception("admin_delete_user gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/admin/shops', methods=['GET'])
def admin_get_shops():
    _, error_response = require_admin()
    if error_response:
        return error_response

    try:
        page = max(int(request.args.get('page', 1)), 1)
        per_page = min(max(int(request.args.get('per_page', 10)), 1), 100)
        search = (request.args.get('search') or '').strip().lower()

        conn = get_connection()
        cursor = conn.cursor()
        facilities_index = load_facilities_index()

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

        rows = paginate_query(
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
            facilities_text = format_facilities_to_text(facility_entry)
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
                'facility_count': count_enabled_facilities(facilities_obj),
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
        LOG_API.exception("admin_get_shops gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/admin/facilities/<place_id>', methods=['GET'])
def admin_get_facility_entry(place_id):
    _, error_response = require_admin()
    if error_response:
        return error_response

    try:
        facilities_index = load_facilities_index()

        conn = get_connection()
        cursor = conn.cursor()
        shop_row = cursor.execute('SELECT name FROM coffee_shops WHERE place_id = ?', (place_id,)).fetchone()
        conn.close()

        shop_name = shop_row[0] if shop_row else ''
        entry = facilities_index.get(place_id) or default_facilities_entry(place_id, shop_name)
        if shop_name and not entry.get('name'):
            entry['name'] = shop_name

        return jsonify({'status': 'success', 'item': entry}), 200
    except Exception as e:
        LOG_API.exception("admin_get_facility_entry gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/admin/facilities/<place_id>', methods=['PUT'])
def admin_update_facility_entry(place_id):
    _, error_response = require_admin()
    if error_response:
        return error_response

    try:
        data = request.get_json() or {}
        entry = data.get('item')
        if not isinstance(entry, dict):
            return jsonify({'status': 'error', 'message': 'item harus berupa object JSON'}), 400

        facilities_index = load_facilities_index()

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
        save_facilities_index(facilities_index)

        return jsonify({'status': 'success', 'message': 'Facilities JSON berhasil diperbarui'}), 200
    except Exception as e:
        LOG_API.exception("admin_update_facility_entry gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/admin/shops', methods=['POST'])
def admin_create_shop():
    _, error_response = require_admin()
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
        LOG_API.exception("admin_create_shop gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/admin/shops/<place_id>', methods=['PUT'])
def admin_update_shop(place_id):
    _, error_response = require_admin()
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
        LOG_API.exception("admin_update_shop gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/admin/shops/<place_id>', methods=['DELETE'])
def admin_delete_shop(place_id):
    _, error_response = require_admin()
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
        LOG_API.exception("admin_delete_shop gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/admin/reviews', methods=['GET'])
def admin_get_reviews():
    _, error_response = require_admin()
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

        rows = paginate_query(
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
        LOG_API.exception("admin_get_reviews gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/admin/review-reports', methods=['GET'])
def admin_get_review_reports():
    _, error_response = require_admin()
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

        rows = paginate_query(
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
        LOG_API.exception("admin_get_review_reports gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/admin/review-reports/<int:report_id>', methods=['PUT'])
def admin_update_review_report(report_id):
    _, error_response = require_admin()
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
        LOG_API.exception("admin_update_review_report gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/admin/reviews/<int:review_id>', methods=['DELETE'])
def admin_delete_review(review_id):
    _, error_response = require_admin()
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
        LOG_API.exception("admin_delete_review gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/admin/settings', methods=['GET'])
def admin_get_settings_summary():
    _, error_response = require_admin()
    if error_response:
        return error_response

    try:
        return jsonify({
            'status': 'success',
            'settings': {
                'llm_available': llm_is_available(),
                'llm_model': HF_MODEL,
                'api_base_note': 'Frontend memakai VITE_API_BASE untuk mengakses Flask API',
                'rerank_cache_expiry_days': RERANK_CACHE_EXPIRY_DAYS,
            }
        }), 200
    except Exception as e:
        LOG_API.exception("admin_get_settings_summary gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/admin/preference-suggestions', methods=['GET'])
def admin_list_preference_suggestions():
    """Daftar saran preferensi pill untuk admin."""
    _, error_response = require_admin()
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
        LOG_API.exception("admin_list_preference_suggestions gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/admin/preference-suggestions/<int:suggestion_id>', methods=['PUT'])
def admin_update_preference_suggestion(suggestion_id):
    """Perbarui status/catatan saran preferensi (admin)."""
    _, error_response = require_admin()
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
        LOG_API.exception("admin_update_preference_suggestion gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500


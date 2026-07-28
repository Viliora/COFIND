"""
Favorites Management Utilities
CRUD operations for favorite coffee shops
"""

from datetime import datetime
from auth_utils import get_db_connection


def _resolve_shop_row(cursor, place_id):
    """Cari baris coffee_shops: exact place_id, lalu TRIM(place_id)."""
    trimmed = (place_id or '').strip()
    if not trimmed:
        return None
    shop = cursor.execute(
        'SELECT id, place_id FROM coffee_shops WHERE place_id = ?',
        (trimmed,),
    ).fetchone()
    if shop:
        return shop
    shop = cursor.execute(
        'SELECT id, place_id FROM coffee_shops WHERE TRIM(place_id) = ?',
        (trimmed,),
    ).fetchone()
    return shop


def add_favorite(user_id, place_id):
    """Add a coffee shop to favorites"""
    conn = None
    try:
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return {'success': False, 'error': 'Invalid user_id'}

        trimmed_pid = (place_id or '').strip()
        if not trimmed_pid:
            return {'success': False, 'error': 'place_id required'}

        conn = get_db_connection()
        cursor = conn.cursor()

        existing = cursor.execute(
            'SELECT id FROM favorites WHERE user_id = ? AND (place_id = ? OR TRIM(place_id) = ?)',
            (user_id, trimmed_pid, trimmed_pid),
        ).fetchone()

        if existing:
            return {'success': False, 'error': 'Already in favorites'}

        shop = _resolve_shop_row(cursor, trimmed_pid)
        if not shop:
            return {'success': False, 'error': 'Coffee shop not found'}

        shop_id = shop[0]
        canonical_place_id = shop[1] if len(shop) > 1 else trimmed_pid

        cursor.execute(
            '''
            INSERT INTO favorites (user_id, shop_id, place_id, added_at)
            VALUES (?, ?, ?, ?)
            ''',
            (user_id, shop_id, canonical_place_id, datetime.utcnow().isoformat()),
        )

        conn.commit()
        favorite_id = cursor.lastrowid

        return {
            'success': True,
            'favorite_id': favorite_id,
            'message': 'Added to favorites',
        }
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return {'success': False, 'error': str(e)}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def remove_favorite(user_id, place_id):
    """Remove a coffee shop from favorites"""
    conn = None
    try:
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return {'success': False, 'error': 'Invalid user_id'}

        trimmed = (place_id or '').strip()
        if not trimmed:
            return {'success': False, 'error': 'place_id required'}

        conn = get_db_connection()
        cursor = conn.cursor()

        favorite = cursor.execute(
            'SELECT id FROM favorites WHERE user_id = ? AND (place_id = ? OR TRIM(place_id) = ?)',
            (user_id, trimmed, trimmed),
        ).fetchone()

        if not favorite:
            return {'success': False, 'error': 'Not in favorites'}

        cursor.execute(
            'DELETE FROM favorites WHERE user_id = ? AND (place_id = ? OR TRIM(place_id) = ?)',
            (user_id, trimmed, trimmed),
        )

        conn.commit()
        return {'success': True, 'message': 'Removed from favorites'}
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return {'success': False, 'error': str(e)}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def get_user_favorites(user_id, limit=100):
    """Get all favorites for a user"""
    try:
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return {'success': False, 'error': 'Invalid user_id'}

        conn = get_db_connection()
        cursor = conn.cursor()

        favorites = cursor.execute('''
            SELECT f.id, f.place_id, f.added_at,
                   c.name, c.address, c.rating
            FROM favorites f
            LEFT JOIN coffee_shops c ON f.place_id = c.place_id
            WHERE f.user_id = ?
            ORDER BY f.added_at DESC
            LIMIT ?
        ''', (user_id, limit)).fetchall()

        conn.close()

        favorite_list = []
        for fav in favorites:
            favorite_list.append({
                'id': fav[0],
                'place_id': fav[1],
                'created_at': fav[2],
                'shop': {
                    'name': fav[3],
                    'address': fav[4],
                    'rating': fav[5]
                } if fav[3] else None
            })

        return {'success': True, 'favorites': favorite_list}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def is_favorite(user_id, place_id):
    """Check if a shop is in user's favorites"""
    try:
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return {'success': False, 'error': 'Invalid user_id'}

        trimmed = (place_id or '').strip()
        if not trimmed:
            return {'success': True, 'is_favorite': False}

        conn = get_db_connection()
        cursor = conn.cursor()

        favorite = cursor.execute(
            'SELECT id FROM favorites WHERE user_id = ? AND (place_id = ? OR TRIM(place_id) = ?)',
            (user_id, trimmed, trimmed),
        ).fetchone()

        conn.close()

        return {
            'success': True,
            'is_favorite': favorite is not None
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_favorite_count(place_id):
    """Get number of times a coffee shop is favorited"""
    try:
        trimmed = (place_id or '').strip()
        if not trimmed:
            return {'success': True, 'count': 0}

        conn = get_db_connection()
        cursor = conn.cursor()

        count = cursor.execute(
            'SELECT COUNT(*) FROM favorites WHERE place_id = ? OR TRIM(place_id) = ?',
            (trimmed, trimmed),
        ).fetchone()[0]

        conn.close()

        return {
            'success': True,
            'count': count
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

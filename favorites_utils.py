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


def get_co_favorited_shops(place_id, limit=8, exclude_user_id=None):
    """
    Coffee shop lain yang paling sering difavoritkan bersamaan oleh user
    yang juga memfavoritkan place_id ini (item-based collaborative signal).

    exclude_user_id: jika di-set, hanya user_id lain yang dipakai sebagai sumber
    f1 (pengguna yang memfavoritkan toko ini); pola favorit pengguna tersebut
    tidak ikut menghitung rekomendasi.
    """
    conn = None
    try:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 8
        limit = max(1, min(limit, 20))

        ex_uid = None
        if exclude_user_id is not None:
            try:
                ex_uid = int(exclude_user_id)
            except (TypeError, ValueError):
                ex_uid = None

        trimmed = (place_id or '').strip()
        if not trimmed:
            return {'success': True, 'shops': []}

        conn = get_db_connection()
        cursor = conn.cursor()

        exclude_clause = ""
        params_inner = [trimmed, trimmed]
        if ex_uid is not None:
            exclude_clause = " AND f1.user_id != ?"
            params_inner.append(ex_uid)
        params_inner.append(limit)

        sql = f'''
SELECT c.place_id, c.name, c.address, c.rating, COALESCE(c.total_reviews, 0)
FROM (
    SELECT TRIM(f2.place_id) AS pid, COUNT(DISTINCT f2.user_id) AS w
    FROM favorites f1
    INNER JOIN favorites f2 ON f1.user_id = f2.user_id
    WHERE TRIM(f1.place_id) = ?
      AND f2.place_id IS NOT NULL
      AND TRIM(f2.place_id) != ?{exclude_clause}
    GROUP BY TRIM(f2.place_id)
    ORDER BY w DESC
    LIMIT ?
) sub
INNER JOIN coffee_shops c ON TRIM(c.place_id) = sub.pid
ORDER BY sub.w DESC
'''
        cursor.execute(sql, tuple(params_inner))
        rows = cursor.fetchall()

        shops = []
        for row in rows:
            tr = row[4] if len(row) > 4 else 0
            addr = row[2] or ''
            shops.append({
                'place_id': row[0],
                'name': row[1],
                'address': addr,
                'vicinity': addr,
                'rating': row[3],
                'total_reviews': tr,
                'user_ratings_total': tr,
            })

        return {'success': True, 'shops': shops}
    except Exception as e:
        return {'success': False, 'error': str(e), 'shops': []}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

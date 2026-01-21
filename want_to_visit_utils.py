"""
Want-to-visit Management Utilities
CRUD operations for want_to_visit coffee shops
"""
from datetime import datetime
from auth_utils import get_db_connection

def add_want_to_visit(user_id, place_id):
    """Add a coffee shop to want_to_visit"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        existing = cursor.execute(
            'SELECT id FROM want_to_visit WHERE user_id = ? AND place_id = ?',
            (user_id, place_id)
        ).fetchone()

        if existing:
            return {'success': False, 'error': 'Already in want_to_visit'}

        cursor.execute(
            '''
            INSERT INTO want_to_visit (user_id, place_id, added_at)
            VALUES (?, ?, ?)
            ''',
            (user_id, place_id, datetime.utcnow().isoformat())
        )

        conn.commit()
        want_id = cursor.lastrowid
        conn.close()

        return {
            'success': True,
            'want_to_visit_id': want_id,
            'message': 'Added to want_to_visit'
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def remove_want_to_visit(user_id, place_id):
    """Remove a coffee shop from want_to_visit"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        existing = cursor.execute(
            'SELECT id FROM want_to_visit WHERE user_id = ? AND place_id = ?',
            (user_id, place_id)
        ).fetchone()

        if not existing:
            return {'success': False, 'error': 'Not in want_to_visit'}

        cursor.execute(
            'DELETE FROM want_to_visit WHERE user_id = ? AND place_id = ?',
            (user_id, place_id)
        )

        conn.commit()
        conn.close()

        return {'success': True, 'message': 'Removed from want_to_visit'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_user_want_to_visit(user_id, limit=100):
    """Get all want_to_visit for a user"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        rows = cursor.execute(
            '''
            SELECT w.id, w.place_id, w.added_at,
                   c.name, c.address, c.rating, c.user_ratings_total
            FROM want_to_visit w
            LEFT JOIN coffee_shops c ON w.place_id = c.place_id
            WHERE w.user_id = ?
            ORDER BY w.added_at DESC
            LIMIT ?
            ''',
            (user_id, limit)
        ).fetchall()

        conn.close()

        want_list = []
        for row in rows:
            want_list.append({
                'id': row[0],
                'place_id': row[1],
                'added_at': row[2],
                'shop': {
                    'name': row[3],
                    'address': row[4],
                    'rating': row[5],
                    'user_ratings_total': row[6]
                } if row[3] else None
            })

        return {'success': True, 'want_to_visit': want_list}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def is_want_to_visit(user_id, place_id):
    """Check if a shop is in user's want_to_visit"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        existing = cursor.execute(
            'SELECT id FROM want_to_visit WHERE user_id = ? AND place_id = ?',
            (user_id, place_id)
        ).fetchone()

        conn.close()

        return {
            'success': True,
            'is_want_to_visit': existing is not None
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

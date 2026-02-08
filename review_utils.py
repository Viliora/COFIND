"""
Review Management Utilities
CRUD operations for coffee shop reviews
"""

import sqlite3
from datetime import datetime
from auth_utils import get_db_connection

def _validate_rating(r, allow_none=False):
    if allow_none and r is None:
        return True
    return r is not None and 1 <= r <= 5

def create_review(user_id, place_id, rating, text='', rating_makanan=None, rating_layanan=None, rating_suasana=None, photos=None):
    """Create a new review with optional category ratings and photos."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if not _validate_rating(rating):
            return {'success': False, 'error': 'Rating must be between 1 and 5'}
        if rating_makanan is not None and not _validate_rating(rating_makanan):
            return {'success': False, 'error': 'Rating makanan must be between 1 and 5'}
        if rating_layanan is not None and not _validate_rating(rating_layanan):
            return {'success': False, 'error': 'Rating layanan must be between 1 and 5'}
        if rating_suasana is not None and not _validate_rating(rating_suasana):
            return {'success': False, 'error': 'Rating suasana must be between 1 and 5'}
        
        existing = cursor.execute(
            'SELECT id FROM reviews WHERE user_id = ? AND place_id = ?',
            (user_id, place_id)
        ).fetchone()
        if existing:
            return {'success': False, 'error': 'You already have a review for this shop'}
        
        shop = cursor.execute(
            'SELECT id FROM coffee_shops WHERE place_id = ?',
            (place_id,)
        ).fetchone()
        if not shop:
            return {'success': False, 'error': 'Coffee shop not found'}
        shop_id = shop[0]
        
        cursor.execute('''
            INSERT INTO reviews (user_id, shop_id, place_id, rating, review_text, rating_makanan, rating_layanan, rating_suasana, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, shop_id, place_id, rating, text or '', rating_makanan, rating_layanan, rating_suasana, datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
        review_id = cursor.lastrowid
        
        photos = photos or []
        for i, p in enumerate(photos[:5]):  # max 5 photos
            caption = (p.get('caption') or '').strip() if isinstance(p, dict) else ''
            image_data = p.get('image_data') if isinstance(p, dict) else None
            cursor.execute(
                'INSERT INTO review_photos (review_id, caption, image_data) VALUES (?, ?, ?)',
                (review_id, caption or None, image_data)
            )
        
        conn.commit()
        row = cursor.execute(
            'SELECT id, user_id, shop_id, place_id, rating, review_text, rating_makanan, rating_layanan, rating_suasana, created_at, updated_at FROM reviews WHERE id = ?',
            (review_id,)
        ).fetchone()
        photos_out = cursor.execute(
            'SELECT id, caption, image_data FROM review_photos WHERE review_id = ? ORDER BY id',
            (review_id,)
        ).fetchall()
        conn.close()
        
        return {
            'success': True,
            'review': {
                'id': row[0],
                'user_id': row[1],
                'shop_id': row[2],
                'place_id': row[3],
                'rating': row[4],
                'text': row[5],
                'rating_makanan': row[6],
                'rating_layanan': row[7],
                'rating_suasana': row[8],
                'created_at': row[9],
                'updated_at': row[10],
                'photos': [{'id': p[0], 'caption': p[1], 'image_data': p[2]} for p in photos_out]
            }
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_review(review_id):
    """Get a single review with photos."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        review = cursor.execute(
            'SELECT id, user_id, shop_id, place_id, rating, review_text, rating_makanan, rating_layanan, rating_suasana, created_at, updated_at FROM reviews WHERE id = ?',
            (review_id,)
        ).fetchone()
        if not review:
            conn.close()
            return {'success': False, 'error': 'Review not found'}
        photos = cursor.execute(
            'SELECT id, caption, image_data FROM review_photos WHERE review_id = ? ORDER BY id',
            (review_id,)
        ).fetchall()
        conn.close()
        return {
            'success': True,
            'review': {
                'id': review[0],
                'user_id': review[1],
                'shop_id': review[2],
                'place_id': review[3],
                'rating': review[4],
                'text': review[5],
                'rating_makanan': review[6],
                'rating_layanan': review[7],
                'rating_suasana': review[8],
                'created_at': review[9],
                'updated_at': review[10],
                'photos': [{'id': p[0], 'caption': p[1], 'image_data': p[2]} for p in photos]
            }
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_reviews_for_shop(place_id, limit=50, current_user_id=None):
    """Get all reviews for a coffee shop. Optionally include like_count and user_has_liked when current_user_id is set."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        reviews = cursor.execute('''
            SELECT r.id, r.user_id, r.shop_id, r.place_id, r.rating, r.review_text,
                   r.rating_makanan, r.rating_layanan, r.rating_suasana,
                   r.created_at, r.updated_at, u.username
            FROM reviews r
            LEFT JOIN users u ON r.user_id = u.id
            WHERE r.place_id = ?
            ORDER BY r.created_at DESC
            LIMIT ?
        ''', (place_id, limit)).fetchall()
        
        user_ids = list({r[1] for r in reviews if r[1]})
        user_total_reviews = {}
        if user_ids:
            placeholders = ','.join('?' * len(user_ids))
            counts = cursor.execute(
                f'SELECT user_id, COUNT(*) FROM reviews WHERE user_id IN ({placeholders}) GROUP BY user_id',
                user_ids
            ).fetchall()
            user_total_reviews = {row[0]: row[1] for row in counts}
        review_ids = [r[0] for r in reviews]
        like_counts = {}
        user_liked = {}
        if review_ids:
            placeholders = ','.join('?' * len(review_ids))
            like_rows = cursor.execute(
                f'SELECT review_id, COUNT(*) FROM review_likes WHERE review_id IN ({placeholders}) GROUP BY review_id',
                review_ids
            ).fetchall()
            like_counts = {row[0]: row[1] for row in like_rows}
            if current_user_id:
                liked_rows = cursor.execute(
                    'SELECT review_id FROM review_likes WHERE user_id = ? AND review_id IN (' + placeholders + ')',
                    [current_user_id] + review_ids
                ).fetchall()
                user_liked = {row[0]: True for row in liked_rows}
        review_list = []
        for review in reviews:
            review_id = review[0]
            uid = review[1]
            photos = cursor.execute(
                'SELECT id, caption, image_data FROM review_photos WHERE review_id = ? ORDER BY id',
                (review_id,)
            ).fetchall()
            review_list.append({
                'id': review_id,
                'user_id': uid,
                'shop_id': review[2],
                'place_id': review[3],
                'rating': review[4],
                'text': review[5],
                'rating_makanan': review[6],
                'rating_layanan': review[7],
                'rating_suasana': review[8],
                'created_at': review[9],
                'updated_at': review[10],
                'username': review[11],
                'full_name': review[11],
                'photos': [{'id': p[0], 'caption': p[1], 'image_data': p[2]} for p in photos],
                'user_total_reviews': user_total_reviews.get(uid, 0),
                'like_count': like_counts.get(review_id, 0),
                'user_has_liked': user_liked.get(review_id, False)
            })
        conn.close()
        
        return {'success': True, 'reviews': review_list}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_user_review_stats(user_id):
    """Get total review count and average rating for a user."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        row = cursor.execute(
            'SELECT COUNT(*), AVG(rating) FROM reviews WHERE user_id = ?',
            (user_id,)
        ).fetchone()
        conn.close()
        return {
            'success': True,
            'review_count': row[0] or 0,
            'average_rating': round(row[1], 2) if row[1] is not None else 0
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_user_reviews(user_id, limit=50):
    """Get all reviews by a user with shop name and optional photos."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        reviews = cursor.execute('''
            SELECT r.id, r.user_id, r.shop_id, r.place_id, r.rating, r.review_text,
                   r.rating_makanan, r.rating_layanan, r.rating_suasana,
                   r.created_at, r.updated_at, c.name AS shop_name
            FROM reviews r
            LEFT JOIN coffee_shops c ON r.place_id = c.place_id
            WHERE r.user_id = ?
            ORDER BY r.created_at DESC
            LIMIT ?
        ''', (user_id, limit)).fetchall()
        review_list = []
        for review in reviews:
            review_id = review[0]
            photos = cursor.execute(
                'SELECT id, caption, image_data FROM review_photos WHERE review_id = ? ORDER BY id',
                (review_id,)
            ).fetchall()
            like_count = cursor.execute(
                'SELECT COUNT(*) FROM review_likes WHERE review_id = ?', (review_id,)
            ).fetchone()[0]
            review_list.append({
                'id': review_id,
                'user_id': review[1],
                'shop_id': review[2],
                'place_id': review[3],
                'rating': review[4],
                'text': review[5],
                'rating_makanan': review[6],
                'rating_layanan': review[7],
                'rating_suasana': review[8],
                'created_at': review[9],
                'updated_at': review[10],
                'shop_name': review[11],
                'photos': [{'id': p[0], 'caption': p[1], 'image_data': p[2]} for p in photos],
                'like_count': like_count
            })
        conn.close()
        return {'success': True, 'reviews': review_list}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def update_review(review_id, user_id, rating=None, text=None, rating_makanan=None, rating_layanan=None, rating_suasana=None, photos=None):
    """Update a review (rating, text, rating_makanan/layanan/suasana, photos)."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        review = cursor.execute(
            'SELECT id, user_id, shop_id, place_id, rating, review_text, rating_makanan, rating_layanan, rating_suasana FROM reviews WHERE id = ?',
            (review_id,)
        ).fetchone()
        if not review:
            conn.close()
            return {'success': False, 'error': 'Review not found'}
        if review[1] != user_id:
            conn.close()
            return {'success': False, 'error': 'Unauthorized'}
        new_rating = rating if rating is not None else review[4]
        new_text = text if text is not None else review[5]
        def _opt_rating(val, current):
            if val is None:
                return current
            return val if 1 <= val <= 5 else None
        new_makanan = _opt_rating(rating_makanan, review[6])
        new_layanan = _opt_rating(rating_layanan, review[7])
        new_suasana = _opt_rating(rating_suasana, review[8])
        if rating is not None and not _validate_rating(rating):
            conn.close()
            return {'success': False, 'error': 'Rating must be between 1 and 5'}
        if rating_makanan is not None and not _validate_rating(rating_makanan, allow_none=True):
            conn.close()
            return {'success': False, 'error': 'Rating makanan must be between 1 and 5'}
        if rating_layanan is not None and not _validate_rating(rating_layanan, allow_none=True):
            conn.close()
            return {'success': False, 'error': 'Rating layanan must be between 1 and 5'}
        if rating_suasana is not None and not _validate_rating(rating_suasana, allow_none=True):
            conn.close()
            return {'success': False, 'error': 'Rating suasana must be between 1 and 5'}
        cursor.execute('''
            UPDATE reviews
            SET rating = ?, review_text = ?, rating_makanan = ?, rating_layanan = ?, rating_suasana = ?, updated_at = ?
            WHERE id = ?
        ''', (new_rating, new_text, new_makanan, new_layanan, new_suasana, datetime.utcnow().isoformat(), review_id))
        if photos is not None:
            cursor.execute('DELETE FROM review_photos WHERE review_id = ?', (review_id,))
            for p in (photos or [])[:5]:
                caption = (p.get('caption') or '').strip() if isinstance(p, dict) else ''
                image_data = p.get('image_data') if isinstance(p, dict) else None
                if image_data:
                    cursor.execute(
                        'INSERT INTO review_photos (review_id, caption, image_data) VALUES (?, ?, ?)',
                        (review_id, caption or None, image_data)
                    )
        conn.commit()
        conn.close()
        result = get_review(review_id)
        return result
    except Exception as e:
        return {'success': False, 'error': str(e)}

def delete_review(review_id, user_id):
    """Delete a review"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check review exists and user owns it
        review = cursor.execute(
            'SELECT * FROM reviews WHERE id = ?',
            (review_id,)
        ).fetchone()
        
        if not review:
            return {'success': False, 'error': 'Review not found'}
        
        if review[1] != user_id:
            return {'success': False, 'error': 'Unauthorized'}
        
        # Delete review
        cursor.execute('DELETE FROM reviews WHERE id = ?', (review_id,))
        conn.commit()
        conn.close()
        
        return {'success': True, 'message': 'Review deleted'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_average_rating(place_id):
    """Get average rating for a coffee shop"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        result = cursor.execute(
            'SELECT AVG(rating), COUNT(*) FROM reviews WHERE place_id = ?',
            (place_id,)
        ).fetchone()
        
        conn.close()
        
        avg_rating = result[0] or 0
        review_count = result[1] or 0
        
        return {
            'success': True,
            'average_rating': round(avg_rating, 2),
            'review_count': review_count
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def toggle_review_like(user_id, review_id):
    """Toggle like on a review. Returns { success, liked, like_count }."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM reviews WHERE id = ?', (review_id,))
        if not cursor.fetchone():
            conn.close()
            return {'success': False, 'error': 'Review not found'}
        cursor.execute('SELECT 1 FROM review_likes WHERE user_id = ? AND review_id = ?', (user_id, review_id))
        exists = cursor.fetchone()
        if exists:
            cursor.execute('DELETE FROM review_likes WHERE user_id = ? AND review_id = ?', (user_id, review_id))
            liked = False
        else:
            cursor.execute('INSERT INTO review_likes (user_id, review_id) VALUES (?, ?)', (user_id, review_id))
            liked = True
        count = cursor.execute('SELECT COUNT(*) FROM review_likes WHERE review_id = ?', (review_id,)).fetchone()[0]
        conn.commit()
        conn.close()
        return {'success': True, 'liked': liked, 'like_count': count}
    except Exception as e:
        return {'success': False, 'error': str(e)}

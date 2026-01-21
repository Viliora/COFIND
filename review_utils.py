"""
Review Management Utilities
CRUD operations for coffee shop reviews
"""

import sqlite3
from datetime import datetime
from auth_utils import get_db_connection

def create_review(user_id, place_id, rating, text='', photos=None):
    """Create a new review"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Validate rating
        if not 1 <= rating <= 5:
            return {'success': False, 'error': 'Rating must be between 1 and 5'}
        
        # Check if user already reviewed this shop
        existing = cursor.execute(
            'SELECT id FROM reviews WHERE user_id = ? AND place_id = ?',
            (user_id, place_id)
        ).fetchone()
        
        if existing:
            return {'success': False, 'error': 'You already have a review for this shop'}
        
        # Create review
        cursor.execute('''
            INSERT INTO reviews (user_id, place_id, rating, text, photos, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, place_id, rating, text or '', photos or '', datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
        
        conn.commit()
        review_id = cursor.lastrowid
        
        # Return review object
        review = cursor.execute(
            'SELECT * FROM reviews WHERE id = ?',
            (review_id,)
        ).fetchone()
        
        conn.close()
        
        return {
            'success': True,
            'review': {
                'id': review[0],
                'user_id': review[1],
                'place_id': review[2],
                'rating': review[3],
                'text': review[4],
                'photos': review[5],
                'created_at': review[6],
                'updated_at': review[7]
            }
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_review(review_id):
    """Get a single review"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        review = cursor.execute(
            'SELECT * FROM reviews WHERE id = ?',
            (review_id,)
        ).fetchone()
        
        conn.close()
        
        if not review:
            return {'success': False, 'error': 'Review not found'}
        
        return {
            'success': True,
            'review': {
                'id': review[0],
                'user_id': review[1],
                'place_id': review[2],
                'rating': review[3],
                'text': review[4],
                'photos': review[5],
                'created_at': review[6],
                'updated_at': review[7]
            }
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_reviews_for_shop(place_id, limit=50):
    """Get all reviews for a coffee shop"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        reviews = cursor.execute('''
            SELECT r.*, u.username, u.full_name
            FROM reviews r
            LEFT JOIN users u ON r.user_id = u.id
            WHERE r.place_id = ?
            ORDER BY r.created_at DESC
            LIMIT ?
        ''', (place_id, limit)).fetchall()
        
        conn.close()
        
        review_list = []
        for review in reviews:
            review_list.append({
                'id': review[0],
                'user_id': review[1],
                'place_id': review[2],
                'rating': review[3],
                'text': review[4],
                'photos': review[5],
                'created_at': review[6],
                'updated_at': review[7],
                'username': review[8],
                'full_name': review[9]
            })
        
        return {'success': True, 'reviews': review_list}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_user_reviews(user_id, limit=50):
    """Get all reviews by a user"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        reviews = cursor.execute('''
            SELECT * FROM reviews
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (user_id, limit)).fetchall()
        
        conn.close()
        
        review_list = []
        for review in reviews:
            review_list.append({
                'id': review[0],
                'user_id': review[1],
                'place_id': review[2],
                'rating': review[3],
                'text': review[4],
                'photos': review[5],
                'created_at': review[6],
                'updated_at': review[7]
            })
        
        return {'success': True, 'reviews': review_list}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def update_review(review_id, user_id, rating=None, text=None, photos=None):
    """Update a review"""
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
        
        # Update review
        new_rating = rating if rating is not None else review[3]
        new_text = text if text is not None else review[4]
        new_photos = photos if photos is not None else review[5]
        
        if rating is not None and not 1 <= rating <= 5:
            return {'success': False, 'error': 'Rating must be between 1 and 5'}
        
        cursor.execute('''
            UPDATE reviews
            SET rating = ?, text = ?, photos = ?, updated_at = ?
            WHERE id = ?
        ''', (new_rating, new_text, new_photos, datetime.utcnow().isoformat(), review_id))
        
        conn.commit()
        conn.close()
        
        # Return updated review
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

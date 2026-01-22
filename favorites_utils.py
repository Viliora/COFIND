"""
Favorites Management Utilities
CRUD operations for favorite coffee shops
"""

import sqlite3
from datetime import datetime
from auth_utils import get_db_connection

def add_favorite(user_id, place_id):
    """Add a coffee shop to favorites"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if already favorited
        existing = cursor.execute(
            'SELECT id FROM favorites WHERE user_id = ? AND place_id = ?',
            (user_id, place_id)
        ).fetchone()
        
        if existing:
            return {'success': False, 'error': 'Already in favorites'}
        
        # Get shop_id from place_id
        shop = cursor.execute(
            'SELECT id FROM coffee_shops WHERE place_id = ?',
            (place_id,)
        ).fetchone()
        
        if not shop:
            return {'success': False, 'error': 'Coffee shop not found'}
        
        shop_id = shop[0]
        
        # Add favorite
        cursor.execute('''
            INSERT INTO favorites (user_id, shop_id, place_id, added_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, shop_id, place_id, datetime.utcnow().isoformat()))
        
        conn.commit()
        favorite_id = cursor.lastrowid
        conn.close()
        
        return {
            'success': True,
            'favorite_id': favorite_id,
            'message': 'Added to favorites'
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def remove_favorite(user_id, place_id):
    """Remove a coffee shop from favorites"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if exists
        favorite = cursor.execute(
            'SELECT id FROM favorites WHERE user_id = ? AND place_id = ?',
            (user_id, place_id)
        ).fetchone()
        
        if not favorite:
            return {'success': False, 'error': 'Not in favorites'}
        
        # Remove favorite
        cursor.execute(
            'DELETE FROM favorites WHERE user_id = ? AND place_id = ?',
            (user_id, place_id)
        )
        
        conn.commit()
        conn.close()
        
        return {'success': True, 'message': 'Removed from favorites'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_user_favorites(user_id, limit=100):
    """Get all favorites for a user"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get favorites with shop data
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
        conn = get_db_connection()
        cursor = conn.cursor()
        
        favorite = cursor.execute(
            'SELECT id FROM favorites WHERE user_id = ? AND place_id = ?',
            (user_id, place_id)
        ).fetchone()
        
        conn.close()
        
        return {
            'success': True,
            'is_favorite': favorite is not None
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_favorite_count(place_id):
    """Get number of times a shop is favorited"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        count = cursor.execute(
            'SELECT COUNT(*) FROM favorites WHERE place_id = ?',
            (place_id,)
        ).fetchone()[0]
        
        conn.close()
        
        return {
            'success': True,
            'count': count
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

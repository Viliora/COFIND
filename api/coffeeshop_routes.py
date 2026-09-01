"""Endpoint publik data coffee shop: daftar, detail, dan pencarian nama."""

from __future__ import annotations

import time

from flask import Blueprint, jsonify, request

from db_backend import dict_from_row, get_connection
from llm_backend import LLM_BACKEND, llm_is_available
from logging_config import get_logger

bp = Blueprint('coffeeshops', __name__)
LOG_API = get_logger('api')

# Root endpoint
@bp.route('/')
def home():
    return jsonify({"message": "Welcome to COFIND API"})

# Test endpoint untuk debug
@bp.route('/api/test', methods=['GET'])
def test_api():
    return jsonify({
        "status": "ok",
        "message": "Flask server is running",
        "timestamp": time.time(),
        "hf_client_ready": llm_is_available(),
        "llm_backend": LLM_BACKEND,
    })

@bp.route('/api/coffeeshops', methods=['GET'])
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
        LOG_API.error(f"Failed to fetch coffeeshops: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/api/coffeeshops/<int:shop_id>', methods=['GET'])
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
        LOG_API.exception("get_coffeeshop gagal")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/api/coffeeshops/place/<place_id>', methods=['GET'])
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
        LOG_API.exception("get_coffeeshop_by_place_id gagal")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/api/coffeeshops/search', methods=['GET'])
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
        LOG_API.exception("search_coffeeshops gagal")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


"""Endpoint favorit coffee shop milik user."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from favorites_utils import (
    add_favorite,
    get_favorite_count,
    get_user_favorites,
    is_favorite,
    remove_favorite,
)
from logging_config import get_logger

bp = Blueprint('favorites', __name__)
LOG_API = get_logger('api')

@bp.route('/api/favorites', methods=['POST'])
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
        LOG_API.exception("api_add_favorite gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/favorites/<place_id>', methods=['DELETE'])
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
        LOG_API.exception("api_remove_favorite gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/users/<int:user_id>/favorites', methods=['GET'])
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
        LOG_API.exception("api_get_user_favorites gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/coffeeshops/<place_id>/favorite-status', methods=['GET'])
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
        LOG_API.exception("api_check_favorite gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/coffeeshops/<place_id>/favorite-count', methods=['GET'])
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
        LOG_API.exception("api_get_favorite_count gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500


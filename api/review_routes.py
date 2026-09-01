"""Endpoint review: CRUD, like, laporan, dan profil publik penulis review."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from auth_guards import extract_bearer_token
from auth_utils import get_user_by_id, verify_token
from logging_config import get_logger
from review_utils import (
    create_review,
    create_review_report,
    delete_review,
    get_average_rating,
    get_latest_reviews,
    get_review,
    get_reviews_for_shop,
    get_user_review_stats,
    get_user_reviews,
    toggle_review_like,
    update_review,
)

bp = Blueprint('reviews', __name__)
LOG_API = get_logger('api')

@bp.route('/api/reviews/latest', methods=['GET'])
@bp.route('/api/reviews', methods=['GET'])
def api_latest_reviews():
    """Ulasan terbaru untuk tampilan publik (About / beranda / koleksi)."""
    result = get_latest_reviews(request.args.get('limit', 10))
    if not result.get('success'):
        return jsonify({'status': 'error', 'message': result.get('error', 'Gagal memuat ulasan')}), 500
    return jsonify({'status': 'success', 'items': result.get('items') or []}), 200

@bp.route('/api/reviews', methods=['POST'])
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
        LOG_API.exception("api_create_review gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/reviews/<int:review_id>', methods=['GET'])
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
        LOG_API.exception("api_get_review gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/reviews/<int:review_id>', methods=['PUT'])
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
        LOG_API.exception("api_update_review gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/reviews/<int:review_id>', methods=['DELETE'])
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
        LOG_API.exception("api_delete_review gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/reviews/<int:review_id>/like', methods=['POST'])
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
        LOG_API.exception("api_toggle_review_like gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/reviews/<int:review_id>/report', methods=['POST'])
def api_report_review(review_id):
    """Laporkan review. Body opsional: { report_reason, report_text }. Wajib login."""
    token = extract_bearer_token()
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
        LOG_API.exception("api_report_review gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/coffeeshops/<place_id>/reviews', methods=['GET'])
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
        LOG_API.exception("api_get_shop_reviews gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/users/<int:user_id>/profile', methods=['GET'])
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
        LOG_API.exception("api_get_user_public_profile gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/users/<int:user_id>/reviews', methods=['GET'])
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
        LOG_API.exception("api_get_user_reviews gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500


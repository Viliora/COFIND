"""Endpoint review: CRUD, like, laporan, dan profil publik penulis review."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from auth_guards import (
    forbid_user_id_spoofing,
    get_optional_authenticated_user,
    require_authenticated_user,
)
from auth_utils import get_user_by_id
from logging_config import get_logger
from review_utils import (
    create_review,
    create_review_report,
    delete_review,
    get_average_rating,
    get_review_star_counts,
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
    """Create a new review (rating tempat + text)."""
    try:
        auth_user, auth_error = require_authenticated_user()
        if auth_error:
            return auth_error

        data = request.get_json(silent=True) or {}
        spoof_error = forbid_user_id_spoofing(auth_user, data.get('user_id'))
        if spoof_error:
            return spoof_error

        place_id = data.get('place_id')
        rating = data.get('rating')
        text = data.get('text', '')

        if not place_id or rating is None:
            return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

        result = create_review(auth_user['id'], place_id, rating, text)
        
        if result['success']:
            try:
                from shop_search_store import refresh_shop_search_document
                refresh_shop_search_document(place_id)
            except Exception:
                pass
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
        auth_user, auth_error = require_authenticated_user()
        if auth_error:
            return auth_error

        data = request.get_json(silent=True) or {}
        spoof_error = forbid_user_id_spoofing(auth_user, data.get('user_id'))
        if spoof_error:
            return spoof_error
        
        result = update_review(
            review_id,
            auth_user['id'],
            rating=data.get('rating'),
            text=data.get('text'),
        )
        
        if result['success']:
            review = result.get('review') or {}
            try:
                from shop_search_store import refresh_shop_search_document
                refresh_shop_search_document(review.get('place_id'))
            except Exception:
                pass
            return jsonify({
                'status': 'success',
                'review': review,
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
        auth_user, auth_error = require_authenticated_user()
        if auth_error:
            return auth_error

        data = request.get_json(silent=True) or {}
        spoof_error = forbid_user_id_spoofing(auth_user, data.get('user_id'))
        if spoof_error:
            return spoof_error
        
        result = delete_review(review_id, auth_user['id'])
        
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
    """Toggle like on a review."""
    try:
        auth_user, auth_error = require_authenticated_user()
        if auth_error:
            return auth_error

        data = request.get_json(silent=True) or {}
        spoof_error = forbid_user_id_spoofing(auth_user, data.get('user_id'))
        if spoof_error:
            return spoof_error

        result = toggle_review_like(auth_user['id'], review_id)
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
    auth_user, auth_error = require_authenticated_user()
    if auth_error:
        return auth_error

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

@bp.route('/api/coffeeshops/<place_id>/reviews/rating-summary', methods=['GET'])
def api_get_shop_review_rating_summary(place_id):
    """Distribusi bintang 1–5 dari kolom reviews.rating."""
    try:
        result = get_review_star_counts(place_id)
        if not result.get('success'):
            return jsonify({'status': 'error', 'message': result.get('error', 'Gagal memuat ringkasan rating')}), 400
        return jsonify({
            'status': 'success',
            'star_counts': result.get('star_counts') or {},
            'review_star_total': result.get('review_star_total') or 0,
            'average_rating': result.get('average_rating'),
        }), 200
    except Exception as e:
        LOG_API.exception("api_get_shop_review_rating_summary gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/api/coffeeshops/<place_id>/reviews', methods=['GET'])
def api_get_shop_reviews(place_id):
    """Get all reviews for a coffee shop. user_has_liked dari sesi login (Bearer), bukan query user_id."""
    try:
        limit = request.args.get('limit', 50, type=int)
        auth_user = get_optional_authenticated_user()
        if auth_user:
            spoof_error = forbid_user_id_spoofing(auth_user, request.args.get('user_id'))
            if spoof_error:
                return spoof_error
        current_user_id = auth_user['id'] if auth_user else None
        result = get_reviews_for_shop(place_id, limit, current_user_id=current_user_id)
        
        if result['success']:
            # Also get average rating
            rating_result = get_average_rating(place_id)
            resp = jsonify({
                'status': 'success',
                'reviews': result['reviews'],
                'average_rating': rating_result.get('average_rating', 0),
                'review_count': rating_result.get('review_count', 0)
            })
            resp.headers['Cache-Control'] = 'no-store'
            return resp, 200
        else:
            LOG_API.warning(
                "api_get_shop_reviews gagal untuk place_id=%s: %s",
                place_id,
                result.get('error'),
            )
            return jsonify({
                'status': 'error',
                'message': result.get('error') or 'Gagal memuat ulasan',
                'reviews': [],
                'average_rating': 0,
                'review_count': 0,
            }), 500
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


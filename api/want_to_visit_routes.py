"""Endpoint daftar "ingin dikunjungi" milik user."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from auth_guards import forbid_user_id_spoofing, require_authenticated_user
from logging_config import get_logger
from want_to_visit_utils import (
    add_want_to_visit,
    get_user_want_to_visit,
    is_want_to_visit,
    remove_want_to_visit,
)

bp = Blueprint('want_to_visit', __name__)
LOG_API = get_logger('api')

@bp.route('/api/want-to-visit', methods=['POST'])
def api_add_want_to_visit():
    """Add a coffee shop to want_to_visit"""
    try:
        auth_user, auth_error = require_authenticated_user()
        if auth_error:
            return auth_error

        data = request.get_json(silent=True) or {}
        spoof_error = forbid_user_id_spoofing(auth_user, data.get('user_id'))
        if spoof_error:
            return spoof_error

        place_id = data.get('place_id')
        if not place_id:
            return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

        result = add_want_to_visit(auth_user['id'], place_id)

        if result['success']:
            return jsonify({
                'status': 'success',
                'want_to_visit_id': result['want_to_visit_id'],
                'message': result['message']
            }), 201
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 400
    except Exception as e:
        LOG_API.exception("api_add_want_to_visit gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/want-to-visit/<place_id>', methods=['DELETE'])
def api_remove_want_to_visit(place_id):
    """Remove a coffee shop from want_to_visit"""
    try:
        auth_user, auth_error = require_authenticated_user()
        if auth_error:
            return auth_error

        data = request.get_json(silent=True) or {}
        spoof_error = forbid_user_id_spoofing(auth_user, data.get('user_id'))
        if spoof_error:
            return spoof_error

        result = remove_want_to_visit(auth_user['id'], place_id)

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
        LOG_API.exception("api_remove_want_to_visit gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/users/<int:user_id>/want-to-visit', methods=['GET'])
def api_get_user_want_to_visit(user_id):
    """Get all want_to_visit for a user"""
    try:
        auth_user, auth_error = require_authenticated_user()
        if auth_error:
            return auth_error
        if int(auth_user['id']) != int(user_id):
            return jsonify({
                'status': 'error',
                'message': 'Akses ditolak.',
            }), 403

        limit = request.args.get('limit', 100, type=int)
        result = get_user_want_to_visit(user_id, limit)

        if result['success']:
            return jsonify({
                'status': 'success',
                'want_to_visit': result['want_to_visit']
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 400
    except Exception as e:
        LOG_API.exception("api_get_user_want_to_visit gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/coffeeshops/<place_id>/want-to-visit-status', methods=['GET'])
def api_check_want_to_visit(place_id):
    """Check if a coffee shop is in user's want_to_visit"""
    try:
        auth_user, auth_error = require_authenticated_user()
        if auth_error:
            return auth_error

        spoof_error = forbid_user_id_spoofing(auth_user, request.args.get('user_id'))
        if spoof_error:
            return spoof_error

        result = is_want_to_visit(auth_user['id'], place_id)

        if result['success']:
            return jsonify({
                'status': 'success',
                'is_want_to_visit': result['is_want_to_visit']
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 400
    except Exception as e:
        LOG_API.exception("api_check_want_to_visit gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

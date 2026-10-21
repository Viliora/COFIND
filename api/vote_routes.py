"""Endpoint penilaian toko (vote) dan poin pro/kontra."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from auth_guards import forbid_user_id_spoofing, get_optional_authenticated_user, require_authenticated_user
from db_backend import get_connection
from logging_config import get_logger
from pros_cons_utils import get_pros_cons, maybe_refresh_pros_cons, toggle_pros_cons_vote
from vote_utils import get_user_vote, get_vote_summary, upsert_vote

bp = Blueprint('votes', __name__)
LOG_API = get_logger('api')

@bp.route('/api/coffeeshops/<place_id>/votes/summary', methods=['GET'])
def api_get_vote_summary(place_id):
    """Aggregated vote summary (presence, rating, best_for, slider averages) for a coffee shop."""
    try:
        result = get_vote_summary(place_id)
        if result['success']:
            return jsonify({'status': 'success', **result}), 200
        return jsonify({'status': 'error', 'message': result['error']}), 400
    except Exception as e:
        LOG_API.exception("api_get_vote_summary gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/coffeeshops/<place_id>/votes/me', methods=['GET'])
def api_get_my_vote(place_id):
    """Current user's vote for a coffee shop."""
    try:
        auth_user, auth_error = require_authenticated_user()
        if auth_error:
            return auth_error

        spoof_error = forbid_user_id_spoofing(auth_user, request.args.get('user_id'))
        if spoof_error:
            return spoof_error

        vote = get_user_vote(auth_user['id'], place_id)
        return jsonify({'status': 'success', 'vote': vote}), 200
    except Exception as e:
        LOG_API.exception("api_get_my_vote gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/api/coffeeshops/<place_id>/users/<int:user_id>/vote', methods=['GET'])
def api_get_user_vote_for_shop(place_id, user_id):
    """Vote publik (read-only) satu user untuk satu toko — untuk tampilan ulasan, bukan aksi."""
    try:
        vote = get_user_vote(user_id, place_id)
        return jsonify({'status': 'success', 'vote': vote}), 200
    except Exception as e:
        LOG_API.exception("api_get_user_vote_for_shop gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/coffeeshops/<place_id>/votes', methods=['POST'])
def api_upsert_vote(place_id):
    """Create or update the current user's vote for a coffee shop."""
    try:
        auth_user, auth_error = require_authenticated_user()
        if auth_error:
            return auth_error

        data = request.get_json(silent=True) or {}
        spoof_error = forbid_user_id_spoofing(auth_user, data.get('user_id'))
        if spoof_error:
            return spoof_error

        result = upsert_vote(
            auth_user['id'],
            place_id,
            presence=data.get('presence'),
            rating=data.get('rating'),
            best_for=data.get('best_for'),
            pelayanan=data.get('pelayanan'),
            kebersihan=data.get('kebersihan'),
            kenyamanan=data.get('kenyamanan'),
            harga=data.get('harga'),
        )
        if result['success']:
            return jsonify({'status': 'success'}), 200
        return jsonify({'status': 'error', 'message': result['error']}), 400
    except Exception as e:
        LOG_API.exception("api_upsert_vote gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/coffeeshops/<place_id>/pros-cons', methods=['GET'])
def api_get_pros_cons(place_id):
    """
    Ambil poin pros & cons (hasil ekstraksi AI) untuk satu coffee shop.
    Batch job ekstraksi AI hanya dijalankan (lazy trigger) jika sudah waktunya
    (>=7 hari) atau sudah ada >=5 review baru sejak pembaruan terakhir.
    Selain itu, hanya membaca hasil yang sudah tersimpan di database.
    """
    try:
        auth_user = get_optional_authenticated_user()
        spoof_error = forbid_user_id_spoofing(auth_user, request.args.get('user_id')) if auth_user else None
        if spoof_error:
            return spoof_error
        user_id = auth_user['id'] if auth_user else None

        conn = get_connection()
        cursor = conn.cursor()
        shop_row = cursor.execute('SELECT name FROM coffee_shops WHERE place_id = ?', (place_id,)).fetchone()
        conn.close()
        shop_name = shop_row[0] if shop_row else place_id

        maybe_refresh_pros_cons(place_id, shop_name)

        result = get_pros_cons(place_id, user_id=user_id)
        if result['success']:
            return jsonify({
                'status': 'success',
                'pros': result['pros'],
                'cons': result['cons'],
                'last_generated_at': result.get('last_generated_at'),
            }), 200
        return jsonify({'status': 'error', 'message': result['error']}), 400
    except Exception as e:
        LOG_API.exception("api_get_pros_cons gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/coffeeshops/<place_id>/pros-cons/<int:point_id>/vote', methods=['POST'])
def api_vote_pros_cons(place_id, point_id):
    """Upvote/downvote satu poin pro/con. Body: { vote_type: 'up'|'down' }."""
    try:
        auth_user, auth_error = require_authenticated_user()
        if auth_error:
            return auth_error

        data = request.get_json(silent=True) or {}
        spoof_error = forbid_user_id_spoofing(auth_user, data.get('user_id'))
        if spoof_error:
            return spoof_error

        vote_type = data.get('vote_type')
        if vote_type not in ('up', 'down'):
            return jsonify({'status': 'error', 'message': "vote_type harus 'up' atau 'down'"}), 400

        result = toggle_pros_cons_vote(auth_user['id'], point_id, vote_type)
        if result['success']:
            return jsonify({
                'status': 'success',
                'upvotes': result['upvotes'],
                'downvotes': result['downvotes'],
                'user_vote': result['user_vote'],
            }), 200
        return jsonify({'status': 'error', 'message': result['error']}), 400
    except Exception as e:
        LOG_API.exception("api_vote_pros_cons gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

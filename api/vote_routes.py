"""Endpoint penilaian toko (vote) dan poin pro/kontra."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

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
        user_id = request.args.get('user_id', type=int)
        if not user_id:
            return jsonify({'status': 'error', 'message': 'user_id required'}), 400
        vote = get_user_vote(user_id, place_id)
        return jsonify({'status': 'success', 'vote': vote}), 200
    except Exception as e:
        LOG_API.exception("api_get_my_vote gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/coffeeshops/<place_id>/votes', methods=['POST'])
def api_upsert_vote(place_id):
    """Create or update the current user's vote for a coffee shop."""
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({'status': 'error', 'message': 'user_id required'}), 400

        result = upsert_vote(
            user_id,
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
        user_id = request.args.get('user_id', type=int)

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
    """Upvote/downvote satu poin pro/con. Body: { user_id, vote_type: 'up'|'down' }."""
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get('user_id')
        vote_type = data.get('vote_type')
        if not user_id:
            return jsonify({'status': 'error', 'message': 'user_id required'}), 400
        if vote_type not in ('up', 'down'):
            return jsonify({'status': 'error', 'message': "vote_type harus 'up' atau 'down'"}), 400

        result = toggle_pros_cons_vote(user_id, point_id, vote_type)
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


"""Endpoint rekomendasi pill / free-text dan feedback evaluasi."""

from __future__ import annotations

import json

from flask import Blueprint, Response, jsonify, request, stream_with_context

from auth_guards import require_authenticated_user
from logging_config import get_logger
from recommendation.request_prefs import read_recommendation_preferences
from recommendation_feedback_utils import (
    get_feedback_evaluation_summary,
    get_user_feedback_map,
    upsert_recommendation_feedback,
)
from recommendation.pipeline import recommendation_pipeline_events

bp = Blueprint('recommendation', __name__)
LOG_API = get_logger('api')
LOG_RECOMMEND = get_logger('recommend')

def _sse_pack(event, payload):
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@bp.route('/api/recommend-by-preferences', methods=['POST'])
def api_recommend_by_preferences():
    """Rekomendasi pill/free-text (respons JSON sekali kirim). Progress diabaikan di sini."""
    prefs, query_text = read_recommendation_preferences()
    auth_user, auth_error = require_authenticated_user()
    if auth_error is not None:
        return auth_error

    body, status = {'status': 'error', 'message': 'Pipeline tidak menghasilkan respons.'}, 500
    for kind, payload in recommendation_pipeline_events(prefs, auth_user, query_text=query_text):
        if kind == 'result':
            body, status = payload
    return jsonify(body), status


@bp.route('/api/recommend-by-preferences/stream', methods=['POST'])
def api_recommend_by_preferences_stream():
    prefs, query_text = read_recommendation_preferences()
    auth_user, auth_error = require_authenticated_user()
    if auth_error is not None:
        return auth_error

    LOG_RECOMMEND.info(
        f"Stream rekomendasi: user_id={auth_user.get('id')} prefs={prefs!r} "
        f"query_text={query_text!r}"
    )

    def generate():
        yield ': cofind-stream\n\n'
        delivered_result = False
        try:
            for kind, payload in recommendation_pipeline_events(
                prefs, auth_user, query_text=query_text,
            ):
                if kind == 'progress':
                    yield _sse_pack('progress', payload)
                elif kind == 'result':
                    body, status = payload
                    delivered_result = True
                    yield _sse_pack('result', {'status_code': status, 'body': body})
        except Exception as stream_err:
            LOG_RECOMMEND.exception("Stream rekomendasi gagal")
            if not delivered_result:
                delivered_result = True
                yield _sse_pack('result', {
                    'status_code': 500,
                    'body': {
                        'status': 'error',
                        'message': str(stream_err),
                        'recommendations': [],
                    },
                })
        if not delivered_result:
            yield _sse_pack('result', {
                'status_code': 500,
                'body': {
                    'status': 'error',
                    'message': 'Pipeline tidak menghasilkan respons.',
                    'recommendations': [],
                },
            })

    response = Response(stream_with_context(generate()), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache, no-transform'
    response.headers['Connection'] = 'keep-alive'
    response.headers['X-Accel-Buffering'] = 'no'
    return response


@bp.route('/api/recommend-by-preferences/feedback', methods=['POST'])
def api_recommend_feedback_upsert():
    try:
        auth_user, auth_error = require_authenticated_user()
        if auth_error is not None:
            return auth_error

        data = request.get_json(silent=True) or {}
        result = upsert_recommendation_feedback(
            auth_user.get('id'),
            data.get('place_id'),
            data.get('preferences') or [],
            data.get('vote'),
            reason=data.get('reason'),
            rank_position=data.get('rank_position'),
            score=data.get('score'),
        )
        if not result.get('success'):
            return jsonify({
                'status': 'error',
                'message': result.get('error') or 'Gagal menyimpan feedback',
            }), 400
        return jsonify({'status': 'success', 'feedback': result.get('feedback')}), 200
    except Exception as e:
        LOG_API.exception("api_recommend_feedback_upsert gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/api/recommend-by-preferences/feedback', methods=['GET'])
def api_recommend_feedback_get():
    try:
        auth_user, auth_error = require_authenticated_user()
        if auth_error is not None:
            return auth_error

        prefs_raw = request.args.get('preferences') or ''
        if ',' in prefs_raw:
            preferences = [p.strip() for p in prefs_raw.split(',') if p.strip()]
        elif prefs_raw.strip():
            preferences = [prefs_raw.strip()]
        else:
            preferences = []

        place_ids_raw = request.args.get('place_ids') or ''
        place_ids = [p.strip() for p in place_ids_raw.split(',') if p.strip()] or None

        feedback_map = get_user_feedback_map(auth_user.get('id'), preferences, place_ids=place_ids)
        return jsonify({
            'status': 'success',
            'preferences': preferences,
            'feedback_by_place_id': feedback_map,
        }), 200
    except Exception as e:
        LOG_API.exception("api_recommend_feedback_get gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/api/recommend-by-preferences/feedback/summary', methods=['GET'])
def api_recommend_feedback_summary():
    try:
        _auth_user, auth_error = require_authenticated_user()
        if auth_error is not None:
            return auth_error

        prefs_raw = request.args.get('preferences') or ''
        preferences = [p.strip() for p in prefs_raw.split(',') if p.strip()] or None
        try:
            limit = int(request.args.get('limit') or 200)
        except (TypeError, ValueError):
            limit = 200

        result = get_feedback_evaluation_summary(preferences=preferences, limit=limit)
        if not result.get('success'):
            return jsonify({
                'status': 'error',
                'message': result.get('error') or 'Gagal mengambil ringkasan',
            }), 400
        return jsonify({
            'status': 'success',
            'counts': result.get('counts') or {},
            'not_helpful_recent': result.get('not_helpful_recent') or [],
        }), 200
    except Exception as e:
        LOG_API.exception("api_recommend_feedback_summary gagal")
        return jsonify({'status': 'error', 'message': str(e)}), 500

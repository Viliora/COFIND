"""Gerbang autentikasi untuk endpoint API.

Setiap fungsi mengembalikan tuple `(user, error_response)`. Pemanggil hanya perlu
memeriksa `error_response`; bila tidak None, kembalikan langsung ke client.
"""

from __future__ import annotations

from flask import jsonify, request

from auth_utils import verify_token


def extract_bearer_token() -> str:
    return request.headers.get('Authorization', '').replace('Bearer ', '').strip()


def require_admin():
    """User dengan flag is_admin. Return (user, None) bila lolos."""
    token = extract_bearer_token()
    if not token:
        return None, (jsonify({'status': 'error', 'message': 'No token provided'}), 401)

    auth_result = verify_token(token)
    if not auth_result.get('valid'):
        return None, (jsonify({'status': 'error', 'message': 'Invalid or expired token'}), 401)

    user = auth_result.get('user') or {}
    if not user.get('is_admin'):
        return None, (jsonify({'status': 'error', 'message': 'Admin access required'}), 403)

    return user, None


def require_authenticated_user():
    """Pengguna login (bukan admin-only): token sesi valid."""
    token = extract_bearer_token()
    if not token:
        return None, (jsonify({
            'status': 'error',
            'message': 'Login diperlukan.',
        }), 401)

    auth_result = verify_token(token)
    if not auth_result.get('valid'):
        return None, (jsonify({
            'status': 'error',
            'message': 'Sesi tidak valid atau kadaluarsa. Silakan login lagi.',
        }), 401)

    user = auth_result.get('user')
    if not user or not user.get('id'):
        return None, (jsonify({
            'status': 'error',
            'message': 'Sesi tidak valid. Silakan login lagi.',
        }), 401)

    return user, None


def get_optional_authenticated_user():
    """Pengguna login jika token valid; None jika tidak ada / tidak valid."""
    token = extract_bearer_token()
    if not token:
        return None

    auth_result = verify_token(token)
    if not auth_result.get('valid'):
        return None

    user = auth_result.get('user')
    if not user or not user.get('id'):
        return None

    return user


def forbid_user_id_spoofing(auth_user, claimed_user_id):
    """Tolak jika body/query user_id tidak cocok dengan sesi (opsional, untuk transisi API)."""
    if claimed_user_id is None or claimed_user_id == '':
        return None
    try:
        claimed = int(claimed_user_id)
    except (TypeError, ValueError):
        return (jsonify({
            'status': 'error',
            'message': 'user_id tidak valid.',
        }), 400)
    if claimed != int(auth_user['id']):
        return (jsonify({
            'status': 'error',
            'message': 'user_id tidak sesuai dengan sesi login.',
        }), 403)
    return None

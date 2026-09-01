"""Endpoint autentikasi: signup, login, verifikasi sesi, dan update profil."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from auth_utils import (
    get_user_by_id,
    login,
    logout,
    signup,
    update_password,
    update_user_profile,
    verify_token,
)
from logging_config import get_logger

bp = Blueprint('auth', __name__)
LOG_API = get_logger('api')

@bp.route('/api/auth/signup', methods=['POST'])
def auth_signup():
    """Register new user"""
    try:
        data = request.get_json()
        result = signup(
            email=data.get('email'),
            username=data.get('username'),
            password=data.get('password'),
            full_name=data.get('full_name', '')
        )
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'user': result['user'],
                'token': result['token'],
                'expires_in': result['expires_in']
            }), 201
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 400
    except Exception as e:
        LOG_API.exception("auth_signup gagal")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/api/auth/login', methods=['POST'])
def auth_login():
    """Login user"""
    try:
        data = request.get_json()
        result = login(
            email=data.get('email'),
            password=data.get('password')
        )
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'user': result['user'],
                'token': result['token'],
                'expires_in': result['expires_in']
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 401
    except Exception as e:
        LOG_API.exception("auth_login gagal")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/api/auth/verify', methods=['POST'])
def auth_verify():
    """Verify session token"""
    try:
        data = request.get_json()
        token = data.get('token') or request.headers.get('Authorization', '').replace('Bearer ', '')
        
        result = verify_token(token)
        
        if result['valid']:
            return jsonify({
                'status': 'success',
                'user': result['user']
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Invalid or expired token'
            }), 401
    except Exception as e:
        LOG_API.exception("auth_verify gagal")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    """Logout user"""
    try:
        data = request.get_json()
        token = data.get('token') or request.headers.get('Authorization', '').replace('Bearer ', '')
        
        result = logout(token)
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'message': 'Logged out successfully'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 500
    except Exception as e:
        LOG_API.exception("auth_logout gagal")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/api/auth/user', methods=['GET'])
def auth_get_user():
    """Get current user info"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            return jsonify({
                'status': 'error',
                'message': 'No token provided'
            }), 401
        
        result = verify_token(token)
        
        if not result['valid']:
            return jsonify({
                'status': 'error',
                'message': 'Invalid or expired token'
            }), 401
        
        return jsonify({
            'status': 'success',
            'user': result['user']
        }), 200
    except Exception as e:
        LOG_API.exception("auth_get_user gagal")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/api/auth/update-profile', methods=['PUT'])
def auth_update_profile():
    """Update user profile"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            return jsonify({
                'status': 'error',
                'message': 'No token provided'
            }), 401
        
        result = verify_token(token)
        
        if not result['valid']:
            return jsonify({
                'status': 'error',
                'message': 'Invalid or expired token'
            }), 401
        
        user_id = result['user']['id']
        data = request.get_json()
        
        update_result = update_user_profile(
            user_id=user_id,
            full_name=data.get('full_name'),
            bio=data.get('bio'),
            avatar_url=data.get('avatar_url'),
            phone=data.get('phone')
        )
        
        if update_result['success']:
            # Get updated user
            updated_user = get_user_by_id(user_id)
            return jsonify({
                'status': 'success',
                'user': updated_user
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': update_result['error']
            }), 500
    except Exception as e:
        LOG_API.exception("auth_update_profile gagal")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/api/auth/update-password', methods=['PUT'])
def auth_update_password():
    """Update user password"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            return jsonify({
                'status': 'error',
                'message': 'No token provided'
            }), 401
        
        result = verify_token(token)
        
        if not result['valid']:
            return jsonify({
                'status': 'error',
                'message': 'Invalid or expired token'
            }), 401
        
        user_id = result['user']['id']
        data = request.get_json()
        
        update_result = update_password(
            user_id=user_id,
            old_password=data.get('old_password'),
            new_password=data.get('new_password')
        )
        
        if update_result['success']:
            return jsonify({
                'status': 'success',
                'message': 'Password updated successfully'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': update_result['error']
            }), 400
    except Exception as e:
        LOG_API.exception("auth_update_password gagal")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


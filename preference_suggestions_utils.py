"""
Preference Suggestions - saran preferensi dari user (hanya untuk user login).
"""

import sqlite3
from datetime import datetime
from auth_utils import get_db_connection

def create_preference_suggestion(user_id, preference_text, reason_text):
    """Simpan saran preferensi dari user."""
    try:
        preference_text = (preference_text or '').strip()
        reason_text = (reason_text or '').strip()
        if not preference_text:
            return {'success': False, 'error': 'Preferensi tidak boleh kosong'}
        if not reason_text:
            return {'success': False, 'error': 'Alasan tidak boleh kosong'}

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO preference_suggestions (user_id, preference_text, reason_text, created_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, preference_text, reason_text, datetime.utcnow().isoformat()))
        conn.commit()
        row_id = cursor.lastrowid
        conn.close()

        return {
            'success': True,
            'id': row_id,
            'message': 'Saran preferensi berhasil disimpan'
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

"""
Utilities untuk feedback rekomendasi pill preference (thumbs up / thumbs down).

Vote:
- helpful     → "Rekomendasi membantu"
- not_helpful → "Tidak relevan / tidak membantu"

Data dipakai untuk evaluasi sistem dan personalisasi ringan:
shop yang user tandai not_helpful untuk set preferensi yang sama
di-downrank / dikecualikan pada request rekomendasi berikutnya.
"""

from __future__ import annotations

import json
from datetime import datetime

from auth_utils import get_db_connection
from db_backend import dict_from_row

VOTE_OPTIONS = ('helpful', 'not_helpful')

_TABLE_READY = False


def preferences_key_from_pills(pills):
    """Kunci stabil: pill diurut abjad, dipisah '+'."""
    cleaned = []
    seen = set()
    for p in pills or []:
        v = str(p or '').strip().lower()
        if not v or v in seen:
            continue
        seen.add(v)
        cleaned.append(v)
    cleaned.sort()
    return '+'.join(cleaned)


def _normalize_pills(pills):
    cleaned = []
    seen = set()
    for p in pills or []:
        v = str(p or '').strip().lower()
        if not v or v in seen:
            continue
        seen.add(v)
        cleaned.append(v)
    return cleaned


def ensure_recommendation_feedback_table():
    """Buat tabel jika belum ada (idempotent)."""
    global _TABLE_READY
    if _TABLE_READY:
        return True
    conn = None
    try:
        from db_backend import use_postgres

        conn = get_db_connection()
        cursor = conn.cursor()
        if use_postgres():
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recommendation_feedback (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    place_id TEXT NOT NULL,
                    preferences_key TEXT NOT NULL,
                    preferences_json TEXT NOT NULL,
                    vote TEXT NOT NULL,
                    reason TEXT,
                    rank_position INTEGER,
                    score REAL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE (user_id, place_id, preferences_key)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_rec_feedback_vote
                ON recommendation_feedback (vote, preferences_key)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_rec_feedback_user
                ON recommendation_feedback (user_id, preferences_key)
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recommendation_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    place_id TEXT NOT NULL,
                    preferences_key TEXT NOT NULL,
                    preferences_json TEXT NOT NULL,
                    vote TEXT NOT NULL,
                    reason TEXT,
                    rank_position INTEGER,
                    score REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (user_id, place_id, preferences_key),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_rec_feedback_vote
                ON recommendation_feedback (vote, preferences_key)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_rec_feedback_user
                ON recommendation_feedback (user_id, preferences_key)
            """)
        conn.commit()
        _TABLE_READY = True
        return True
    except Exception as e:
        print(f"[WARN] ensure_recommendation_feedback_table: {e}")
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        return False
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def upsert_recommendation_feedback(
    user_id,
    place_id,
    preferences,
    vote,
    reason=None,
    rank_position=None,
    score=None,
):
    """Simpan atau perbarui feedback user untuk satu rekomendasi."""
    ensure_recommendation_feedback_table()
    conn = None
    try:
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return {'success': False, 'error': 'Invalid user_id'}

        place_id = str(place_id or '').strip()
        if not place_id:
            return {'success': False, 'error': 'place_id required'}

        pills = _normalize_pills(preferences)
        if not pills:
            return {'success': False, 'error': 'preferences required'}

        vote = str(vote or '').strip().lower()
        if vote not in VOTE_OPTIONS:
            return {'success': False, 'error': 'vote must be helpful or not_helpful'}

        prefs_key = preferences_key_from_pills(pills)
        prefs_json = json.dumps(pills, ensure_ascii=False)
        reason_text = str(reason or '').strip()[:500] or None

        rank_val = None
        if rank_position is not None:
            try:
                rank_val = int(rank_position)
            except (TypeError, ValueError):
                rank_val = None

        score_val = None
        if score is not None:
            try:
                score_val = float(score)
            except (TypeError, ValueError):
                score_val = None

        now = datetime.utcnow().isoformat()
        conn = get_db_connection()
        cursor = conn.cursor()

        existing = cursor.execute(
            '''
            SELECT id FROM recommendation_feedback
            WHERE user_id = ? AND place_id = ? AND preferences_key = ?
            ''',
            (user_id, place_id, prefs_key),
        ).fetchone()

        if existing:
            existing_id = existing[0] if not isinstance(existing, dict) else existing.get('id')
            cursor.execute(
                '''
                UPDATE recommendation_feedback
                SET vote = ?, reason = ?, rank_position = ?, score = ?,
                    preferences_json = ?, updated_at = ?
                WHERE id = ?
                ''',
                (vote, reason_text, rank_val, score_val, prefs_json, now, existing_id),
            )
            feedback_id = existing_id
        else:
            cursor.execute(
                '''
                INSERT INTO recommendation_feedback (
                    user_id, place_id, preferences_key, preferences_json,
                    vote, reason, rank_position, score, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    user_id, place_id, prefs_key, prefs_json,
                    vote, reason_text, rank_val, score_val, now, now,
                ),
            )
            feedback_id = getattr(cursor, 'lastrowid', None)

        conn.commit()
        return {
            'success': True,
            'feedback': {
                'id': feedback_id,
                'user_id': user_id,
                'place_id': place_id,
                'preferences': pills,
                'preferences_key': prefs_key,
                'vote': vote,
                'reason': reason_text,
                'rank_position': rank_val,
                'score': score_val,
            },
        }
    except Exception as e:
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        return {'success': False, 'error': str(e)}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def get_user_feedback_map(user_id, preferences, place_ids=None):
    """
    Ambil map place_id -> feedback untuk user + set preferensi.
    Jika place_ids diberikan, hanya filter ke daftar itu.
    """
    ensure_recommendation_feedback_table()
    conn = None
    try:
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return {}

        prefs_key = preferences_key_from_pills(preferences)
        if not prefs_key:
            return {}

        conn = get_db_connection()
        cursor = conn.cursor()
        rows = cursor.execute(
            '''
            SELECT id, user_id, place_id, preferences_key, preferences_json,
                   vote, reason, rank_position, score, created_at, updated_at
            FROM recommendation_feedback
            WHERE user_id = ? AND preferences_key = ?
            ''',
            (user_id, prefs_key),
        ).fetchall()

        wanted = None
        if place_ids is not None:
            wanted = {str(p).strip() for p in place_ids if str(p or '').strip()}

        out = {}
        for row in rows or []:
            rd = dict_from_row(cursor, row) or {}
            pid = str(rd.get('place_id') or '').strip()
            if not pid:
                continue
            if wanted is not None and pid not in wanted:
                continue
            try:
                prefs = json.loads(rd.get('preferences_json') or '[]')
            except Exception:
                prefs = []
            out[pid] = {
                'id': rd.get('id'),
                'place_id': pid,
                'preferences': prefs if isinstance(prefs, list) else [],
                'preferences_key': rd.get('preferences_key'),
                'vote': rd.get('vote'),
                'reason': rd.get('reason'),
                'rank_position': rd.get('rank_position'),
                'score': rd.get('score'),
                'created_at': rd.get('created_at'),
                'updated_at': rd.get('updated_at'),
            }
        return out
    except Exception as e:
        print(f"[WARN] get_user_feedback_map: {e}")
        return {}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def get_not_helpful_place_ids(user_id, preferences):
    """Place ID yang user tandai tidak relevan untuk set preferensi ini."""
    feedback_map = get_user_feedback_map(user_id, preferences)
    return {
        pid for pid, item in feedback_map.items()
        if item.get('vote') == 'not_helpful'
    }


def get_feedback_evaluation_summary(preferences=None, limit=200):
    """
    Ringkasan feedback untuk evaluasi sistem.
    Return counts + daftar recent not_helpful (berguna untuk analisis kualitas).
    """
    ensure_recommendation_feedback_table()
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        prefs_key = preferences_key_from_pills(preferences) if preferences else None

        if prefs_key:
            rows = cursor.execute(
                '''
                SELECT vote, COUNT(*) AS cnt
                FROM recommendation_feedback
                WHERE preferences_key = ?
                GROUP BY vote
                ''',
                (prefs_key,),
            ).fetchall()
        else:
            rows = cursor.execute(
                '''
                SELECT vote, COUNT(*) AS cnt
                FROM recommendation_feedback
                GROUP BY vote
                '''
            ).fetchall()

        counts = {'helpful': 0, 'not_helpful': 0, 'total': 0}
        for row in rows or []:
            rd = dict_from_row(cursor, row) or {}
            vote = rd.get('vote')
            cnt = int(rd.get('cnt') or 0)
            if vote in counts:
                counts[vote] = cnt
            counts['total'] += cnt

        if prefs_key:
            recent = cursor.execute(
                '''
                SELECT id, user_id, place_id, preferences_key, preferences_json,
                       vote, reason, rank_position, score, created_at, updated_at
                FROM recommendation_feedback
                WHERE preferences_key = ? AND vote = 'not_helpful'
                ORDER BY updated_at DESC
                LIMIT ?
                ''',
                (prefs_key, int(limit)),
            ).fetchall()
        else:
            recent = cursor.execute(
                '''
                SELECT id, user_id, place_id, preferences_key, preferences_json,
                       vote, reason, rank_position, score, created_at, updated_at
                FROM recommendation_feedback
                WHERE vote = 'not_helpful'
                ORDER BY updated_at DESC
                LIMIT ?
                ''',
                (int(limit),),
            ).fetchall()

        not_helpful_items = []
        for row in recent or []:
            rd = dict_from_row(cursor, row) or {}
            try:
                prefs = json.loads(rd.get('preferences_json') or '[]')
            except Exception:
                prefs = []
            not_helpful_items.append({
                'id': rd.get('id'),
                'user_id': rd.get('user_id'),
                'place_id': rd.get('place_id'),
                'preferences': prefs if isinstance(prefs, list) else [],
                'preferences_key': rd.get('preferences_key'),
                'reason': rd.get('reason'),
                'rank_position': rd.get('rank_position'),
                'score': rd.get('score'),
                'updated_at': rd.get('updated_at'),
            })

        return {
            'success': True,
            'counts': counts,
            'not_helpful_recent': not_helpful_items,
        }
    except Exception as e:
        return {'success': False, 'error': str(e), 'counts': {}, 'not_helpful_recent': []}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

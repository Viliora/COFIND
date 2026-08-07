"""
Utilities untuk saran preferensi pill dari user ke admin.

User yang tidak menemukan pill cocok dapat mengirim saran label baru.
Admin meninjau status: pending | reviewed | accepted | rejected.
"""

from __future__ import annotations

from datetime import datetime

from auth_utils import get_db_connection
from db_backend import dict_from_row

STATUS_OPTIONS = ('pending', 'reviewed', 'accepted', 'rejected')

_TABLE_READY = False


def _table_columns(cursor, table_name):
    """Nama kolom tabel (set lowercase). Kosong jika tabel belum ada."""
    try:
        from db_backend import use_postgres
        if use_postgres():
            rows = cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = ?
                """,
                (table_name,),
            ).fetchall()
            return {str(r[0]).lower() for r in (rows or [])}
        rows = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
        # PRAGMA: (cid, name, type, notnull, dflt_value, pk)
        return {str(r[1]).lower() for r in (rows or [])}
    except Exception:
        return set()


def ensure_preference_suggestions_table():
    """Buat/migrasikan tabel saran preferensi (idempotent).

    Catatan: `CREATE TABLE IF NOT EXISTS` tidak memperbaiki skema lama.
    DB produksi sempat punya kolom preference_text/reason_text tanpa status —
    fungsi ini menambah kolom yang hilang dan backfill dari skema lama.
    """
    global _TABLE_READY
    if _TABLE_READY:
        return True
    conn = None
    try:
        from db_backend import use_postgres

        conn = get_db_connection()
        cursor = conn.cursor()
        pg = use_postgres()

        if pg:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS preference_suggestions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    label TEXT,
                    description TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    admin_notes TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    resolved_at TIMESTAMPTZ
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS preference_suggestions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    label TEXT,
                    description TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    admin_notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

        cols = _table_columns(cursor, 'preference_suggestions')

        # Migrasi kolom yang hilang (tabel lama: preference_text / reason_text).
        alter_specs = [
            ('label', 'TEXT' if pg else 'TEXT'),
            ('description', 'TEXT' if pg else 'TEXT'),
            ('status', "TEXT NOT NULL DEFAULT 'pending'" if pg else "TEXT NOT NULL DEFAULT 'pending'"),
            ('admin_notes', 'TEXT' if pg else 'TEXT'),
            ('updated_at', 'TIMESTAMPTZ DEFAULT NOW()' if pg else 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
            ('resolved_at', 'TIMESTAMPTZ' if pg else 'TIMESTAMP'),
        ]
        for col_name, col_type in alter_specs:
            if col_name not in cols:
                if pg:
                    cursor.execute(
                        f'ALTER TABLE preference_suggestions ADD COLUMN IF NOT EXISTS {col_name} {col_type}'
                    )
                else:
                    cursor.execute(
                        f'ALTER TABLE preference_suggestions ADD COLUMN {col_name} {col_type}'
                    )

        cols = _table_columns(cursor, 'preference_suggestions')

        # Backfill dari skema lama bila masih ada.
        if 'preference_text' in cols and 'label' in cols:
            cursor.execute(
                """
                UPDATE preference_suggestions
                SET label = preference_text
                WHERE (label IS NULL OR TRIM(label) = '')
                  AND preference_text IS NOT NULL
                """
            )
            # Sync sebaliknya agar baris baru dengan label tetap valid di kolom lama.
            cursor.execute(
                """
                UPDATE preference_suggestions
                SET preference_text = label
                WHERE (preference_text IS NULL OR TRIM(preference_text) = '')
                  AND label IS NOT NULL
                """
            )
        if 'reason_text' in cols and 'description' in cols:
            cursor.execute(
                """
                UPDATE preference_suggestions
                SET description = reason_text
                WHERE (description IS NULL OR TRIM(description) = '')
                  AND reason_text IS NOT NULL
                """
            )
            cursor.execute(
                """
                UPDATE preference_suggestions
                SET reason_text = description
                WHERE (reason_text IS NULL OR TRIM(reason_text) = '')
                  AND description IS NOT NULL
                """
            )
        if 'status' in cols:
            cursor.execute(
                """
                UPDATE preference_suggestions
                SET status = 'pending'
                WHERE status IS NULL OR TRIM(status) = ''
                """
            )

        # Longgarkan NOT NULL pada kolom legacy agar insert berbasis label tidak gagal.
        if pg:
            if 'preference_text' in cols:
                cursor.execute(
                    'ALTER TABLE preference_suggestions ALTER COLUMN preference_text DROP NOT NULL'
                )
            if 'reason_text' in cols:
                cursor.execute(
                    'ALTER TABLE preference_suggestions ALTER COLUMN reason_text DROP NOT NULL'
                )

        if pg:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pref_suggestions_status
                ON preference_suggestions (status, created_at DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pref_suggestions_user
                ON preference_suggestions (user_id, created_at DESC)
            """)
        else:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pref_suggestions_status
                ON preference_suggestions (status, created_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pref_suggestions_user
                ON preference_suggestions (user_id, created_at)
            """)

        conn.commit()
        _TABLE_READY = True
        return True
    except Exception as e:
        print(f"[WARN] ensure_preference_suggestions_table: {e}")
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


def create_preference_suggestion(user_id, label, description=None):
    """Simpan saran preferensi baru dari user login."""
    if not ensure_preference_suggestions_table():
        return {'success': False, 'error': 'Tabel saran preferensi belum siap'}

    uid = int(user_id) if user_id is not None else None
    if not uid:
        return {'success': False, 'error': 'User tidak valid'}

    cleaned_label = ' '.join(str(label or '').strip().split())
    if not cleaned_label:
        return {'success': False, 'error': 'Label preferensi wajib diisi'}
    if len(cleaned_label) > 80:
        return {'success': False, 'error': 'Label maksimal 80 karakter'}

    cleaned_desc = str(description or '').strip() or None
    if cleaned_desc and len(cleaned_desc) > 500:
        return {'success': False, 'error': 'Deskripsi maksimal 500 karakter'}

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.utcnow().isoformat()
        cols = _table_columns(cursor, 'preference_suggestions')

        # Dual-write ke kolom legacy bila masih ada (preference_text/reason_text).
        if 'preference_text' in cols:
            cursor.execute(
                '''
                INSERT INTO preference_suggestions
                    (user_id, label, description, preference_text, reason_text,
                     status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                ''',
                (
                    uid,
                    cleaned_label,
                    cleaned_desc,
                    cleaned_label,
                    cleaned_desc or '',
                    now,
                    now,
                ),
            )
        else:
            cursor.execute(
                '''
                INSERT INTO preference_suggestions
                    (user_id, label, description, status, created_at, updated_at)
                VALUES (?, ?, ?, 'pending', ?, ?)
                ''',
                (uid, cleaned_label, cleaned_desc, now, now),
            )
        conn.commit()

        suggestion_id = getattr(cursor, 'lastrowid', None)
        row = None
        if suggestion_id is not None:
            row = cursor.execute(
                '''
                SELECT id, user_id, label, description, status, admin_notes,
                       created_at, updated_at, resolved_at
                FROM preference_suggestions
                WHERE id = ?
                ''',
                (suggestion_id,),
            ).fetchone()

        suggestion = dict_from_row(cursor, row) if row else {
            'id': suggestion_id,
            'user_id': uid,
            'label': cleaned_label,
            'description': cleaned_desc,
            'status': 'pending',
        }
        return {'success': True, 'suggestion': suggestion}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def list_preference_suggestions(page=1, per_page=10, search='', status_filter=''):
    """Daftar saran untuk admin (paginated)."""
    if not ensure_preference_suggestions_table():
        return {
            'success': False,
            'error': 'Tabel saran preferensi belum siap',
            'items': [],
            'pagination': {'page': 1, 'per_page': per_page, 'total': 0, 'total_pages': 1},
        }

    page = max(int(page or 1), 1)
    per_page = min(max(int(per_page or 10), 1), 100)
    search = (search or '').strip().lower()
    status_filter = (status_filter or '').strip().lower()

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        where_clauses = []
        params = []

        if search:
            where_clauses.append(
                '('
                'LOWER(COALESCE(ps.label, "")) LIKE ? OR '
                'LOWER(COALESCE(ps.description, "")) LIKE ? OR '
                'LOWER(COALESCE(u.username, "")) LIKE ? OR '
                'LOWER(COALESCE(u.email, "")) LIKE ?'
                ')'
            )
            like = f'%{search}%'
            params.extend([like, like, like, like])

        if status_filter:
            where_clauses.append("LOWER(COALESCE(ps.status, 'pending')) = ?")
            params.append(status_filter)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ''

        total = cursor.execute(
            f'''
            SELECT COUNT(*)
            FROM preference_suggestions ps
            LEFT JOIN users u ON u.id = ps.user_id
            {where_sql}
            ''',
            params,
        ).fetchone()[0]

        offset = (page - 1) * per_page
        rows = cursor.execute(
            f'''
            SELECT ps.id, ps.user_id, ps.label, ps.description, ps.status,
                   ps.admin_notes, ps.created_at, ps.updated_at, ps.resolved_at,
                   u.username AS username, u.email AS email
            FROM preference_suggestions ps
            LEFT JOIN users u ON u.id = ps.user_id
            {where_sql}
            ORDER BY ps.created_at DESC
            LIMIT ? OFFSET ?
            ''',
            (*params, per_page, offset),
        ).fetchall()

        items = [dict_from_row(cursor, row) for row in rows]
        return {
            'success': True,
            'items': items,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': max((total + per_page - 1) // per_page, 1),
            },
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'items': [],
            'pagination': {'page': page, 'per_page': per_page, 'total': 0, 'total_pages': 1},
        }
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def update_preference_suggestion(suggestion_id, status='pending', admin_notes=None):
    """Perbarui status/catatan saran (admin)."""
    if not ensure_preference_suggestions_table():
        return {'success': False, 'error': 'Tabel saran preferensi belum siap'}

    cleaned_status = (status or 'pending').strip().lower()
    if cleaned_status not in STATUS_OPTIONS:
        return {
            'success': False,
            'error': f'Status tidak valid. Pilih salah satu: {", ".join(STATUS_OPTIONS)}',
        }

    notes = str(admin_notes or '').strip() or None
    now = datetime.utcnow().isoformat()
    resolved_at = now if cleaned_status in ('accepted', 'rejected') else None

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        existing = cursor.execute(
            'SELECT id FROM preference_suggestions WHERE id = ?',
            (suggestion_id,),
        ).fetchone()
        if not existing:
            return {'success': False, 'error': 'Saran preferensi tidak ditemukan'}

        cursor.execute(
            '''
            UPDATE preference_suggestions
            SET status = ?, admin_notes = ?, updated_at = ?, resolved_at = ?
            WHERE id = ?
            ''',
            (cleaned_status, notes, now, resolved_at, suggestion_id),
        )
        conn.commit()
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

"""
Backend database: Supabase (PostgreSQL) atau SQLite lokal.
- Jika DATABASE_URL ter-set dan COFIND_DB_BACKEND bukan 'sqlite', pakai Postgres.
- Set COFIND_DB_BACKEND=sqlite untuk memaksa SQLite (kode SQLite tetap ada, nonaktif secara default bila URL ada).
"""
from __future__ import annotations

import os
import re
import sqlite3
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'cofind.db')
DATABASE_URL = (os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL") or "").strip()

# Tabel yang memakai SERIAL id dan kode membaca cursor.lastrowid setelah INSERT biasa.
_INSERT_RETURNING_TABLES = frozenset({
    "users",
    "favorites",
    "want_to_visit",
    "preference_suggestions",
    "reviews",
    "coffee_shops",
})


def use_postgres() -> bool:
    explicit = (os.getenv("COFIND_DB_BACKEND") or "").strip().lower()
    if explicit in ("sqlite", "local"):
        return False
    if explicit in ("postgres", "postgresql", "supabase"):
        return bool(DATABASE_URL)
    return bool(DATABASE_URL)


def use_sqlite() -> bool:
    return not use_postgres()


def _adapt_sql_postgres(sql: str) -> str:
    s = sql.replace("?", "%s")
    s = s.replace("datetime('now')", "NOW()")
    s = s.replace("datetime(\"now\")", "NOW()")
    s = re.sub(r'COALESCE\(rr\.status,\s*"pending"\)', "COALESCE(rr.status, 'pending')", s)
    s = s.replace(', "")', ", ''")
    s = s.replace(', ""))', ", ''))")
    s = s.replace('LOWER(COALESCE(rr.status, "pending"))', "LOWER(COALESCE(rr.status, 'pending'))")

    if "INSERT OR REPLACE INTO opening_hours" in sql:
        if "COALESCE((SELECT created_at" in sql:
            return (
                "INSERT INTO opening_hours (place_id, hours_display, created_at, updated_at) "
                "VALUES (%s, %s, COALESCE((SELECT created_at FROM opening_hours WHERE place_id = %s), %s), %s) "
                "ON CONFLICT (place_id) DO UPDATE SET "
                "hours_display = EXCLUDED.hours_display, "
                "created_at = opening_hours.created_at, "
                "updated_at = EXCLUDED.updated_at"
            )
        return (
            "INSERT INTO opening_hours (place_id, hours_display, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (place_id) DO UPDATE SET "
            "hours_display = EXCLUDED.hours_display, "
            "updated_at = EXCLUDED.updated_at"
        )

    return s


def _insert_table_for_returning(sql: str) -> Optional[str]:
    m = re.search(r"INSERT\s+INTO\s+(\w+)", sql, re.IGNORECASE | re.DOTALL)
    return m.group(1).lower() if m else None


def _needs_returning_id(original_sql: str, adapted_sql: str) -> bool:
    if "INSERT OR" in original_sql.upper():
        return False
    if "RETURNING" in adapted_sql.upper():
        return False
    table = _insert_table_for_returning(original_sql)
    return bool(table and table in _INSERT_RETURNING_TABLES)


def dict_from_row(cursor: Any, row: Any) -> Optional[dict]:
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    try:
        return dict(row)
    except (TypeError, ValueError):
        pass
    desc = cursor.description
    if not desc:
        return None
    cols = [d[0] for d in desc]
    return dict(zip(cols, row))


class AdaptingCursor:
    def __init__(self, raw: Any, backend: str):
        self._cur = raw
        self._backend = backend
        self._last_insert_id: Optional[int] = None

    def execute(self, sql: str, params: Optional[tuple] = None):
        params = params or ()
        if self._backend == "postgres":
            original = sql
            sql_adapted = _adapt_sql_postgres(sql)
            if _needs_returning_id(original, sql_adapted):
                sql_adapted = sql_adapted.rstrip().rstrip(";") + " RETURNING id"
                self._cur.execute(sql_adapted, params)
                row = self._cur.fetchone()
                self._last_insert_id = int(row[0]) if row and row[0] is not None else None
            else:
                self._cur.execute(sql_adapted, params)
                self._last_insert_id = None
        else:
            self._cur.execute(sql, params)
            self._last_insert_id = None
        return self

    def executemany(self, sql: str, seq_of_params):
        if self._backend == "postgres":
            sql = _adapt_sql_postgres(sql)
        return self._cur.executemany(sql, seq_of_params)

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    @property
    def description(self):
        return self._cur.description

    @property
    def lastrowid(self):
        if self._backend == "postgres":
            return self._last_insert_id
        return self._cur.lastrowid

    def __getattr__(self, name: str):
        return getattr(self._cur, name)


class AdaptingConnection:
    def __init__(self, raw: Any, backend: str):
        self._raw = raw
        self._backend = backend

    def __enter__(self):
        self._raw.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        return self._raw.__exit__(exc_type, exc, tb)

    def cursor(self, *args, **kwargs):
        if self._backend == "postgres":
            return AdaptingCursor(self._raw.cursor(*args, **kwargs), self._backend)
        return AdaptingCursor(self._raw.cursor(*args, **kwargs), self._backend)

    def execute(self, sql, params=None):
        """Kompatibel dengan sqlite3.Connection.execute (untuk kode legacy)."""
        cur = self.cursor()
        cur.execute(sql, params or ())
        return cur

    def commit(self):
        return self._raw.commit()

    def rollback(self):
        return self._raw.rollback()

    def close(self):
        return self._raw.close()

    @property
    def row_factory(self):
        return getattr(self._raw, "row_factory", None)

    @row_factory.setter
    def row_factory(self, value):
        if hasattr(self._raw, "row_factory"):
            self._raw.row_factory = value


def get_connection() -> AdaptingConnection:
    if use_postgres():
        import psycopg2

        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL (atau SUPABASE_DB_URL) wajib untuk backend Postgres/Supabase.")
        raw = psycopg2.connect(DATABASE_URL)
        return AdaptingConnection(raw, "postgres")

    raw = sqlite3.connect(DATABASE_PATH, timeout=10)
    raw.row_factory = sqlite3.Row
    try:
        raw.execute("PRAGMA journal_mode=WAL;")
        raw.execute("PRAGMA busy_timeout=5000;")
    except sqlite3.Error:
        pass
    return AdaptingConnection(raw, "sqlite")

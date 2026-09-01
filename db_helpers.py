"""Helper query database yang dipakai beberapa modul route."""

from __future__ import annotations


def paginate_query(cursor, base_query: str, params, page: int, per_page: int):
    """Jalankan `base_query` dengan LIMIT/OFFSET berdasarkan halaman (1-indexed)."""
    offset = (page - 1) * per_page
    return cursor.execute(
        f"{base_query} LIMIT ? OFFSET ?",
        [*params, per_page, offset],
    ).fetchall()

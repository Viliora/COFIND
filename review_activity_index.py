"""Indeks bukti aktivitas per (place_id, pill) — dibangun offline, dibaca saat gerbang."""

from __future__ import annotations

import os
from typing import FrozenSet, Optional, Sequence

from logging_config import get_logger

logger = get_logger("review_activity_index")

_TABLE = "review_activity_hits"


def index_enabled() -> bool:
    raw = (os.getenv("COFIND_REVIEW_ACTIVITY_INDEX") or "true").strip().lower()
    return raw not in ("0", "false", "no", "off")


def ensure_review_activity_index_table() -> bool:
    try:
        from db_backend import get_connection

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {_TABLE} (
                place_id TEXT NOT NULL,
                pill TEXT NOT NULL,
                review_id INTEGER,
                score REAL NOT NULL DEFAULT 0,
                updated_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (place_id, pill, review_id)
            )
            """
        )
        cur.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{_TABLE}_place_pill ON {_TABLE}(place_id, pill)"
        )
        conn.commit()
        conn.close()
        return True
    except Exception as err:
        logger.warning(f"ensure_review_activity_index_table: {err}")
        return False


def clear_index() -> None:
    if not ensure_review_activity_index_table():
        return
    from db_backend import get_connection

    conn = get_connection()
    conn.execute(f"DELETE FROM {_TABLE}")
    conn.commit()
    conn.close()


def upsert_hit(place_id: str, pill: str, review_id: Optional[int], score: float) -> None:
    from db_backend import get_connection

    pid = str(place_id or "").strip()
    pl = str(pill or "").strip()
    if not pid or not pl:
        return
    conn = get_connection()
    conn.execute(
        f"""
        INSERT INTO {_TABLE} (place_id, pill, review_id, score, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        ON CONFLICT(place_id, pill, review_id) DO UPDATE SET
            score = excluded.score,
            updated_at = excluded.updated_at
        """,
        (pid, pl, review_id, float(score)),
    )
    conn.commit()
    conn.close()


def place_has_activity_pills(place_id: str, pills: Sequence[str]) -> bool:
    if not index_enabled():
        return False
    pid = str(place_id or "").strip()
    wanted = {str(p).strip() for p in (pills or []) if str(p or "").strip()}
    if not pid or not wanted:
        return False
    if not ensure_review_activity_index_table():
        return False
    try:
        from db_backend import get_connection

        conn = get_connection()
        placeholders = ",".join("?" for _ in wanted)
        row = conn.execute(
            f"""
            SELECT 1 FROM {_TABLE}
            WHERE place_id = ? AND pill IN ({placeholders}) AND score > 0
            LIMIT 1
            """,
            (pid, *sorted(wanted)),
        ).fetchone()
        conn.close()
        return row is not None
    except Exception as err:
        logger.warning(f"place_has_activity_pills: {err}")
        return False


def indexed_pills_for_place(place_id: str) -> FrozenSet[str]:
    pid = str(place_id or "").strip()
    if not pid or not index_enabled():
        return frozenset()
    if not ensure_review_activity_index_table():
        return frozenset()
    try:
        from db_backend import get_connection

        conn = get_connection()
        rows = conn.execute(
            f"SELECT DISTINCT pill FROM {_TABLE} WHERE place_id = ? AND score > 0",
            (pid,),
        ).fetchall()
        conn.close()
        return frozenset(str(r[0]) for r in rows if r and r[0])
    except Exception as err:
        logger.warning(f"indexed_pills_for_place: {err}")
        return frozenset()

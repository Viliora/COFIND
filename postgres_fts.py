"""Skor BM25/sparse via Postgres FTS per toko (kandidat terbatas)."""

from __future__ import annotations

import os
from typing import Dict, List, Sequence

from logging_config import get_logger

logger = get_logger('recommend')


def bm25_backend() -> str:
    return (os.getenv('COFIND_BM25_BACKEND') or 'memory').strip().lower()


def postgres_fts_enabled() -> bool:
    return bm25_backend() == 'postgres'


def score_shops_fts(place_ids: Sequence[str], query_tokens: Sequence[str]) -> Dict[str, float]:
    if not place_ids or not query_tokens:
        return {}
    from db_backend import get_connection
    from shop_search_store import ensure_coffee_shop_search_columns

    if not ensure_coffee_shop_search_columns():
        return {}
    query = ' & '.join(
        t.replace("'", "''") for t in query_tokens if str(t or '').strip()
    )
    if not query:
        return {}
    ids = [str(p).strip() for p in place_ids if str(p or '').strip()]
    if not ids:
        return {}
    placeholders = ','.join(['%s'] * len(ids))
    sql = f"""
        SELECT place_id,
               ts_rank_cd(review_tsv, plainto_tsquery('simple', %s)) AS rank
        FROM coffee_shops
        WHERE place_id IN ({placeholders})
          AND review_tsv @@ plainto_tsquery('simple', %s)
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        params = [query, *ids, query]
        cur.execute(sql, params)
        out: Dict[str, float] = {}
        for row in cur.fetchall():
            out[str(row[0])] = float(row[1] or 0.0)
        return out
    except Exception as err:
        logger.warning('postgres FTS gagal: %s', str(err)[:200])
        return {}
    finally:
        conn.close()

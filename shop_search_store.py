"""Kolom FTS agregat per coffee shop (review_document_text + review_tsv)."""

from __future__ import annotations

from logging_config import get_logger
from review_utils import get_reviews_for_shop

logger = get_logger('db')

_TABLE_READY = False


def ensure_coffee_shop_search_columns() -> bool:
    global _TABLE_READY
    if _TABLE_READY:
        return True
    from db_backend import get_connection

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "ALTER TABLE coffee_shops ADD COLUMN IF NOT EXISTS review_document_text TEXT"
        )
        cur.execute(
            "ALTER TABLE coffee_shops ADD COLUMN IF NOT EXISTS review_tsv tsvector"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_coffee_shops_review_tsv "
            "ON coffee_shops USING GIN (review_tsv)"
        )
        conn.commit()
        _TABLE_READY = True
        return True
    except Exception as err:
        conn.rollback()
        logger.warning('ensure_coffee_shop_search_columns gagal: %s', err)
        return False
    finally:
        conn.close()


def refresh_shop_search_document(place_id: str) -> bool:
    from bm25_utils import shop_document_text
    from hybrid_retrieval import tokenize_for_match
    from slang_normalize import normalize_text_with_slang

    pid = str(place_id or '').strip()
    if not pid:
        return False
    if not ensure_coffee_shop_search_columns():
        return False
    result = get_reviews_for_shop(pid, limit=None)
    reviews = (result.get('reviews') or []) if isinstance(result, dict) else []
    doc = shop_document_text(reviews or [])
    normalized = ' '.join(tokenize_for_match(normalize_text_with_slang(doc)))
    from db_backend import get_connection

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE coffee_shops
            SET review_document_text = %s,
                review_tsv = to_tsvector('simple', COALESCE(%s, ''))
            WHERE place_id = %s
            """,
            (doc, normalized, pid),
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception as err:
        conn.rollback()
        logger.warning('refresh_shop_search_document(%s): %s', pid, err)
        return False
    finally:
        conn.close()

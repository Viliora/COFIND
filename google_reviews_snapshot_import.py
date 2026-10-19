"""
Impor ulasan Google dari data/google_reviews_snapshot.json ke tabel `reviews`.

Operasional (tanpa API di runtime):
  1. python fetch_google_places_reviews.py -o data/google_reviews_snapshot.json
  2. python import_google_reviews_from_snapshot.py

Baris impor: review_source = 'google_places', user_id NULL.
Ulasan komunitas: review_source = 'cofind' (default).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from db_backend import get_connection
from logging_config import get_logger

logger = get_logger("google_reviews_import")

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SNAPSHOT_PATH = os.path.join(_REPO_ROOT, "data", "google_reviews_snapshot.json")

GOOGLE_REVIEW_SOURCE = "google_places"
COFIND_REVIEW_SOURCE = "cofind"


def trim_review_for_storage(rev: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(rev, dict):
        return {}
    text = rev.get("text")
    return {
        "rating": rev.get("rating"),
        "text": (str(text).strip() if text is not None else ""),
        "publish_time": rev.get("publish_time"),
        "relative_time": rev.get("relative_time"),
        "author_display_name": rev.get("author_display_name"),
    }


def _parse_json_col(value: Any) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _parse_snapshot_generated_at(payload: dict) -> datetime | None:
    raw = payload.get("generated_at")
    if not raw:
        return None
    try:
        s = str(raw).replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _publish_time_to_created_at(publish_time: Any) -> str:
    try:
        ts = int(publish_time)
        if ts <= 0:
            return datetime.utcnow().isoformat()
        return datetime.utcfromtimestamp(ts).replace(microsecond=0).isoformat()
    except (TypeError, ValueError):
        return datetime.utcnow().isoformat()


def ensure_reviews_unified_schema(conn) -> None:
    """Kolom & indeks untuk ulasan Google di tabel reviews; migrasi dari google_maps_reviews jika ada."""
    cur = conn.cursor()
    stmts = [
        "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS review_source TEXT NOT NULL DEFAULT 'cofind'",
        "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS author_display_name TEXT",
        "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS relative_time TEXT",
        "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS external_publish_time BIGINT",
    ]
    for sql in stmts:
        try:
            cur.execute(sql)
        except Exception as err:
            if "duplicate column" not in str(err).lower():
                raise
    try:
        cur.execute("ALTER TABLE reviews ALTER COLUMN user_id DROP NOT NULL")
    except Exception:
        pass
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_reviews_google_places_dedupe
        ON reviews (place_id, author_display_name, external_publish_time)
        WHERE review_source = 'google_places'
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_reviews_place_source_created
        ON reviews (place_id, review_source, created_at DESC)
        """
    )
    conn.commit()
    _migrate_legacy_google_maps_reviews_table(conn)


def _migrate_legacy_google_maps_reviews_table(conn) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'google_maps_reviews'
            """
        )
        if not cur.fetchone():
            return
    except Exception:
        return

    cur.execute(
        """
        SELECT gmr.place_id, gmr.rating, gmr.review_text, gmr.publish_time,
               gmr.relative_time, gmr.author_display_name, cs.id AS shop_id
        FROM google_maps_reviews gmr
        INNER JOIN coffee_shops cs ON cs.place_id = gmr.place_id
        """
    )
    rows = cur.fetchall() or []
    migrated = 0
    for row in rows:
        if isinstance(row, dict):
            place_id = row.get("place_id")
            shop_id = row.get("shop_id")
            rating = row.get("rating")
            text = row.get("review_text")
            pub = row.get("publish_time")
            rel = row.get("relative_time")
            author = row.get("author_display_name")
        else:
            place_id, rating, text, pub, rel, author, shop_id = (
                list(row) + [None] * 7
            )[:7]
        author = str(author or "").strip() or "Google User"
        try:
            pub_int = int(pub) if pub is not None else None
        except (TypeError, ValueError):
            pub_int = None
        created = _publish_time_to_created_at(pub_int)
        cur.execute(
            """
            SELECT 1 FROM reviews
            WHERE place_id = ? AND review_source = ?
              AND author_display_name = ? AND external_publish_time IS NOT DISTINCT FROM ?
            """,
            (place_id, GOOGLE_REVIEW_SOURCE, author, pub_int),
        )
        if cur.fetchone():
            continue
        cur.execute(
            """
            INSERT INTO reviews (
                user_id, shop_id, place_id, rating, review_text,
                created_at, updated_at, review_source,
                author_display_name, relative_time, external_publish_time
            )
            VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                shop_id,
                place_id,
                rating,
                text or "",
                created,
                created,
                GOOGLE_REVIEW_SOURCE,
                author,
                rel,
                pub_int,
            ),
        )
        migrated += 1

    cur.execute("DROP TABLE IF EXISTS google_maps_reviews CASCADE")
    conn.commit()
    if migrated:
        logger.info("Migrasi %s baris dari google_maps_reviews ke reviews", migrated)


def import_google_reviews_snapshot(
    json_path: str | None = None,
    *,
    conn=None,
) -> dict[str, Any]:
    path = json_path or DEFAULT_SNAPSHOT_PATH
    summary: dict[str, Any] = {
        "snapshot_path": path,
        "shops_processed": 0,
        "reviews_inserted": 0,
        "reviews_removed": 0,
        "shops_updated": 0,
        "skipped_place_ids": [],
        "warnings": [],
        "errors": [],
    }
    if not os.path.isfile(path):
        summary["errors"].append(f"File tidak ditemukan: {path}")
        return summary

    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    shops = payload.get("shops") or []
    if not isinstance(shops, list):
        summary["errors"].append("Format snapshot: shops bukan array")
        return summary

    snapshot_at = _parse_snapshot_generated_at(payload)
    snapshot_at_iso = snapshot_at.isoformat() if snapshot_at else None

    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    ensure_reviews_unified_schema(conn)
    cur = conn.cursor()

    for shop in shops:
        if not isinstance(shop, dict):
            continue
        place_id = str(shop.get("db_place_id") or "").strip()
        if not place_id:
            continue

        google_place_id = str(shop.get("google_place_id") or "").strip()
        if google_place_id and google_place_id != place_id:
            summary["warnings"].append(
                f"{place_id}: db_place_id != google_place_id ({google_place_id})"
            )

        cur.execute(
            "SELECT id FROM coffee_shops WHERE place_id = ?",
            (place_id,),
        )
        shop_row = cur.fetchone()
        if not shop_row:
            summary["skipped_place_ids"].append(place_id)
            continue
        shop_id = shop_row[0] if not isinstance(shop_row, dict) else shop_row.get("id")

        cur.execute(
            """
            SELECT COUNT(*) FROM reviews
            WHERE place_id = ? AND review_source = ?
            """,
            (place_id, GOOGLE_REVIEW_SOURCE),
        )
        removed_row = cur.fetchone()
        removed_before = int((removed_row[0] if removed_row else 0) or 0)

        cur.execute(
            """
            DELETE FROM reviews
            WHERE place_id = ? AND review_source = ?
            """,
            (place_id, GOOGLE_REVIEW_SOURCE),
        )
        summary["reviews_removed"] += removed_before

        reviews_raw = shop.get("reviews") or []
        inserted = 0
        shop_trimmed: list[dict] = []
        for rev in reviews_raw:
            trimmed = trim_review_for_storage(rev)
            if not trimmed.get("text") and trimmed.get("rating") is None:
                continue
            author = str(trimmed.get("author_display_name") or "").strip() or "Google User"
            pub = trimmed.get("publish_time")
            try:
                pub_int = int(pub) if pub is not None else None
            except (TypeError, ValueError):
                pub_int = None
            rating = trimmed.get("rating")
            try:
                rating_int = int(rating) if rating is not None else None
            except (TypeError, ValueError):
                rating_int = None

            created = _publish_time_to_created_at(pub_int)
            cur.execute(
                """
                INSERT INTO reviews (
                    user_id, shop_id, place_id, rating, review_text,
                    created_at, updated_at, review_source,
                    author_display_name, relative_time, external_publish_time
                )
                VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (
                    shop_id,
                    place_id,
                    rating_int,
                    trimmed.get("text") or "",
                    created,
                    created,
                    GOOGLE_REVIEW_SOURCE,
                    author,
                    trimmed.get("relative_time"),
                    pub_int,
                ),
            )
            new_row = cur.fetchone()
            review_id = new_row[0] if new_row and not isinstance(new_row, dict) else (
                new_row.get("id") if isinstance(new_row, dict) else None
            )
            if review_id:
                try:
                    from review_embedding_store import schedule_review_embedding_after_write
                    schedule_review_embedding_after_write(
                        int(review_id), trimmed.get("text") or ""
                    )
                except Exception as embed_err:
                    logger.debug("embedding schedule skip: %s", embed_err)
            inserted += 1
            shop_trimmed.append(trimmed)

        summary["reviews_inserted"] += inserted
        summary["shops_processed"] += 1

        cur.execute(
            "SELECT google_places_snapshot, rating, total_reviews FROM coffee_shops WHERE place_id = ?",
            (place_id,),
        )
        row = cur.fetchone()
        existing_snapshot = {}
        old_rating = None
        old_total = None
        if row:
            if isinstance(row, dict):
                existing_snapshot = _parse_json_col(row.get("google_places_snapshot"))
                old_rating = row.get("rating")
                old_total = row.get("total_reviews")
            else:
                existing_snapshot = _parse_json_col(row[0])
                old_rating = row[1]
                old_total = row[2]

        merged = {**existing_snapshot}
        aggregates = dict(merged.get("aggregates") or {})
        google_rating = shop.get("google_rating")
        google_total = shop.get("google_user_rating_count")
        if google_rating is not None:
            aggregates["rating"] = google_rating
        if google_total is not None:
            aggregates["user_ratings_total"] = google_total
        merged["aggregates"] = aggregates
        merged["reviews"] = shop_trimmed
        if snapshot_at_iso:
            merged["fetched_at"] = snapshot_at_iso
        if shop.get("google_maps_uri"):
            merged["google_maps_url"] = shop.get("google_maps_uri")

        new_rating = float(google_rating) if google_rating is not None else old_rating
        new_total = int(google_total) if google_total is not None else old_total

        cur.execute(
            """
            UPDATE coffee_shops
            SET rating = ?,
                total_reviews = ?,
                google_places_snapshot = ?::jsonb,
                updated_at = NOW()
            WHERE place_id = ?
            """,
            (
                new_rating if new_rating is not None else 0,
                new_total if new_total is not None else 0,
                json.dumps(merged, ensure_ascii=False),
                place_id,
            ),
        )
        if cur.rowcount:
            summary["shops_updated"] += 1

    conn.commit()
    if own_conn:
        conn.close()

    logger.info(
        "Impor snapshot selesai: %s toko, %s ulasan",
        summary["shops_processed"],
        summary["reviews_inserted"],
    )
    return summary

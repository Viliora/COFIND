"""
Ambil ulasan Google Places untuk semua coffee shop di database.

Alur per toko:
  1. Pencarian tempat dari coffee_shops.name (+ address ringkas)
  2. Place Details → reviews (max 5), reviews_sort=most_relevant (Legacy) / relevance (New)

Default: Places API Legacy (kompatibel dengan kunci Maps AIza...).

Setelah fetch, impor ke database (tanpa API rutin di app):
    python import_google_reviews_from_snapshot.py

Pemakaian:
    python fetch_google_places_reviews.py
    python fetch_google_places_reviews.py --limit 3
    python fetch_google_places_reviews.py --place-id ChIJ...
    python fetch_google_places_reviews.py -o data/google_reviews_snapshot.json
    python fetch_google_places_reviews.py --dry-run

Kunci Maps: GOOGLE_PLACES_API_KEY, GOOGLE_MAPS_API_KEY, atau VITE_GOOGLE_MAPS_API_KEY
(harus format AIza..., bukan token Gemini). Butuh DATABASE_URL / SUPABASE_DB_URL.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

import requests
from dotenv import load_dotenv

from places_api_client import (
    build_search_query,
    legacy_place_details,
    legacy_text_search_first as legacy_text_search,
    normalize_reviews_legacy,
    normalize_reviews_new,
    pick_place_candidate,
    places_get_details_new,
    places_text_search_new,
    resolve_api_key,
)

load_dotenv()


def fetch_coffee_shops_from_db(
    place_id: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    from db_backend import dict_from_row, get_connection

    sql = """
        SELECT place_id, name, address, rating, total_reviews
        FROM coffee_shops
        ORDER BY name ASC
    """
    params: list[Any] = []
    if place_id:
        sql = """
            SELECT place_id, name, address, rating, total_reviews
            FROM coffee_shops
            WHERE place_id = ?
        """
        params.append(place_id)
    if limit is not None and not place_id:
        sql += " LIMIT ?"
        params.append(int(limit))
    elif limit is not None and place_id:
        pass

    conn = get_connection()
    try:
        cur = conn.cursor()
        rows = cur.execute(sql, tuple(params)).fetchall()
        return [dict_from_row(cur, row) or {} for row in rows]
    finally:
        conn.close()


def process_shop(
    session: requests.Session,
    api_key: str,
    shop: dict[str, Any],
    *,
    api_mode: str,
) -> dict[str, Any]:
    db_place_id = str(shop.get("place_id") or "")
    name = str(shop.get("name") or "")
    address = str(shop.get("address") or "")
    search_query = build_search_query(name, address)

    if api_mode == "new":
        search_hit = places_text_search_new(session, api_key, search_query)
    else:
        search_hit = legacy_text_search(session, api_key, search_query)
    if search_hit and search_hit.get("_error"):
        return {
            "db_place_id": db_place_id,
            "db_name": name,
            "db_address": address,
            "search_query": search_query,
            "error": search_hit.get("message"),
            "reviews_sort": "most_relevant",
        }

    google_place_id, match_note = pick_place_candidate(search_hit, db_place_id)
    if not google_place_id:
        return {
            "db_place_id": db_place_id,
            "db_name": name,
            "db_address": address,
            "search_query": search_query,
            "error": match_note or "no_match",
            "reviews_sort": "most_relevant",
        }

    if api_mode == "new":
        details = places_get_details_new(session, api_key, google_place_id)
    else:
        details = legacy_place_details(session, api_key, google_place_id)
    if details.get("_error"):
        return {
            "db_place_id": db_place_id,
            "db_name": name,
            "db_address": address,
            "search_query": search_query,
            "google_place_id": google_place_id,
            "match_note": match_note,
            "error": details.get("message"),
            "reviews_sort": "most_relevant",
        }

    if api_mode == "new":
        display = details.get("displayName") or {}
        matched_name = display.get("text") if isinstance(display, dict) else display
        return {
            "db_place_id": db_place_id,
            "db_name": name,
            "db_address": address,
            "search_query": search_query,
            "google_place_id": google_place_id,
            "match_note": match_note,
            "matched_display_name": matched_name,
            "matched_formatted_address": details.get("formattedAddress"),
            "google_rating": details.get("rating"),
            "google_user_rating_count": details.get("userRatingCount"),
            "google_maps_uri": details.get("googleMapsUri"),
            "reviews_sort": "most_relevant",
            "reviews_count_returned": len(details.get("reviews") or []),
            "reviews": normalize_reviews_new(details),
            "error": None,
        }

    return {
        "db_place_id": db_place_id,
        "db_name": name,
        "db_address": address,
        "search_query": search_query,
        "google_place_id": google_place_id,
        "match_note": match_note,
        "matched_display_name": details.get("name"),
        "matched_formatted_address": details.get("formatted_address"),
        "google_rating": details.get("rating"),
        "google_user_rating_count": details.get("user_ratings_total"),
        "google_maps_uri": details.get("url"),
        "reviews_sort": "most_relevant",
        "reviews_count_returned": len(details.get("reviews") or []),
        "reviews": normalize_reviews_legacy(details),
        "error": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch Google Places reviews for coffee shops in DB (by name search)."
    )
    parser.add_argument("--place-id", help="Hanya satu coffee_shops.place_id")
    parser.add_argument("--limit", type=int, help="Batas jumlah toko (urut nama)")
    parser.add_argument(
        "-o",
        "--output",
        default="",
        help="Path file JSON output (default: stdout)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.35,
        help="Jeda detik antar toko (hindari rate limit)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Hanya list toko dari DB, tanpa panggil Google",
    )
    parser.add_argument(
        "--api",
        choices=("legacy", "new"),
        default="legacy",
        help="Places API Legacy (default, AIza key) atau New",
    )
    args = parser.parse_args()

    try:
        shops = fetch_coffee_shops_from_db(
            place_id=args.place_id,
            limit=args.limit,
        )
    except Exception as exc:
        print(f"Gagal baca database: {exc}", file=sys.stderr)
        return 1

    if not shops:
        print("Tidak ada baris coffee_shops.", file=sys.stderr)
        return 1

    if args.dry_run:
        payload = {
            "dry_run": True,
            "shop_count": len(shops),
            "shops": [
                {
                    "place_id": s.get("place_id"),
                    "name": s.get("name"),
                    "search_query": build_search_query(
                        str(s.get("name") or ""),
                        str(s.get("address") or ""),
                    ),
                }
                for s in shops
            ],
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(text)
        else:
            print(text)
        return 0

    api_key, key_source = resolve_api_key()
    print(
        f"Menggunakan kunci dari {key_source}, API={args.api}",
        file=sys.stderr,
    )
    session = requests.Session()
    results: list[dict[str, Any]] = []
    errors = 0

    for i, shop in enumerate(shops):
        if i > 0 and args.delay > 0:
            time.sleep(args.delay)
        row = process_shop(session, api_key, shop, api_mode=args.api)
        results.append(row)
        if row.get("error"):
            errors += 1
            print(
                f"[WARN] {shop.get('name')}: {row.get('error')}",
                file=sys.stderr,
            )
        else:
            n = row.get("reviews_count_returned", 0)
            print(
                f"[OK] {shop.get('name')} → {n} review(s), place_id={row.get('google_place_id')}",
                file=sys.stderr,
            )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_mode": args.api,
        "api_key_env": key_source,
        "reviews_sort": "most_relevant",
        "note": (
            "Maks. 5 ulasan per toko. Legacy: reviews_sort=most_relevant; "
            "New: sorted by relevance. Pencarian teks dari coffee_shops.name."
        ),
        "shop_count": len(results),
        "error_count": errors,
        "shops": results,
    }

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        out_path = args.output
        parent = os.path.dirname(out_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Disimpan: {out_path}", file=sys.stderr)
    else:
        print(text)

    return 0 if errors < len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

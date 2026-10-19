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
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PLACES_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"
LEGACY_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
LEGACY_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

_GOOGLE_PLACE_ID_RE = re.compile(r"^ChI[A-Za-z0-9_-]+$")
_MAPS_KEY_ENV_ORDER = (
    "GOOGLE_PLACES_API_KEY",
    "GOOGLE_MAPS_API_KEY",
    "VITE_GOOGLE_MAPS_API_KEY",
)


def _resolve_api_key() -> tuple[str, str]:
    """Return (api_key, env_var_name). Hanya terima kunci Maps (AIza...)."""
    invalid: list[str] = []
    for env_name in _MAPS_KEY_ENV_ORDER:
        key = (os.getenv(env_name) or "").strip()
        if not key or key == "YOUR_API_KEY_HERE":
            continue
        if key.startswith("AIza"):
            return key, env_name
        invalid.append(env_name)
    hint = ""
    if invalid:
        hint = (
            f" ({', '.join(invalid)} ter-set tapi bukan kunci Maps AIza... — "
            "salin kunci dari Google Cloud Console / Maps Platform.)"
        )
    raise SystemExit(
        "Tidak ada kunci Maps valid. Set GOOGLE_PLACES_API_KEY=AIza... di .env"
        + hint
    )


def _headers(field_mask: str, api_key: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": field_mask,
    }


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


def build_search_query(name: str, address: str | None) -> str:
    name = (name or "").strip()
    address = (address or "").strip()
    if not name:
        return ""
    if address:
        # Potong alamat panjang agar query fokus ke nama + area
        short_addr = address.split(",")[0].strip()
        if short_addr and short_addr.lower() not in name.lower():
            return f"{name} {short_addr}"
    return name


def legacy_text_search(
    session: requests.Session,
    api_key: str,
    text_query: str,
) -> dict[str, Any] | None:
    if not text_query:
        return None
    resp = session.get(
        LEGACY_TEXT_SEARCH_URL,
        params={"query": text_query, "language": "id", "key": api_key},
        timeout=30,
    )
    if resp.status_code != 200:
        return {
            "_error": True,
            "status_code": resp.status_code,
            "message": resp.text[:500],
        }
    data = resp.json()
    status = data.get("status")
    if status not in ("OK", "ZERO_RESULTS"):
        return {
            "_error": True,
            "message": data.get("error_message") or status or resp.text[:500],
        }
    results = data.get("results") or []
    if not results:
        return None
    hit = results[0]
    return {
        "place_id": hit.get("place_id"),
        "name": hit.get("name"),
        "formatted_address": hit.get("formatted_address"),
    }


def legacy_place_details(
    session: requests.Session,
    api_key: str,
    google_place_id: str,
) -> dict[str, Any]:
    resp = session.get(
        LEGACY_DETAILS_URL,
        params={
            "place_id": google_place_id,
            "fields": "place_id,name,rating,user_ratings_total,reviews,formatted_address,url",
            "reviews_sort": "most_relevant",
            "language": "id",
            "key": api_key,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        return {
            "_error": True,
            "status_code": resp.status_code,
            "message": resp.text[:800],
        }
    data = resp.json()
    if data.get("status") != "OK":
        return {
            "_error": True,
            "message": data.get("error_message") or data.get("status"),
        }
    return data.get("result") or {}


def places_text_search_new(
    session: requests.Session,
    api_key: str,
    text_query: str,
) -> dict[str, Any] | None:
    if not text_query:
        return None
    body = {
        "textQuery": text_query,
        "languageCode": "id",
        "regionCode": "ID",
        "maxResultCount": 5,
    }
    resp = session.post(
        PLACES_TEXT_SEARCH_URL,
        headers=_headers(
            "places.id,places.displayName,places.formattedAddress",
            api_key,
        ),
        json=body,
        timeout=30,
    )
    if resp.status_code != 200:
        return {
            "_error": True,
            "status_code": resp.status_code,
            "message": resp.text[:500],
        }
    data = resp.json()
    places = data.get("places") or []
    if not places:
        return None
    return places[0]


def pick_place_candidate(
    search_hit: dict[str, Any] | None,
    db_place_id: str,
) -> tuple[str | None, str | None]:
    """Pilih place_id Google untuk Place Details."""
    if search_hit and search_hit.get("_error"):
        return None, "text_search_failed"
    hit_id = (search_hit or {}).get("place_id") or (search_hit or {}).get("id") or ""
    db_place_id = (db_place_id or "").strip()
    if hit_id:
        if db_place_id and _GOOGLE_PLACE_ID_RE.match(db_place_id):
            if db_place_id == hit_id:
                return hit_id, None
            # Tetap pakai hasil search (berdasarkan nama); catat mismatch di output
            return hit_id, "db_place_id_differs_from_search"
        return hit_id, None
    if db_place_id and _GOOGLE_PLACE_ID_RE.match(db_place_id):
        return db_place_id, "text_search_empty_used_db_place_id"
    return None, "no_google_place_id"


def places_get_details_new(
    session: requests.Session,
    api_key: str,
    google_place_id: str,
) -> dict[str, Any]:
    url = PLACES_DETAILS_URL.format(place_id=google_place_id)
    field_mask = (
        "id,displayName,formattedAddress,rating,userRatingCount,reviews,googleMapsUri"
    )
    resp = session.get(
        url,
        headers=_headers(field_mask, api_key),
        params={"languageCode": "id"},
        timeout=30,
    )
    if resp.status_code != 200:
        return {
            "_error": True,
            "status_code": resp.status_code,
            "message": resp.text[:800],
        }
    return resp.json()


def normalize_reviews_new(place: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for rev in place.get("reviews") or []:
        text_obj = rev.get("text") or rev.get("originalText") or {}
        author = rev.get("authorAttribution") or {}
        out.append(
            {
                "rating": rev.get("rating"),
                "text": text_obj.get("text") if isinstance(text_obj, dict) else text_obj,
                "language_code": text_obj.get("languageCode")
                if isinstance(text_obj, dict)
                else None,
                "publish_time": rev.get("publishTime"),
                "relative_time": rev.get("relativePublishTimeDescription"),
                "author_display_name": author.get("displayName"),
                "author_uri": author.get("uri"),
                "google_maps_uri": rev.get("googleMapsUri"),
                "review_resource_name": rev.get("name"),
            }
        )
    return out


def normalize_reviews_legacy(place: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for rev in place.get("reviews") or []:
        out.append(
            {
                "rating": rev.get("rating"),
                "text": rev.get("text"),
                "language_code": None,
                "publish_time": rev.get("time"),
                "relative_time": rev.get("relative_time_description"),
                "author_display_name": rev.get("author_name"),
                "author_uri": rev.get("author_url"),
                "google_maps_uri": None,
                "review_resource_name": None,
            }
        )
    return out


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
        normalize = normalize_reviews_new
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
            "reviews": normalize(details),
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

    api_key, key_source = _resolve_api_key()
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

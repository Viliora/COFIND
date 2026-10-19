"""
Fetch metadata Google Places (Legacy Details) dan simpan ke coffee_shops.

Kolom: rating, total_reviews, price_level, facilities (JSON), google_places_snapshot (JSON).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import requests

from fetch_google_places_reviews import (
    _resolve_api_key,
    build_search_query,
    fetch_coffee_shops_from_db,
    legacy_place_details,
    legacy_text_search,
    normalize_reviews_legacy,
    pick_place_candidate,
)

LEGACY_METADATA_FIELDS = (
    "place_id,name,formatted_address,url,rating,user_ratings_total,price_level,"
    "curbside_pickup,delivery,dine_in,takeout,reservable,"
    "serves_breakfast,serves_brunch,serves_lunch,serves_dinner,"
    "serves_beer,serves_wine,serves_vegetarian_food,"
    "wheelchair_accessible_entrance,editorial_summary,business_status"
)

PRICE_LEVEL_LABELS = {
    0: "Gratis",
    1: "Murah",
    2: "Sedang",
    3: "Mahal",
    4: "Sangat mahal",
}


def ensure_coffee_shop_google_columns(conn) -> None:
    cur = conn.cursor()
    stmts = [
        "ALTER TABLE coffee_shops ADD COLUMN IF NOT EXISTS facilities JSONB DEFAULT '{}'::jsonb",
        "ALTER TABLE coffee_shops ADD COLUMN IF NOT EXISTS google_places_snapshot JSONB DEFAULT '{}'::jsonb",
        "ALTER TABLE coffee_shops ADD COLUMN IF NOT EXISTS price_level INTEGER",
    ]
    for sql in stmts:
        try:
            cur.execute(sql)
        except Exception as err:
            if "duplicate column" not in str(err).lower():
                raise
    conn.commit()


def _parse_json_col(value: Any) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value) or {}
        except json.JSONDecodeError:
            return {}
    return {}


def legacy_result_to_facilities(result: dict[str, Any], existing: dict | None = None) -> dict:
    """Map respons Place Details Legacy ke struktur facilities (FacilitiesTab)."""
    base = existing if isinstance(existing, dict) else {}
    out = {**base}

    def ensure_dict(key: str) -> dict:
        val = out.get(key)
        if not isinstance(val, dict):
            val = {}
            out[key] = val
        return val

    service = ensure_dict("service_options")
    for api_key, dest in (
        ("dine_in", "dine_in"),
        ("takeout", "takeaway"),
        ("delivery", "delivery"),
        ("curbside_pickup", "curbside_pickup"),
        ("reservable", "reservable"),
    ):
        if result.get(api_key) is True:
            service[dest] = True

    accessibility = ensure_dict("accessibility")
    if result.get("wheelchair_accessible_entrance") is True:
        accessibility["wheelchair_accessible_entrance"] = True
    elif result.get("wheelchair_accessible_entrance") is False:
        accessibility["wheelchair_accessible_entrance"] = False

    popular = ensure_dict("popular_for")
    meal_map = (
        ("serves_breakfast", "breakfast"),
        ("serves_brunch", "brunch"),
        ("serves_lunch", "lunch"),
        ("serves_dinner", "dinner"),
    )
    for api_key, dest in meal_map:
        if result.get(api_key) is True:
            popular[dest] = True

    dining = ensure_dict("dining_options")
    for api_key, dest in meal_map:
        if result.get(api_key) is True:
            dining[dest] = True

    offerings = ensure_dict("offerings")
    if any(result.get(k) for k in ("serves_breakfast", "serves_lunch", "serves_dinner")):
        offerings["coffee"] = True

    highlights = ensure_dict("highlights")
    if result.get("serves_vegetarian_food") is True:
        highlights["vegetarian_options"] = True
    if result.get("serves_beer") is True or result.get("serves_wine") is True:
        highlights["serves_alcohol"] = True

    meta = ensure_dict("meta")
    meta["source"] = "google_places_api_legacy"
    meta["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    editorial = (result.get("editorial_summary") or {}).get("overview")
    if editorial and not out.get("atmosphere"):
        pass  # keep existing atmosphere from import

    return out


def business_attributes_from_result(result: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "curbside_pickup", "delivery", "dine_in", "takeout", "reservable",
        "serves_breakfast", "serves_brunch", "serves_lunch", "serves_dinner",
        "serves_beer", "serves_wine", "serves_vegetarian_food",
        "wheelchair_accessible_entrance",
    )
    attrs = {}
    for k in keys:
        val = result.get(k)
        if val is not None:
            attrs[k] = val
    return attrs


def fetch_place_metadata_legacy(
    session: requests.Session,
    api_key: str,
    place_id: str,
) -> dict[str, Any]:
    resp = session.get(
        "https://maps.googleapis.com/maps/api/place/details/json",
        params={
            "place_id": place_id,
            "fields": LEGACY_METADATA_FIELDS + ",reviews",
            "reviews_sort": "most_relevant",
            "language": "id",
            "key": api_key,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        return {"_error": True, "message": resp.text[:500]}
    data = resp.json()
    if data.get("status") != "OK":
        return {"_error": True, "message": data.get("error_message") or data.get("status")}
    return data.get("result") or {}


def build_snapshot(result: dict[str, Any]) -> dict[str, Any]:
    pl = result.get("price_level")
    try:
        pl_int = int(pl) if pl is not None else None
    except (TypeError, ValueError):
        pl_int = None
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "aggregates": {
            "rating": result.get("rating"),
            "user_ratings_total": result.get("user_ratings_total"),
        },
        "price_level": pl_int,
        "price_level_label": PRICE_LEVEL_LABELS.get(pl_int) if pl_int is not None else None,
        "business_attributes": business_attributes_from_result(result),
        "reviews": normalize_reviews_legacy(result),
        "formatted_address": result.get("formatted_address"),
        "google_maps_url": result.get("url"),
        "business_status": result.get("business_status"),
    }


def import_facilities_json_to_db(conn, json_path: str | None = None) -> int:
    from facilities_store import FACILITIES_PATH, _flatten_facility_entries

    path = json_path or FACILITIES_PATH
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    index = _flatten_facility_entries(payload)
    if not index:
        return 0
    cur = conn.cursor()
    updated = 0
    for place_id, entry in index.items():
        facilities = entry.get("facilities") or {}
        if not facilities:
            continue
        cur.execute("SELECT 1 FROM coffee_shops WHERE place_id = ?", (place_id,))
        if not cur.fetchone():
            continue
        cur.execute(
            """
            UPDATE coffee_shops
            SET facilities = ?::jsonb,
                updated_at = NOW()
            WHERE place_id = ?
            """,
            (json.dumps(facilities, ensure_ascii=False), place_id),
        )
        if cur.rowcount:
            updated += 1
    conn.commit()
    return updated


def upsert_shop_google_metadata(
    conn,
    place_id: str,
    result: dict[str, Any],
) -> None:
    cur = conn.cursor()
    cur.execute(
        "SELECT facilities FROM coffee_shops WHERE place_id = ?",
        (place_id,),
    )
    row = cur.fetchone()
    existing_fac = {}
    if row:
        existing_fac = _parse_json_col(row[0] if not isinstance(row, dict) else row.get("facilities"))

    facilities = legacy_result_to_facilities(result, existing=existing_fac)
    snapshot = build_snapshot(result)
    rating = result.get("rating")
    total = result.get("user_ratings_total")
    price_level = snapshot.get("price_level")
    now = datetime.now(timezone.utc).isoformat()

    cur.execute(
        """
        UPDATE coffee_shops
        SET rating = ?,
            total_reviews = ?,
            price_level = ?,
            facilities = ?::jsonb,
            google_places_snapshot = ?::jsonb,
            updated_at = ?
        WHERE place_id = ?
        """,
        (
            float(rating) if rating is not None else 0,
            int(total) if total is not None else 0,
            price_level,
            json.dumps(facilities, ensure_ascii=False),
            json.dumps(snapshot, ensure_ascii=False),
            now,
            place_id,
        ),
    )
    conn.commit()


def sync_shop_from_google(
    session: requests.Session,
    api_key: str,
    shop: dict[str, Any],
    *,
    use_text_search: bool = True,
) -> dict[str, Any]:
    db_place_id = str(shop.get("place_id") or "")
    name = str(shop.get("name") or "")
    address = str(shop.get("address") or "")
    google_place_id = db_place_id
    if use_text_search:
        q = build_search_query(name, address)
        hit = legacy_text_search(session, api_key, q)
        if hit and not hit.get("_error"):
            picked, _ = pick_place_candidate(hit, db_place_id)
            if picked:
                google_place_id = picked

    result = fetch_place_metadata_legacy(session, api_key, google_place_id)
    if result.get("_error"):
        return {"success": False, "place_id": db_place_id, "error": result.get("message")}

    from db_backend import get_connection

    conn = get_connection()
    try:
        upsert_shop_google_metadata(conn, db_place_id, result)
    finally:
        conn.close()

    return {
        "success": True,
        "place_id": db_place_id,
        "google_place_id": google_place_id,
        "rating": result.get("rating"),
        "reviews_in_snapshot": len(result.get("reviews") or []),
    }


def sync_all_shops(
    *,
    limit: int | None = None,
    import_json_first: bool = True,
    delay_seconds: float = 0.35,
) -> dict[str, Any]:
    api_key, _ = _resolve_api_key()
    from db_backend import get_connection

    conn = get_connection()
    try:
        ensure_coffee_shop_google_columns(conn)
        imported = import_facilities_json_to_db(conn) if import_json_first else 0
    finally:
        conn.close()

    import time

    session = requests.Session()
    shops = fetch_coffee_shops_from_db(limit=limit)
    results = []
    errors = 0
    for i, shop in enumerate(shops):
        if i > 0 and delay_seconds > 0:
            time.sleep(delay_seconds)
        row = sync_shop_from_google(session, api_key, shop)
        results.append(row)
        if not row.get("success"):
            errors += 1

    return {
        "imported_from_json": imported,
        "shop_count": len(results),
        "error_count": errors,
        "results": results,
    }

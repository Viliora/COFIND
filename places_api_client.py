"""Klien Google Places (Legacy + New) — dipakai fetch & discovery."""

from __future__ import annotations

import os
import re
from typing import Any, Iterator

import requests

PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PLACES_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"
LEGACY_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
LEGACY_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

GOOGLE_PLACE_ID_RE = re.compile(r"^ChI[A-Za-z0-9_-]+$")
MAPS_KEY_ENV_ORDER = (
    "GOOGLE_PLACES_API_KEY",
    "GOOGLE_MAPS_API_KEY",
    "VITE_GOOGLE_MAPS_API_KEY",
)

LEGACY_DETAILS_FIELDS_FULL = (
    "place_id,name,rating,user_ratings_total,reviews,formatted_address,url,"
    "geometry,types,business_status,price_level"
)
LEGACY_DETAILS_FIELDS_SUMMARY = (
    "place_id,name,rating,user_ratings_total,formatted_address,url,"
    "geometry,types,business_status,price_level"
)

PONTIANAK_LOCATION_RESTRICTION = {
    "rectangle": {
        "low": {"latitude": -0.08, "longitude": 109.28},
        "high": {"latitude": 0.02, "longitude": 109.42},
    }
}

NEW_SEARCH_FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,places.location,"
    "places.rating,places.userRatingCount,places.types,places.primaryType,"
    "places.businessStatus"
)


def resolve_api_key() -> tuple[str, str]:
    invalid: list[str] = []
    for env_name in MAPS_KEY_ENV_ORDER:
        key = (os.getenv(env_name) or "").strip()
        if not key or key == "YOUR_API_KEY_HERE":
            continue
        if key.startswith("AIza"):
            return key, env_name
        invalid.append(env_name)
    hint = ""
    if invalid:
        hint = (
            f" ({', '.join(invalid)} ter-set tapi bukan kunci Maps AIza...)"
        )
    raise SystemExit(
        "Tidak ada kunci Maps valid. Set GOOGLE_PLACES_API_KEY=AIza... di .env" + hint
    )


def headers(field_mask: str, api_key: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": field_mask,
    }


def build_search_query(name: str, address: str | None) -> str:
    name = (name or "").strip()
    address = (address or "").strip()
    if not name:
        return ""
    if address:
        short_addr = address.split(",")[0].strip()
        if short_addr and short_addr.lower() not in name.lower():
            return f"{name} {short_addr}"
    return name


def legacy_text_search_first(
    session: requests.Session,
    api_key: str,
    text_query: str,
) -> dict[str, Any] | None:
    page = legacy_text_search_page(session, api_key, text_query)
    if page.get("_error"):
        return page
    results = page.get("results") or []
    if not results:
        return None
    hit = results[0]
    return {
        "place_id": hit.get("place_id"),
        "name": hit.get("name"),
        "formatted_address": hit.get("formatted_address"),
    }


def legacy_text_search_page(
    session: requests.Session,
    api_key: str,
    text_query: str,
    *,
    page_token: str | None = None,
) -> dict[str, Any]:
    if not text_query:
        return {"results": [], "next_page_token": None}
    params: dict[str, Any] = {
        "query": text_query,
        "language": "id",
        "key": api_key,
    }
    if page_token:
        params["pagetoken"] = page_token
    resp = session.get(LEGACY_TEXT_SEARCH_URL, params=params, timeout=30)
    if resp.status_code != 200:
        return {
            "_error": True,
            "status_code": resp.status_code,
            "message": resp.text[:500],
            "results": [],
            "next_page_token": None,
        }
    data = resp.json()
    status = data.get("status")
    if status not in ("OK", "ZERO_RESULTS"):
        return {
            "_error": True,
            "message": data.get("error_message") or status or resp.text[:500],
            "results": [],
            "next_page_token": None,
        }
    return {
        "results": data.get("results") or [],
        "next_page_token": data.get("next_page_token"),
    }


def iter_legacy_text_search(
    session: requests.Session,
    api_key: str,
    text_query: str,
    *,
    max_pages: int = 3,
) -> Iterator[dict[str, Any]]:
    token: str | None = None
    for _ in range(max_pages):
        page = legacy_text_search_page(
            session, api_key, text_query, page_token=token,
        )
        if page.get("_error"):
            return
        for hit in page.get("results") or []:
            yield hit
        token = page.get("next_page_token")
        if not token:
            break


def legacy_place_details(
    session: requests.Session,
    api_key: str,
    google_place_id: str,
    *,
    fields: str = LEGACY_DETAILS_FIELDS_FULL,
    reviews_sort: str = "most_relevant",
) -> dict[str, Any]:
    resp = session.get(
        LEGACY_DETAILS_URL,
        params={
            "place_id": google_place_id,
            "fields": fields,
            "reviews_sort": reviews_sort,
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


def places_text_search_page_new(
    session: requests.Session,
    api_key: str,
    text_query: str,
    *,
    included_type: str | None = None,
    page_token: str | None = None,
    max_result_count: int = 20,
) -> dict[str, Any]:
    if not text_query:
        return {"places": [], "nextPageToken": None}
    body: dict[str, Any] = {
        "textQuery": text_query,
        "languageCode": "id",
        "regionCode": "ID",
        "maxResultCount": max(1, min(20, max_result_count)),
        "locationRestriction": PONTIANAK_LOCATION_RESTRICTION,
    }
    if included_type:
        body["includedType"] = included_type
    if page_token:
        body["pageToken"] = page_token
    resp = session.post(
        PLACES_TEXT_SEARCH_URL,
        headers=headers(NEW_SEARCH_FIELD_MASK, api_key),
        json=body,
        timeout=30,
    )
    if resp.status_code != 200:
        return {
            "_error": True,
            "status_code": resp.status_code,
            "message": resp.text[:500],
            "places": [],
            "nextPageToken": None,
        }
    data = resp.json()
    return {
        "places": data.get("places") or [],
        "nextPageToken": data.get("nextPageToken"),
    }


def iter_places_text_search_new(
    session: requests.Session,
    api_key: str,
    text_query: str,
    *,
    included_type: str | None = None,
    max_pages: int = 3,
) -> Iterator[dict[str, Any]]:
    token: str | None = None
    for _ in range(max_pages):
        page = places_text_search_page_new(
            session,
            api_key,
            text_query,
            included_type=included_type,
            page_token=token,
        )
        if page.get("_error"):
            return
        for place in page.get("places") or []:
            yield place
        token = page.get("nextPageToken")
        if not token:
            break


def places_text_search_new(
    session: requests.Session,
    api_key: str,
    text_query: str,
) -> dict[str, Any] | None:
    page = places_text_search_page_new(session, api_key, text_query)
    if page.get("_error"):
        return page
    places = page.get("places") or []
    if not places:
        return None
    return places[0]


def new_place_to_candidate(place: dict[str, Any]) -> dict[str, Any] | None:
    pid = str(place.get("id") or "").replace("places/", "").strip()
    if not GOOGLE_PLACE_ID_RE.match(pid):
        return None
    display = place.get("displayName") or {}
    name = display.get("text") if isinstance(display, dict) else display
    loc = (place.get("location") or {})
    try:
        lat = float(loc.get("latitude"))
        lng = float(loc.get("longitude"))
    except (TypeError, ValueError):
        lat, lng = None, None
    return {
        "place_id": pid,
        "name": str(name or "").strip(),
        "address": str(place.get("formattedAddress") or ""),
        "latitude": lat,
        "longitude": lng,
        "types": list(place.get("types") or []),
        "primary_type": place.get("primaryType"),
        "rating": place.get("rating"),
        "total_reviews": place.get("userRatingCount"),
        "business_status": place.get("businessStatus"),
        "source": "places_search_text_new",
    }


def pick_place_candidate(
    search_hit: dict[str, Any] | None,
    db_place_id: str,
) -> tuple[str | None, str | None]:
    if search_hit and search_hit.get("_error"):
        return None, "text_search_failed"
    hit_id = (search_hit or {}).get("place_id") or (search_hit or {}).get("id") or ""
    db_place_id = (db_place_id or "").strip()
    if hit_id:
        if db_place_id and GOOGLE_PLACE_ID_RE.match(db_place_id):
            if db_place_id == hit_id:
                return hit_id, None
            return hit_id, "db_place_id_differs_from_search"
        return hit_id, None
    if db_place_id and GOOGLE_PLACE_ID_RE.match(db_place_id):
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
        headers=headers(field_mask, api_key),
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


def geometry_lat_lng(details: dict[str, Any]) -> tuple[float | None, float | None]:
    geom = details.get("geometry") or {}
    loc = geom.get("location") or {}
    lat = loc.get("lat")
    lng = loc.get("lng")
    try:
        return float(lat), float(lng)
    except (TypeError, ValueError):
        return None, None

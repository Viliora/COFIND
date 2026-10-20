"""Serialisasi coffee shop untuk panel admin (selaras skema Postgres/Supabase)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional

from facilities_store import (
    count_enabled_facilities,
    facilities_has_data,
    format_facilities_to_text,
    parse_json_field,
)

# Kolom coffee_shops yang admin boleh baca/tulis (selain id, timestamps).
ADMIN_SHOP_WRITABLE_FIELDS = (
    'name',
    'address',
    'rating',
    'total_reviews',
    'map_embed_url',
    'latitude',
    'longitude',
    'opening_hours_display',
    'phone',
    'website',
    'google_maps_url',
    'price_level',
    'business_status',
)


def _iso_datetime(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _optional_float(value: Any) -> Optional[float]:
    if value is None or value == '':
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> Optional[int]:
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def shop_row_to_admin_list_item(row: Mapping[str, Any], pros_cons: Mapping[str, Any] | None = None) -> dict:
    """Baris coffee_shops → payload daftar admin."""
    rd = dict(row)
    place_id = str(rd.get('place_id') or '')
    facilities_obj = parse_json_field(rd.get('facilities'))
    facility_entry = {
        'place_id': place_id,
        'name': rd.get('name') or '',
        'facilities': facilities_obj,
    }
    snapshot = parse_json_field(rd.get('google_places_snapshot'))
    pc = pros_cons or {}

    return {
        'id': rd.get('id'),
        'place_id': place_id,
        'name': rd.get('name'),
        'address': rd.get('address'),
        'rating': rd.get('rating'),
        'total_reviews': rd.get('total_reviews'),
        'latitude': rd.get('latitude'),
        'longitude': rd.get('longitude'),
        'map_embed_url': rd.get('map_embed_url'),
        'opening_hours_display': rd.get('opening_hours_display') or '',
        'phone': rd.get('phone') or '',
        'website': rd.get('website') or '',
        'google_maps_url': rd.get('google_maps_url') or '',
        'price_level': rd.get('price_level'),
        'business_status': rd.get('business_status') or '',
        'google_places_fetched_at': _iso_datetime(rd.get('google_places_fetched_at')),
        'has_google_snapshot': bool(snapshot),
        'has_facilities': facilities_has_data(facilities_obj),
        'facilities_text': format_facilities_to_text(facility_entry),
        'facility_count': count_enabled_facilities(facilities_obj),
        'pros_cons_pro_count': pc.get('pros_cons_pro_count', 0),
        'pros_cons_con_count': pc.get('pros_cons_con_count', 0),
        'pros_cons_last_generated_at': pc.get('pros_cons_last_generated_at'),
        'pros_cons_has_data': pc.get('pros_cons_has_data', False),
    }


def normalize_shop_write_payload(data: Mapping[str, Any]) -> dict:
    """Normalisasi body create/update shop dari admin UI."""
    out = {
        'name': _optional_str(data.get('name')) or '',
        'address': _optional_str(data.get('address')) or '',
        'rating': _optional_float(data.get('rating')) or 0.0,
        'total_reviews': _optional_int(data.get('total_reviews')) or 0,
        'map_embed_url': _optional_str(data.get('map_embed_url')),
        'latitude': _optional_float(data.get('latitude')),
        'longitude': _optional_float(data.get('longitude')),
        'opening_hours_display': _optional_str(data.get('opening_hours_display')) or '',
        'phone': _optional_str(data.get('phone')),
        'website': _optional_str(data.get('website')),
        'google_maps_url': _optional_str(data.get('google_maps_url')),
        'price_level': _optional_int(data.get('price_level')),
        'business_status': _optional_str(data.get('business_status')),
    }
    return out

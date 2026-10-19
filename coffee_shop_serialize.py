"""Normalisasi baris coffee_shops untuk respons API."""

from __future__ import annotations

import json
from typing import Any, Optional


def _parse_json_field(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def enrich_coffee_shop_row(data: Optional[dict]) -> Optional[dict]:
    if not data:
        return data
    out = dict(data)
    facilities = _parse_json_field(out.get('facilities'))
    snapshot = _parse_json_field(out.get('google_places_snapshot'))
    if facilities is not None:
        out['facilities'] = facilities
    if snapshot is not None:
        out['google_places_snapshot'] = snapshot
    if out.get('total_reviews') is not None and out.get('user_ratings_total') is None:
        out['user_ratings_total'] = out['total_reviews']
    return out

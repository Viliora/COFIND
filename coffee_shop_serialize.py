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


def fetch_catalog_stats(cursor) -> dict[str, Any]:
    """
    Agregat homepage dari DB: jumlah toko, rating Google tersimpan, ulasan Cofind.
    """
    total_shops = int(cursor.execute('SELECT COUNT(*) FROM coffee_shops').fetchone()[0] or 0)
    avg_row = cursor.execute(
        'SELECT AVG(rating) FROM coffee_shops WHERE rating IS NOT NULL AND rating > 0',
    ).fetchone()
    avg_raw = avg_row[0] if avg_row else None
    avg_rating = round(float(avg_raw), 1) if avg_raw is not None else 0.0
    top_rated = int(
        cursor.execute(
            'SELECT COUNT(*) FROM coffee_shops WHERE rating IS NOT NULL AND rating >= 4.5',
        ).fetchone()[0]
        or 0
    )
    total_cofind_reviews = int(
        cursor.execute('SELECT COUNT(*) FROM reviews').fetchone()[0] or 0
    )
    google_reviews_row = cursor.execute(
        'SELECT COALESCE(SUM(COALESCE(total_reviews, 0)), 0) FROM coffee_shops',
    ).fetchone()
    total_google_reviews = int(google_reviews_row[0] if google_reviews_row else 0)
    return {
        'total_shops': total_shops,
        'avg_rating': avg_rating,
        'top_rated': top_rated,
        'total_cofind_reviews': total_cofind_reviews,
        'total_google_reviews': total_google_reviews,
    }


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

"""Akses data fasilitas coffee shop dari database (coffee_shops.facilities)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict

from db_backend import get_connection, use_postgres
from logging_config import get_logger

logger = get_logger('facilities')

_REPO_ROOT = __import__('os').path.dirname(__import__('os').path.abspath(__file__))
# Opsional: impor one-off lewat google_places_sync (file tidak wajib ada).
FACILITIES_PATH = __import__('os').path.join(_REPO_ROOT, 'data', 'facilities.json')


def _parse_json(value: Any) -> dict:
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


def _flatten_facility_entries(payload: Any) -> Dict[str, dict]:
    """Kumpulkan entry dari JSON file (impor one-off)."""
    collected: Dict[str, dict] = {}

    def _accept(place_id: str, name: str, facilities: dict) -> None:
        pid = (place_id or '').strip()
        if not pid or not isinstance(facilities, dict):
            return
        collected[pid] = {
            'place_id': pid,
            'name': name or collected.get(pid, {}).get('name', ''),
            'facilities': facilities,
        }

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            pid = obj.get('place_id')
            facilities = obj.get('facilities')
            if isinstance(pid, str) and isinstance(facilities, dict):
                _accept(pid, obj.get('name') or '', facilities)
            for key, value in obj.items():
                if isinstance(key, str) and key.startswith('ChIJ') and isinstance(value, dict):
                    nested_fac = value.get('facilities')
                    if isinstance(nested_fac, dict):
                        _accept(str(value.get('place_id') or key), value.get('name') or '', nested_fac)
                walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(payload)
    return collected


def load_facilities_index() -> Dict[str, dict]:
    if not use_postgres():
        logger.warning('load_facilities_index membutuhkan Postgres/Supabase')
        return {}
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT place_id, name, facilities
            FROM coffee_shops
            WHERE facilities IS NOT NULL
              AND facilities::text NOT IN ('{}', 'null')
            """
        )
        rows = cur.fetchall()
        conn.close()
    except Exception as err:
        logger.warning(f"Gagal memuat facilities dari DB: {err}")
        return {}

    index: Dict[str, dict] = {}
    for row in rows:
        if isinstance(row, dict):
            pid = row.get('place_id')
            name = row.get('name') or ''
            facilities = _parse_json(row.get('facilities'))
        else:
            pid, name, facilities_raw = row[0], row[1], row[2]
            facilities = _parse_json(facilities_raw)
        if not pid:
            continue
        index[str(pid)] = {
            'place_id': str(pid),
            'name': name or '',
            'facilities': facilities,
        }
    return index


def save_facilities_entry(place_id: str, entry: dict) -> None:
    pid = (place_id or '').strip()
    if not pid:
        raise ValueError('place_id required')
    facilities = entry.get('facilities')
    if not isinstance(facilities, dict):
        raise ValueError('facilities harus object')

    meta = facilities.setdefault('meta', {})
    if not isinstance(meta, dict):
        facilities['meta'] = {}
        meta = facilities['meta']
    meta['last_updated'] = datetime.utcnow().strftime('%Y-%m-%d')
    meta.setdefault('source', 'admin_editor')

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE coffee_shops
        SET facilities = ?::jsonb,
            updated_at = ?
        WHERE place_id = ?
        """,
        (
            json.dumps(facilities, ensure_ascii=False),
            datetime.utcnow().isoformat(),
            pid,
        ),
    )
    conn.commit()
    conn.close()


def save_facilities_index(facilities_index: Dict[str, dict]) -> None:
    for place_id, entry in (facilities_index or {}).items():
        save_facilities_entry(place_id, entry)


def default_facilities_entry(place_id: str, shop_name: str = '') -> dict:
    return {
        'place_id': place_id,
        'name': shop_name or '',
        'facilities': {
            'service_options': {},
            'accessibility': {},
            'highlights': {},
            'popular_for': {},
            'atmosphere': [],
            'crowd': [],
            'dining_options': {},
            'offerings': {},
            'amenities': {},
            'planning': {},
            'parking': {},
            'payments': {},
            'meta': {
                'source': 'admin_editor',
                'last_updated': datetime.utcnow().strftime('%Y-%m-%d'),
            },
        },
    }


def count_enabled_facilities(facilities_obj) -> int:
    if not facilities_obj:
        return 0
    count = 0
    for value in facilities_obj.values():
        if isinstance(value, dict):
            count += sum(1 for item in value.values() if item is True)
        elif isinstance(value, list):
            count += len(value)
    return count


def format_facilities_to_text(shop_facilities) -> str:
    """Ubah data facilities JSON menjadi teks deskriptif terstruktur."""
    facilities = (shop_facilities or {}).get('facilities', shop_facilities or {})
    if not facilities:
        return ''

    parts = []

    highlights = facilities.get('highlights', {})
    active_highlights = [k.replace('_', ' ') for k, v in highlights.items() if v]
    if active_highlights:
        parts.append(f"Memiliki keunggulan: {', '.join(active_highlights)}.")

    popular = facilities.get('popular_for', {})
    active_popular = [k.replace('_', ' ') for k, v in popular.items() if v]
    if active_popular:
        parts.append(f"Populer untuk: {', '.join(active_popular)}.")

    atmosphere = facilities.get('atmosphere', [])
    if atmosphere:
        parts.append(f"Suasana: {', '.join(atmosphere)}.")

    amenities = facilities.get('amenities', {})
    active_amenities = [k.replace('_', ' ') for k, v in amenities.items() if v]
    if active_amenities:
        parts.append(f"Fasilitas tersedia: {', '.join(active_amenities)}.")

    service = facilities.get('service_options', {})
    active_service = [k.replace('_', ' ') for k, v in service.items() if v]
    if active_service:
        parts.append(f"Opsi layanan: {', '.join(active_service)}.")

    return ' '.join(parts)

"""Akses data fasilitas coffee shop (facilities.json) dan format teksnya.

Sumber data sama dengan yang dipakai frontend (FacilitiesTab), sehingga deskripsi
fasilitas pada pipeline rekomendasi konsisten dengan yang dilihat user.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict

from logging_config import get_logger

logger = get_logger('facilities')

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
FACILITIES_PATH = os.path.join(_REPO_ROOT, 'frontend-cofind', 'src', 'data', 'facilities.json')


def _flatten_facility_entries(payload: Any) -> Dict[str, dict]:
    """Kumpulkan semua entry facilities meski JSON sempat tertutup/tersarang salah."""
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
    if not os.path.exists(FACILITIES_PATH):
        logger.warning(f"facilities.json tidak ditemukan: {FACILITIES_PATH}")
        return {}
    try:
        with open(FACILITIES_PATH, 'r', encoding='utf-8') as handle:
            payload = json.load(handle)
    except Exception as err:
        logger.warning(f"Gagal memuat facilities.json: {err}")
        return {}
    return _flatten_facility_entries(payload)


def save_facilities_index(facilities_index: Dict[str, dict]) -> None:
    with open(FACILITIES_PATH, 'w', encoding='utf-8', newline='\n') as handle:
        json.dump({'facilities_by_place_id': facilities_index}, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


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
    facilities = (shop_facilities or {}).get('facilities', {})
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

    return ' '.join(parts)

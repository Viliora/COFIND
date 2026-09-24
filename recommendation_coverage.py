"""
Sinyal coverage pill di luar kutipan modal (keyword hits, metadata, jam buka).
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Sequence, Set, Tuple

# Jam operasional dari DB / admin
_HOURS_24_RE = re.compile(
    r'24\s*[/]?\s*7|24\s*jam|24\s*hours|buka\s*24|open\s*24|never\s*close|non[\s-]?stop|sepanjang\s*hari',
    re.IGNORECASE,
)


def hours_indicate_24_7(hours_display: str) -> bool:
    return bool(_HOURS_24_RE.search(str(hours_display or '').strip()))


def shop_hours_display(shop: dict) -> str:
    profile = shop.get('profile') if isinstance(shop.get('profile'), dict) else {}
    evidence = shop.get('evidence') if isinstance(shop.get('evidence'), dict) else {}
    return str(
        profile.get('opening_hours_display')
        or evidence.get('opening_hours_display')
        or shop.get('opening_hours_display')
        or ''
    ).strip()


def pills_with_review_keyword_hits(shop: dict, pills: Sequence[str]) -> Set[str]:
    pill_set = set(pills or [])
    out: Set[str] = set()
    detail = shop.get('score_detail') or {}
    per_pill = detail.get('per_pill_stats') or {}
    for pill in pill_set:
        stats = per_pill.get(pill)
        if isinstance(stats, dict) and (stats.get('keyword_review_hits') or 0) > 0:
            out.add(pill)
    evidence = shop.get('evidence') or {}
    for stat in evidence.get('pill_stats') or []:
        if not isinstance(stat, dict):
            continue
        pill = stat.get('pill')
        if pill in pill_set and (stat.get('keyword_review_hits') or 0) > 0:
            out.add(str(pill))
    return out


def pills_covered_by_metadata(
    shop: dict,
    pills: Sequence[str],
    *,
    facility_attribute_pills: Iterable[str],
) -> Set[str]:
    facility_set = set(facility_attribute_pills or [])
    pill_set = set(pills or [])
    evidence = shop.get('evidence') or {}
    gate = evidence.get('metadata_gate') or {}
    matched = [
        str(p) for p in (gate.get('matched_attribute_pills') or [])
        if p
    ]
    contradicted = {str(p) for p in (gate.get('contradicted_pills') or []) if p}
    out: Set[str] = set()
    for pill in matched:
        if pill in pill_set and pill in facility_set and pill not in contradicted:
            out.add(pill)
    return out


def pills_covered_by_opening_hours(shop: dict, pills: Sequence[str]) -> Set[str]:
    if 'buka_sampai_malam_24_hours' not in (pills or []):
        return set()
    if hours_indicate_24_7(shop_hours_display(shop)):
        return {'buka_sampai_malam_24_hours'}
    return set()


def merge_pill_coverage(
    shop: dict,
    pills: Sequence[str],
    covered: Sequence[str],
    uncovered: Sequence[str],
    *,
    facility_attribute_pills: Iterable[str],
) -> Tuple[List[str], List[str]]:
    """Gabung bukti kutipan dengan keyword hits, metadata, dan jam buka."""
    extra = set()
    extra |= pills_with_review_keyword_hits(shop, pills)
    extra |= pills_covered_by_metadata(
        shop, pills, facility_attribute_pills=facility_attribute_pills,
    )
    extra |= pills_covered_by_opening_hours(shop, pills)
    covered_set = set(covered or []) | extra
    pills_list = list(pills or [])
    covered_out = [p for p in pills_list if p in covered_set]
    uncovered_out = [p for p in pills_list if p not in covered_set]
    return covered_out, uncovered_out


def supplemental_coverage_lines(shop: dict, pills: Sequence[str]) -> List[str]:
    """Baris tambahan untuk prompt LLM (profil/jam buka)."""
    lines: List[str] = []
    hours = shop_hours_display(shop)
    if hours and 'buka_sampai_malam_24_hours' in (pills or []):
        tag = ' (mendukung pill 24 jam)' if hours_indicate_24_7(hours) else ''
        lines.append(f'  - Jam operasional toko (database): {hours}{tag}')
    gate = (shop.get('evidence') or {}).get('metadata_gate') or {}
    labels = [str(x) for x in (gate.get('matched_attribute_labels') or []) if x]
    if labels:
        lines.append(
            '  - Profil fasilitas resmi selaras pill user (klaim pendukung): '
            + ', '.join(labels)
        )
    return lines

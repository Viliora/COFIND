"""Normalisasi body request rekomendasi (pill vs free text)."""

from __future__ import annotations

from flask import request

from free_text_intent import normalize_free_text_query
from pill_config import FACILITY_ATTRIBUTE_PILLS

_MAX_ACTIVITY_PILLS = 1
_MAX_ATTRIBUTE_PILLS = 3


def _as_pill_list(value):
    if not isinstance(value, list):
        value = [value] if value else []
    out = []
    for item in value:
        pill = str(item).strip().lower()
        if pill and pill not in out:
            out.append(pill)
    return out


def read_recommendation_preferences():
    data = request.get_json(silent=True) or {}
    raw_prefs = _as_pill_list(data.get('preferences'))
    raw_attrs = _as_pill_list(data.get('attributes'))
    raw_query_text = normalize_free_text_query(data.get('query_text'))

    activities = [p for p in raw_prefs if p not in FACILITY_ATTRIBUTE_PILLS][:_MAX_ACTIVITY_PILLS]
    attributes = []
    for pill in raw_prefs + raw_attrs:
        if pill in FACILITY_ATTRIBUTE_PILLS and pill not in attributes:
            attributes.append(pill)
    pills = activities + attributes[:_MAX_ATTRIBUTE_PILLS]
    return pills, raw_query_text

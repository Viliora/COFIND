"""Sinkron batas pill request dengan konstanta backend (dan frontend MAX_FACILITY_ATTRIBUTES=3)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from recommendation.request_prefs import (
    _MAX_ACTIVITY_PILLS,
    _MAX_ATTRIBUTE_PILLS,
    read_recommendation_preferences,
)


ROOT = Path(__file__).resolve().parents[1]
FACILITY_PICKER = ROOT / "frontend-cofind" / "src" / "components" / "FacilityAttributePicker.jsx"


class PrefPillLimitTests(unittest.TestCase):
    def test_backend_attribute_cap(self):
        self.assertEqual(_MAX_ATTRIBUTE_PILLS, 3)
        self.assertEqual(_MAX_ACTIVITY_PILLS, 1)

    def test_frontend_max_facility_attributes_matches_backend(self):
        text = FACILITY_PICKER.read_text(encoding="utf-8")
        m = re.search(r"MAX_FACILITY_ATTRIBUTES\s*=\s*(\d+)", text)
        self.assertIsNotNone(m, "MAX_FACILITY_ATTRIBUTES tidak ditemukan di FacilityAttributePicker.jsx")
        self.assertEqual(int(m.group(1)), _MAX_ATTRIBUTE_PILLS)

    def test_read_prefs_truncates_activity_and_attributes(self):
        from flask import Flask

        app = Flask(__name__)
        payload = {
            "preferences": ["kerja", "belajar", "wifi_kencang"],
            "attributes": ["musholla", "ruangan_ac", "parkir_luas", "banyak_colokan_terminal"],
        }
        with app.test_request_context(json=payload):
            pills, query = read_recommendation_preferences()
        self.assertEqual(query, "")
        activities = [p for p in pills if p in ("kerja", "belajar")]
        self.assertLessEqual(len(activities), _MAX_ACTIVITY_PILLS)
        self.assertLessEqual(len(pills), _MAX_ACTIVITY_PILLS + _MAX_ATTRIBUTE_PILLS)


if __name__ == "__main__":
    unittest.main()

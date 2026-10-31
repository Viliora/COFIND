"""Unit test heuristik pemilihan kafe Pontianak."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLACES = ROOT / "scripts" / "places"
sys.path.insert(0, str(PLACES))

from pontianak_selection import (  # noqa: E402
    brand_key,
    select_candidates,
    tier_hidden_gem,
)


class PontianakSelectionTests(unittest.TestCase):
    EXISTING = {"ChIJexisting123456789012345678901"}

    def test_tier_hidden_gem(self):
        self.assertTrue(tier_hidden_gem({"rating": 5.0, "total_reviews": 80}))
        self.assertFalse(tier_hidden_gem({"rating": 4.8, "total_reviews": 80}))
        self.assertFalse(tier_hidden_gem({"rating": 5.0, "total_reviews": 30}))

    def test_brand_key_aming(self):
        self.assertEqual(brand_key("Aming Coffee Podomoro"), "aming coffee")

    def test_dedupe_existing_and_brand_cap(self):
        candidates = [
            {
                "place_id": "ChIJaaaaaaaaaaaaaaaaaaaaaaa01",
                "name": "Aming Coffee Alpha",
                "address": "Pontianak",
                "latitude": -0.03,
                "longitude": 109.33,
                "types": ["cafe"],
                "rating": 4.95,
                "total_reviews": 60,
                "business_status": "OPERATIONAL",
            },
            {
                "place_id": "ChIJaaaaaaaaaaaaaaaaaaaaaaa02",
                "name": "Aming Coffee Beta",
                "address": "Pontianak",
                "latitude": -0.03,
                "longitude": 109.33,
                "types": ["cafe"],
                "rating": 4.95,
                "total_reviews": 55,
                "business_status": "OPERATIONAL",
            },
            {
                "place_id": "ChIJaaaaaaaaaaaaaaaaaaaaaaa03",
                "name": "Aming Coffee Gamma",
                "address": "Pontianak",
                "latitude": -0.03,
                "longitude": 109.33,
                "types": ["cafe"],
                "rating": 4.95,
                "total_reviews": 70,
                "business_status": "OPERATIONAL",
            },
            {
                "place_id": "ChIJexisting123456789012345678901",
                "name": "Existing Shop",
                "address": "Pontianak",
                "latitude": -0.03,
                "longitude": 109.33,
                "types": ["cafe"],
                "rating": 5.0,
                "total_reviews": 10,
                "business_status": "OPERATIONAL",
            },
        ]
        selected, _, summary = select_candidates(
            candidates,
            existing_place_ids=self.EXISTING,
            target=2,
            max_per_brand=2,
            quotas=(2, 0, 0),
        )
        ids = {s["place_id"] for s in selected}
        self.assertNotIn("ChIJexisting123456789012345678901", ids)
        self.assertLessEqual(len(selected), 2)
        aming = [s for s in selected if "aming" in s["name"].lower()]
        self.assertLessEqual(len(aming), 2)
        self.assertGreaterEqual(summary["by_tier"].get("hidden_gem", 0), 1)


if __name__ == "__main__":
    unittest.main()

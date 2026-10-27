"""Lexical match untuk pill dessert (regresi ulasan cheesecake)."""

from __future__ import annotations

import unittest

from pill_aspect_sentiment import expand_pill_keywords
from pill_config import PILL_MAPPING
from review_weakness import text_matches_any_keyword


CHEESECAKE_REVIEW = (
    "Beli cheesecake nya untuk di bungkus, enakkkk Suka banget ngga terlalu manis kejunya berasa banget"
)


class DessertPillKeywordTests(unittest.TestCase):
    def test_cheesecake_review_matches_dessert_keywords(self):
        keywords = expand_pill_keywords("dessert", PILL_MAPPING)
        self.assertTrue(text_matches_any_keyword(CHEESECAKE_REVIEW, keywords))

    def test_dessert_is_facility_attribute(self):
        from pill_config import FACILITY_ATTRIBUTE_PILLS

        self.assertIn("dessert", FACILITY_ATTRIBUTE_PILLS)


if __name__ == "__main__":
    unittest.main()

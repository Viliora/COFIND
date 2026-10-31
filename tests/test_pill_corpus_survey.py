"""Unit test survei pill — tanpa DB."""

from __future__ import annotations

import unittest

from scripts.eval.pill_corpus_survey import (
    build_activity_matchers,
    match_activity_review,
    survey_all_reviews,
)


class PillCorpusSurveyTests(unittest.TestCase):
    def test_kerja_wfc_detected(self):
        matchers = build_activity_matchers()
        hit = match_activity_review(
            "Tempatnya enak buat wfc, laptopan berjam-jam wifi oke.",
            "kerja",
            matchers["kerja"],
        )
        self.assertIsNotNone(hit)
        self.assertGreaterEqual(hit["score"], 0.6)

    def test_nongkrong_hangout_detected(self):
        matchers = build_activity_matchers()
        hit = match_activity_review(
            "Tempat favorit nongkrong bareng teman, nongki lama sambil ngobrol.",
            "nongkrong_hangout",
            matchers["nongkrong_hangout"],
        )
        self.assertIsNotNone(hit)

    def test_survey_counts_one_review_two_pills(self):
        rows = [
            (
                1,
                "ChIJ_test",
                "Cocok nugas dan wfc, suasananya tenang buat belajar.",
                "google_places",
            ),
        ]
        report = survey_all_reviews(rows, max_samples=3)
        self.assertEqual(report["corpus"]["reviews_usable_min_chars"], 1)
        kerja = report["per_pill"]["kerja"]["reviews_mentioning"]
        belajar = report["per_pill"]["belajar"]["reviews_mentioning"]
        self.assertGreaterEqual(kerja, 1)
        self.assertGreaterEqual(belajar, 1)


if __name__ == "__main__":
    unittest.main()

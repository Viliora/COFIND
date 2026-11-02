"""BM25 per-ulasan + agregasi ke toko."""

from __future__ import annotations

import unittest

from bm25_utils import (
    aggregate_review_bm25_scores,
    score_shops_bm25,
    score_shops_bm25_review_level,
)
from hybrid_retrieval import tokenize_for_match


def _profile(pid: str, review_texts: list[str]) -> dict:
    return {
        "place_id": pid,
        "reviews": [{"text": t} for t in review_texts],
    }


class TestBm25ReviewLevel(unittest.TestCase):
    def test_review_max_uses_best_passage_not_merged_doc(self):
        profiles = [
            _profile("shop-a", ["banyak teks netral " * 30, "wfc laptop buat nugas tenang"]),
            _profile("shop-b", ["banyak teks netral " * 30]),
        ]
        query = ["wfc", "laptop", "nugas"]
        review_scores, meta = score_shops_bm25_review_level(
            profiles, query, tokenize_for_match, aggregate="max",
        )
        self.assertEqual(meta.get("unit"), "review")
        self.assertGreater(review_scores["shop-a"], review_scores["shop-b"])

    def test_aggregate_sum_top_n(self):
        doc_pids = ["a", "a", "b"]
        raw = [1.0, 0.5, 0.2]
        out_max = aggregate_review_bm25_scores(doc_pids, raw, mode="max")
        out_sum = aggregate_review_bm25_scores(
            doc_pids, raw, mode="sum_top", top_n=2,
        )
        self.assertAlmostEqual(out_max["a"], 1.0)
        self.assertAlmostEqual(out_sum["a"], 1.5)


if __name__ == "__main__":
    unittest.main()

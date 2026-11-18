"""Unit test ranking lane dense/bm25 (tanpa DB)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_EVAL = ROOT / "scripts" / "eval"
if str(_EVAL) not in sys.path:
    sys.path.insert(0, str(_EVAL))

from relevance_metrics import rank_place_ids_by_score, recall_at_k  # noqa: E402


class TestRetrievalLaneRank(unittest.TestCase):
    def test_rank_place_ids_by_score_orders_desc(self):
        scores = {"b": 0.2, "a": 0.9, "c": 0.5}
        self.assertEqual(rank_place_ids_by_score(scores, 2), ["a", "c"])

    def test_recall_at_k_with_dense_ranking(self):
        rel = {"a": 2.0, "b": 1.0, "z": 3.0}
        ranked = rank_place_ids_by_score({"a": 0.8, "b": 0.1, "z": 0.5, "x": 0.9}, 3)
        # top3: x, a, z — relevan a,z hit 2/3
        self.assertAlmostEqual(recall_at_k(ranked, rel, 3), 2 / 3)


if __name__ == "__main__":
    unittest.main()

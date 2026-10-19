"""Jaring pengaman Fase 2: RRF, rrf_norm, activity gate — offline, tanpa DB/LLM."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("COFIND_SEMANTIC_GATE", "false")
os.environ["COFIND_RRF_K"] = "60"
os.environ["COFIND_RRF_POOL_SIZE"] = "50"

from hybrid_retrieval import (  # noqa: E402
    _hybrid_retrieve_rrf_core,
    _rrf_ranked_place_ids,
    activity_signal_tokens,
    compile_activity_matcher,
    empty_activity_matcher,
    reciprocal_rank_fusion,
    retrieve_top_k,
    retrieve_top_k_by_text,
    shop_has_activity_signal,
)

GOLDEN_PATH = Path(__file__).resolve().parent / "golden_queries.json"

MINI_PILL_LABELS = {
    "kerja": "Kerja/WFC",
    "bermain game": "Nge-game",
    "wifi_kencang": "Wifi kencang",
    "parkir_luas": "Parkir luas",
    "musholla": "Ada musholla",
}

MINI_PILL_MAPPING = {
    "kerja": {
        "definition": "Work from cafe dengan laptop.",
        "review_keywords": ["kerja", "wfc", "laptop", "ngoding"],
        "facility_fields": {
            "popular_for": ["good_for_working_on_laptop"],
            "amenities": ["wifi"],
        },
    },
    "bermain game": {
        "definition": "Mabar mobile legends dan game online.",
        "review_keywords": [
            "main game",
            "mabar",
            "mobile legends",
            "main ml",
            "nge-game",
        ],
        "facility_fields": {"popular_for": ["good_for_groups"]},
    },
    "wifi_kencang": {
        "review_keywords": ["wifi kencang", "internet stabil"],
        "facility_fields": {"amenities": ["wifi"]},
    },
    "parkir_luas": {
        "review_keywords": ["parkir luas", "parkir mudah"],
        "facility_fields": {"parking": ["lots_of_parking"]},
    },
    "musholla": {
        "review_keywords": ["musholla", "tempat sholat"],
        "facility_fields": {"amenities": ["musholla"]},
    },
}


def make_profile(place_id: str, name: str, review_texts: list[str]) -> dict:
    return {
        "place_id": place_id,
        "name": name,
        "reviews": [{"text": t, "rating": 5} for t in review_texts],
    }


def blend_total_score(rrf_score: float, max_rrf: float, quality=None) -> float:
    """Mirror hybrid_retrieval.py:1163-1186."""
    rrf_norm = (rrf_score / max_rrf) if max_rrf > 0 else 0.0
    if quality is None:
        return rrf_norm
    return 0.9 * rrf_norm + 0.1 * float(quality)


def _patch_bm25_dense(bm25_scores: dict, dense_scores: dict):
    place_ids = list({*bm25_scores.keys(), *dense_scores.keys()})

    def fake_build(profiles, tokenize_fn=None):
        return (place_ids, None, None)

    return (
        patch("hybrid_retrieval.build_bm25_index", side_effect=fake_build),
        patch("hybrid_retrieval.score_shops_bm25", return_value=bm25_scores),
        patch(
            "hybrid_retrieval.score_shops_dense",
            return_value=(dense_scores, {"pool": "mock", "store": "test"}),
        ),
    )


class TestReciprocalRankFusion(unittest.TestCase):
    def test_single_list_rank_one_score(self):
        fused = reciprocal_rank_fusion([["shop-a"]], k=60)
        self.assertAlmostEqual(fused["shop-a"], 1.0 / 61.0)

    def test_dual_list_overlap_orders_by_score(self):
        bm25_ranked = ["shop-a", "shop-b", "shop-c"]
        dense_ranked = ["shop-b", "shop-d", "shop-a"]
        fused = reciprocal_rank_fusion([bm25_ranked, dense_ranked], k=60)

        self.assertEqual(
            list(fused.keys()),
            sorted(fused, key=fused.get, reverse=True),
        )
        self.assertGreater(fused["shop-b"], fused["shop-a"])
        self.assertGreater(fused["shop-b"], fused["shop-c"])
        self.assertGreater(fused["shop-b"], fused["shop-d"])
        self.assertGreater(fused["shop-a"], fused["shop-c"])
        self.assertGreater(fused["shop-a"], fused["shop-d"])

    def test_empty_doc_id_skipped(self):
        fused = reciprocal_rank_fusion([["shop-a", "", "  "]], k=60)
        self.assertEqual(list(fused.keys()), ["shop-a"])

    def test_smaller_k_increases_top_rank_contribution(self):
        top_k1 = reciprocal_rank_fusion([["shop-a"]], k=1)["shop-a"]
        top_k60 = reciprocal_rank_fusion([["shop-a"]], k=60)["shop-a"]
        self.assertGreater(top_k1, top_k60)


class TestRrfRankedPlaceIds(unittest.TestCase):
    def test_filters_near_zero_scores(self):
        profiles = {"a": {}, "b": {}}
        raw = {"a": 1.0, "b": 1e-12}
        ranked = _rrf_ranked_place_ids(raw, profiles, pool_size=10)
        self.assertEqual(ranked, ["a"])

    def test_respects_pool_size(self):
        profiles = {f"p{i}": {} for i in range(5)}
        raw = {f"p{i}": float(5 - i) for i in range(5)}
        ranked = _rrf_ranked_place_ids(raw, profiles, pool_size=2)
        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked[0], "p0")


class TestRrfNormAndQualityBlend(unittest.TestCase):
    def test_rrf_norm_divides_by_max(self):
        scores = {"a": 0.02, "b": 0.04}
        max_rrf = max(scores.values())
        self.assertAlmostEqual(blend_total_score(0.02, max_rrf), 0.5)
        self.assertAlmostEqual(blend_total_score(0.04, max_rrf), 1.0)

    def test_zero_max_rrf_yields_zero_norm(self):
        self.assertAlmostEqual(blend_total_score(0.0, 0.0), 0.0)

    def test_quality_none_uses_rrf_norm_only(self):
        self.assertAlmostEqual(blend_total_score(0.03, 0.06, quality=None), 0.5)
        self.assertAlmostEqual(blend_total_score(0.03, 0.06, quality=0.8), 0.9 * 0.5 + 0.1 * 0.8)


class TestHybridRetrieveRrfCoreMocked(unittest.TestCase):
    def _run_core(
        self,
        profiles,
        *,
        apply_activity_gate=False,
        activity_pills=None,
        bm25_tokens=None,
    ):
        activity_pills = list(activity_pills or [])
        matcher = (
            compile_activity_matcher(
                activity_pills,
                pill_labels=MINI_PILL_LABELS,
                pill_mapping=MINI_PILL_MAPPING,
            )
            if activity_pills
            else empty_activity_matcher()
        )
        act_tokens = list(matcher.get("bm25_tokens") or [])
        telemetry: dict = {}
        return _hybrid_retrieve_rrf_core(
            profiles,
            bm25_tokens=bm25_tokens or ["kerja"],
            dense_query_text="kerja laptop wifi",
            quality_by_place={"shop-a": 0.8, "shop-b": 0.2},
            top_k=5,
            query_tokens_out=["kerja"],
            query_text_out="kerja",
            activity_tokens_out=act_tokens,
            attribute_tokens_out=[],
            activity_query_text_out="kerja laptop",
            activity_matcher_out=matcher,
            telemetry=telemetry,
            apply_activity_gate=apply_activity_gate,
            activity_pills=activity_pills,
            activity_tokens_for_gate=act_tokens,
            activity_phrase_list=list(matcher.get("phrases") or []),
            activity_matcher=matcher if activity_pills else None,
        ), telemetry

    @patch("hybrid_retrieval.score_shops_dense")
    @patch("hybrid_retrieval.score_shops_bm25")
    @patch("hybrid_retrieval.build_bm25_index")
    def test_score_detail_rrf_norm_in_unit_interval(
        self, mock_bm25_index, mock_bm25_score, mock_dense
    ):
        mock_bm25_index.return_value = (["shop-a", "shop-b"], None, None)
        mock_bm25_score.return_value = {"shop-a": 2.0, "shop-b": 1.0}
        mock_dense.return_value = (
            {"shop-a": 0.9, "shop-b": 0.95},
            {"pool": "mock"},
        )
        profiles = [
            make_profile("shop-a", "A", ["wifi bagus buat kerja laptop"]),
            make_profile("shop-b", "B", ["suasana tenang"]),
        ]
        result, _ = self._run_core(profiles, apply_activity_gate=False)
        for item in result["candidates"]:
            detail = item["score_detail"]
            self.assertGreater(detail["rrf_score"], 0)
            self.assertGreaterEqual(detail["rrf_norm"], 0.0)
            self.assertLessEqual(detail["rrf_norm"], 1.0)

    @patch("hybrid_retrieval.score_shops_dense")
    @patch("hybrid_retrieval.score_shops_bm25")
    @patch("hybrid_retrieval.build_bm25_index")
    def test_activity_gate_drops_shop_without_signal(
        self, mock_bm25_index, mock_bm25_score, mock_dense
    ):
        mock_bm25_index.return_value = (["shop-a", "shop-b"], None, None)
        mock_bm25_score.return_value = {"shop-a": 1.0, "shop-b": 3.0}
        mock_dense.return_value = (
            {"shop-a": 0.5, "shop-b": 0.99},
            {"pool": "mock"},
        )
        profiles = [
            make_profile("shop-a", "With signal", ["tempat favorit buat WFC dan laptop"]),
            make_profile("shop-b", "No signal", ["kopi enak tapi mahal"]),
        ]
        result, telemetry = self._run_core(
            profiles,
            apply_activity_gate=True,
            activity_pills=["kerja"],
        )
        ids = {c["place_id"] for c in result["candidates"]}
        self.assertIn("shop-a", ids)
        self.assertNotIn("shop-b", ids)
        self.assertGreaterEqual(int(telemetry.get("activity_rejected") or 0), 1)

    @patch("hybrid_retrieval.score_shops_dense")
    @patch("hybrid_retrieval.score_shops_bm25")
    @patch("hybrid_retrieval.build_bm25_index")
    def test_activity_pass_dense_only_telemetry_without_admission(
        self, mock_bm25_index, mock_bm25_score, mock_dense
    ):
        mock_bm25_index.return_value = (["shop-b"], None, None)
        mock_bm25_score.return_value = {"shop-b": 2.0}
        mock_dense.return_value = ({"shop-b": 0.99}, {"pool": "mock"})
        profiles = [make_profile("shop-b", "Dense only", ["kopi enak saja"])]
        result, telemetry = self._run_core(
            profiles,
            apply_activity_gate=True,
            activity_pills=["kerja"],
        )
        self.assertEqual(result["candidates"], [])
        self.assertGreaterEqual(int(telemetry.get("activity_pass_dense_only") or 0), 1)
        self.assertEqual(int(telemetry.get("activity_pass_lexical") or 0), 0)

    @patch("hybrid_retrieval.score_shops_dense")
    @patch("hybrid_retrieval.score_shops_bm25")
    @patch("hybrid_retrieval.build_bm25_index")
    def test_free_text_path_allows_shop_without_activity_signal(
        self, mock_bm25_index, mock_bm25_score, mock_dense
    ):
        mock_bm25_index.return_value = (["shop-b"], None, None)
        mock_bm25_score.return_value = {"shop-b": 2.0}
        mock_dense.return_value = ({"shop-b": 0.8}, {"pool": "mock"})
        profiles = [make_profile("shop-b", "No activity", ["kopi enak"])]
        result = retrieve_top_k_by_text(
            profiles,
            query_tokens=["kopi"],
            dense_query_text="kopi enak",
            top_k=3,
        )
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["candidates"][0]["place_id"], "shop-b")

    @patch("hybrid_retrieval.score_shops_dense")
    @patch("hybrid_retrieval.score_shops_bm25")
    @patch("hybrid_retrieval.build_bm25_index")
    def test_candidates_sorted_by_descending_score(
        self, mock_bm25_index, mock_bm25_score, mock_dense
    ):
        mock_bm25_index.return_value = (["shop-a", "shop-b", "shop-c"], None, None)
        mock_bm25_score.return_value = {
            "shop-a": 1.0,
            "shop-b": 3.0,
            "shop-c": 2.0,
        }
        mock_dense.return_value = (
            {"shop-a": 0.2, "shop-b": 0.3, "shop-c": 0.9},
            {"pool": "mock"},
        )
        profiles = [
            make_profile("shop-a", "A", ["kerja"]),
            make_profile("shop-b", "B", ["kerja"]),
            make_profile("shop-c", "C", ["kerja"]),
        ]
        result, _ = self._run_core(profiles, apply_activity_gate=False)
        scores = [c["score"] for c in result["candidates"]]
        self.assertEqual(scores, sorted(scores, reverse=True))


class TestActivityGate(unittest.TestCase):
    def setUp(self):
        self.game_matcher = compile_activity_matcher(
            ["bermain game"],
            pill_labels=MINI_PILL_LABELS,
            pill_mapping=MINI_PILL_MAPPING,
        )
        self.kerja_matcher = compile_activity_matcher(
            ["kerja"],
            pill_labels=MINI_PILL_LABELS,
            pill_mapping=MINI_PILL_MAPPING,
        )

    def test_game_review_mabar_ml_has_signal(self):
        reviews = [{"text": "seru buat mabar ML bareng temen"}]
        self.assertTrue(
            shop_has_activity_signal(
                reviews,
                self.game_matcher.get("bm25_tokens") or [],
                activity_matcher=self.game_matcher,
            )
        )

    def test_nge_charge_laptop_not_game_signal(self):
        reviews = [{"text": "colokan banyak buat nge-charge laptop"}]
        self.assertFalse(
            shop_has_activity_signal(
                reviews,
                self.game_matcher.get("bm25_tokens") or [],
                activity_matcher=self.game_matcher,
            )
        )

    def test_rejection_clause_not_activity_signal(self):
        reviews = [{"text": "Tidak cocok untuk main game di sini, terlalu sepi."}]
        self.assertFalse(
            shop_has_activity_signal(
                reviews,
                self.game_matcher.get("bm25_tokens") or [],
                activity_matcher=self.game_matcher,
            )
        )

    def test_kerja_wifi_lancar_has_signal(self):
        reviews = [{"text": "wifi lancar buat kerja dan ngoding"}]
        self.assertTrue(
            shop_has_activity_signal(
                reviews,
                self.kerja_matcher.get("bm25_tokens") or [],
                activity_matcher=self.kerja_matcher,
            )
        )

    def test_activity_signal_tokens_drops_nongkrong_for_game(self):
        raw = ["nongkrong", "mabar", "ml", "main"]
        filtered = activity_signal_tokens(raw, activity_pills=["bermain game"])
        self.assertIn("mabar", filtered)
        self.assertNotIn("nongkrong", filtered)


class TestRetrieveTopKEntrypointsMocked(unittest.TestCase):
    @patch("hybrid_retrieval.score_shops_dense")
    @patch("hybrid_retrieval.score_shops_bm25")
    @patch("hybrid_retrieval.build_bm25_index")
    def test_retrieve_top_k_sets_activity_gate_telemetry(
        self, mock_bm25_index, mock_bm25_score, mock_dense
    ):
        mock_bm25_index.return_value = (["shop-a"], None, None)
        mock_bm25_score.return_value = {"shop-a": 1.0}
        mock_dense.return_value = ({"shop-a": 0.5}, {"pool": "mock"})
        profiles = [make_profile("shop-a", "A", ["wifi lancar buat kerja"])]
        result = retrieve_top_k(
            profiles,
            ["kerja"],
            pill_labels=MINI_PILL_LABELS,
            pill_mapping=MINI_PILL_MAPPING,
            top_k=3,
            activity_pills=["kerja"],
            attribute_pills=[],
        )
        self.assertTrue(result["telemetry"].get("activity_gate_on"))

    @patch("hybrid_retrieval.score_shops_dense")
    @patch("hybrid_retrieval.score_shops_bm25")
    @patch("hybrid_retrieval.build_bm25_index")
    def test_retrieve_top_k_by_text_skips_metadata_gate(
        self, mock_bm25_index, mock_bm25_score, mock_dense
    ):
        mock_bm25_index.return_value = (["shop-a"], None, None)
        mock_bm25_score.return_value = {"shop-a": 1.0}
        mock_dense.return_value = ({"shop-a": 0.5}, {"pool": "mock"})
        profiles = [make_profile("shop-a", "A", ["kopi enak"])]
        result = retrieve_top_k_by_text(
            profiles,
            query_tokens=["kopi"],
            dense_query_text="kopi enak",
            top_k=3,
        )
        gate = result["candidates"][0].get("metadata_gate") or {}
        self.assertFalse(gate.get("enabled"))


class TestGoldenQueriesSchema(unittest.TestCase):
    def test_golden_queries_file_valid(self):
        with GOLDEN_PATH.open(encoding="utf-8") as fh:
            data = json.load(fh)
        queries = data.get("queries") or []
        self.assertGreaterEqual(len(queries), 15)
        ids = [q.get("id") for q in queries]
        self.assertEqual(len(ids), len(set(ids)))
        for q in queries:
            self.assertIn(q.get("route"), ("pill", "free_text"))
            self.assertIn("input", q)
            self.assertIn("expect", q)


if __name__ == "__main__":
    unittest.main()

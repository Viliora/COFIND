#!/usr/bin/env python
"""Bandingkan COFIND_BM25_REVIEW_AGGREGATE max vs sum_top pada judgments yang ada."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JUDGMENTS = ROOT / "data" / "eval" / "relevance_judgments.json"


def main() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    _eval = ROOT / "scripts" / "eval"
    if str(_eval) not in sys.path:
        sys.path.insert(0, str(_eval))

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    os.environ["COFIND_CROSS_ENCODER"] = "false"
    os.environ["COFIND_ACTIVITY_GATE_MODE"] = "rrf_list"
    os.environ["COFIND_BM25_UNIT"] = "review"
    os.environ.setdefault("COFIND_DENSE_USE_ANN", "false")
    os.environ.setdefault("COFIND_REVIEW_ACTIVITY_INDEX", "false")

    from activity_gate_ablation import VARIANTS, _load_judgments, _precompute_query_caches, _run_variant
    from eval_queries_io import load_eval_queries
    from facilities_store import load_facilities_index
    from recommendation.helpers import _build_profiles_for_recommendation, _load_all_place_ids

    rel = _load_judgments(DEFAULT_JUDGMENTS)
    if not rel:
        print("Judgments kosong", file=sys.stderr)
        return 1

    place_ids = _load_all_place_ids()
    profiles, _ = _build_profiles_for_recommendation(
        place_ids, facilities_index=load_facilities_index(),
    )
    query_items = load_eval_queries()
    k_vals = [7, 30]
    top_k = int(os.getenv("COFIND_RETRIEVAL_TOP_K") or "30")

    rows = {}
    for agg in ("max", "sum_top"):
        os.environ["COFIND_BM25_REVIEW_AGGREGATE"] = agg
        caches, _ = _precompute_query_caches(profiles, query_items)
        block = _run_variant(
            VARIANTS["C_rrf_list_only"],
            profiles=profiles,
            query_caches=caches,
            rel_by_query=rel,
            k_values=k_vals,
            top_k_retrieval=top_k,
        )
        rows[agg] = block["summary"]
        print(f"=== aggregate={agg} ===")
        print(json.dumps(block["summary"], ensure_ascii=False, indent=2))

    out = ROOT / "data" / "eval" / "bm25_aggregate_ablation.json"
    out.write_text(json.dumps({"variants": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

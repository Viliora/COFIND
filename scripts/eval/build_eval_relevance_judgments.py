#!/usr/bin/env python
"""
Bangun relevance_judgments.json untuk golden query (baseline) + rubrik otomatis v1.

Rubric (independen dari hard gate — dense marginal = grade 1):
  3 = bukti leksikal kuat (skor aktivitas 1.0 atau banyak hit keyword atribut)
  2 = bukti leksikal jelas (skor > 0 / keyword atribut cocok)
  1 = relevan marjinal (hanya dense >= COFIND_ACTIVITY_DENSE_MIN, atau BM25+dense kuat free-text)
  0 = tidak relevan

Usage:
  python scripts/eval/build_eval_relevance_judgments.py
  python scripts/eval/build_eval_relevance_judgments.py --out data/eval/relevance_judgments.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASELINE = ROOT / "data" / "eval" / "baseline.json"
DEFAULT_EVAL_QUERIES = ROOT / "data" / "eval" / "eval_queries.json"
DEFAULT_OUT = ROOT / "data" / "eval" / "relevance_judgments.json"


def _sync_eval_queries(baseline_path: Path, eval_queries_path: Path) -> int:
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    queries = list(baseline.get("queries") or [])
    payload = {
        "schema_version": 1,
        "description": (
            "Query evaluasi golden (disalin dari baseline.json). "
            "Isi verbatim dari calon pengguna bila tersedia."
        ),
        "queries": [
            {
                "id": q.get("id"),
                "route": q.get("route"),
                "input": q.get("input") or {},
                "tags": q.get("tags") or [],
            }
            for q in queries
            if q.get("id")
        ],
    }
    eval_queries_path.parent.mkdir(parents=True, exist_ok=True)
    eval_queries_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return len(payload["queries"])


def _grade_pill_shop(
    profile: dict,
    *,
    activity_pills: List[str],
    attribute_pills: List[str],
    pill_labels,
    pill_mapping,
    dense_score: float,
    dense_min: float,
) -> Tuple[int, str]:
    from hybrid_retrieval import (
        build_sparse_query_tokens,
        compile_activity_matcher,
        shop_activity_lexical_max,
        text_matches_tokens,
    )

    pid = str(profile.get("place_id") or "")
    reviews = profile.get("reviews") or []
    component: List[int] = []

    for pill in activity_pills:
        matcher = compile_activity_matcher(
            [pill], pill_labels=pill_labels, pill_mapping=pill_mapping,
        )
        tokens = list(matcher.get("bm25_tokens") or [])
        lex = shop_activity_lexical_max(reviews, tokens, activity_matcher=matcher)
        if lex >= 1.0:
            component.append(3)
        elif lex > 0:
            component.append(2)
        elif dense_score >= dense_min:
            component.append(1)
        else:
            component.append(0)

    for pill in attribute_pills:
        tokens = build_sparse_query_tokens(
            [pill], pill_labels=pill_labels, pill_mapping=pill_mapping,
        )
        hits = sum(
            1 for row in reviews
            if text_matches_tokens(str(row.get("text") or row.get("review_text") or ""), tokens)
        )
        if hits >= 2:
            component.append(3)
        elif hits >= 1:
            component.append(2)
        else:
            component.append(0)

    if not component:
        return 0, "no_pills"
    grade = min(component)
    return grade, "pill_min_component"


def _grade_free_text_shop(
    bm25_raw: float,
    dense_raw: float,
    *,
    bm25_p90: float,
    dense_p90: float,
    bm25_p75: float,
    dense_p75: float,
) -> Tuple[int, str]:
    if bm25_raw >= bm25_p90 or dense_raw >= dense_p90:
        return 3, "free_text_top_decile"
    if bm25_raw >= bm25_p75 or dense_raw >= dense_p75:
        return 2, "free_text_top_quartile"
    if bm25_raw > 0 or dense_raw >= 0.72:
        return 1, "free_text_marginal"
    return 0, "free_text_weak"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--eval-queries", type=Path, default=DEFAULT_EVAL_QUERIES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--sync-queries-only", action="store_true")
    args = parser.parse_args()

    if not args.baseline.is_file():
        print(f"Baseline tidak ada: {args.baseline}", file=sys.stderr)
        return 1

    n_q = _sync_eval_queries(args.baseline, args.eval_queries)
    print(f"eval_queries.json: {n_q} query")
    if args.sync_queries_only:
        return 0

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    os.environ.setdefault("COFIND_CROSS_ENCODER", "false")
    os.environ.setdefault("COFIND_ACTIVITY_GATE_MODE", "off")

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")

    from facilities_store import load_facilities_index
    from hybrid_retrieval import (
        activity_dense_min,
        build_dense_query_text,
        build_sparse_query_tokens,
        score_bm25_for_hybrid_retrieval,
        score_shops_dense,
    )
    from pill_config import PILL_LABELS, PILL_MAPPING
    from recommendation.helpers import _build_profiles_for_recommendation, _load_all_place_ids
    from recommendation.pipeline import _split_preference_pills

    _eval_dir = ROOT / "scripts" / "eval"
    if str(_eval_dir) not in sys.path:
        sys.path.insert(0, str(_eval_dir))
    from eval_queries_io import load_eval_queries

    query_items = load_eval_queries(args.eval_queries)
    place_ids = _load_all_place_ids()
    if not place_ids:
        print("DATABASE_URL / place kosong", file=sys.stderr)
        return 1

    facilities_index = load_facilities_index()
    profiles, _ = _build_profiles_for_recommendation(
        place_ids, facilities_index=facilities_index,
    )
    profiles_by_pid = {
        str(p.get("place_id")): p for p in profiles if p.get("place_id")
    }
    dense_min = activity_dense_min()

    judgments = []
    for item in query_items:
        qid = str(item.get("id") or "")
        route = item.get("route")
        inp = item.get("input") or {}
        labels = []

        if route == "pill":
            pills = inp.get("pills") or []
            activity, attribute = _split_preference_pills(pills)
            query_tokens = build_sparse_query_tokens(
                pills, pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING,
            )
            dense_text = build_dense_query_text(
                pills, pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING,
            )
            bm25_raw, _ = score_bm25_for_hybrid_retrieval(profiles, query_tokens)
            dense_raw, _ = score_shops_dense(
                profiles, dense_text, query_tokens=query_tokens,
            )
            for pid, profile in profiles_by_pid.items():
                grade, note = _grade_pill_shop(
                    profile,
                    activity_pills=list(activity),
                    attribute_pills=list(attribute),
                    pill_labels=PILL_LABELS,
                    pill_mapping=PILL_MAPPING,
                    dense_score=float(dense_raw.get(pid) or 0.0),
                    dense_min=dense_min,
                )
                if grade <= 0:
                    continue
                labels.append({
                    "place_id": pid,
                    "grade": grade,
                    "annotator": "rubric_v1_auto",
                    "notes": note,
                })
        elif route == "free_text":
            from hybrid_retrieval import sparse_tokens_from_keywords

            keywords = inp.get("keywords_mock") or []
            dense = inp.get("dense_query_mock") or inp.get("query_text") or ""
            clean = sparse_tokens_from_keywords(keywords)
            bm25_raw, _ = score_bm25_for_hybrid_retrieval(profiles, clean)
            dense_raw, _ = score_shops_dense(profiles, dense, query_tokens=clean)
            bm25_vals = sorted(float(v) for v in bm25_raw.values())
            dense_vals = sorted(float(v) for v in dense_raw.values())

            def _pct(vals: List[float], p: float) -> float:
                if not vals:
                    return 0.0
                idx = min(len(vals) - 1, max(0, int(p * (len(vals) - 1))))
                return vals[idx]

            b90, b75 = _pct(bm25_vals, 0.9), _pct(bm25_vals, 0.75)
            d90, d75 = _pct(dense_vals, 0.9), _pct(dense_vals, 0.75)
            for pid in profiles_by_pid:
                grade, note = _grade_free_text_shop(
                    float(bm25_raw.get(pid) or 0.0),
                    float(dense_raw.get(pid) or 0.0),
                    bm25_p90=b90,
                    dense_p90=d90,
                    bm25_p75=b75,
                    dense_p75=d75,
                )
                if grade <= 0:
                    continue
                labels.append({
                    "place_id": pid,
                    "grade": grade,
                    "annotator": "rubric_v1_auto",
                    "notes": note,
                })
        else:
            continue

        labels.sort(key=lambda row: (-int(row["grade"]), row["place_id"]))
        judgments.append({"query_id": qid, "labels": labels})

    payload = {
        "schema_version": 1,
        "description": (
            "Label relevansi 0–3 per (query, toko). Grade dari rubrik otomatis v1 "
            "(build_eval_relevance_judgments.py); tinjau ulang untuk skripsi final."
        ),
        "protocol": {
            "annotators": 1,
            "align_queries": str(args.eval_queries.relative_to(ROOT)).replace("\\", "/"),
            "rubric": "rubric_v1_auto — lihat docstring build_eval_relevance_judgments.py",
            "relevant_threshold_recall": "grade >= 1",
        },
        "judgments": judgments,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    labeled_pairs = sum(len(j["labels"]) for j in judgments)
    print(f"relevance_judgments.json: {len(judgments)} query, {labeled_pairs} pasangan grade>0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

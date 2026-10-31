#!/usr/bin/env python
"""
Snapshot top-k retrieval (Fase 2) untuk data/eval/eval_queries.json — tanpa CE rerank / ABSA.

Usage:
  python scripts/eval/golden_retrieval_snapshot.py
  python scripts/eval/golden_retrieval_snapshot.py --queries data/eval/eval_queries.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "data" / "eval" / "retrieval_snapshot.json"


def _git_head() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
        ).strip()
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=Path, default=DEFAULT_EVAL_QUERIES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    _eval_dir = ROOT / "scripts" / "eval"
    if str(_eval_dir) not in sys.path:
        sys.path.insert(0, str(_eval_dir))
    from eval_queries_io import DEFAULT_EVAL_QUERIES, load_eval_queries

    os.environ["COFIND_CROSS_ENCODER"] = "false"
    os.environ["COFIND_ABSA_ENABLED"] = "false"
    os.environ.setdefault("COFIND_SEMANTIC_GATE", "false")

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")

    from facilities_store import load_facilities_index
    from hybrid_retrieval import retrieve_top_k, retrieve_top_k_by_text, retrieval_top_k
    from pill_config import PILL_LABELS, PILL_MAPPING
    from recommendation.helpers import _build_profiles_for_recommendation, _load_all_place_ids
    from recommendation.pipeline import _split_preference_pills

    try:
        query_items = load_eval_queries(args.queries)
    except FileNotFoundError as err:
        print(err, file=sys.stderr)
        return 1
    if not query_items:
        print(
            f"Tidak ada query di {args.queries}. "
            "Isi dari calon pengguna (lihat data/eval/eval_queries.example.json).",
            file=sys.stderr,
        )
        return 1

    place_ids = _load_all_place_ids()
    if not place_ids:
        print("Tidak ada place_id — periksa DATABASE_URL.", file=sys.stderr)
        return 1

    facilities_index = load_facilities_index()
    profiles, _ = _build_profiles_for_recommendation(
        place_ids, facilities_index=facilities_index,
    )
    quality_by_place = {str(p.get("place_id")): 0.5 for p in profiles if p.get("place_id")}
    top_k = retrieval_top_k()

    rows = []
    for item in query_items:
        qid = item.get("id")
        route = item.get("route")
        inp = item.get("input") or {}
        entry = {"id": qid, "route": route, "top_k": top_k, "place_ids": [], "error": None}

        try:
            if route == "pill":
                pills = inp.get("pills") or []
                activity, attribute = _split_preference_pills(pills)
                result = retrieve_top_k(
                    profiles,
                    pills,
                    pill_labels=PILL_LABELS,
                    pill_mapping=PILL_MAPPING,
                    quality_by_place=quality_by_place,
                    top_k=top_k,
                    activity_pills=activity,
                    attribute_pills=attribute,
                )
            elif route == "free_text":
                keywords = inp.get("keywords_mock") or []
                dense = inp.get("dense_query_mock") or inp.get("query_text") or ""
                result = retrieve_top_k_by_text(
                    profiles,
                    query_tokens=keywords,
                    dense_query_text=dense,
                    quality_by_place=quality_by_place,
                    top_k=top_k,
                )
            else:
                entry["error"] = f"unknown_route:{route}"
                rows.append(entry)
                continue

            cands = result.get("candidates") or []
            entry["place_ids"] = [
                str(c.get("place_id") or "") for c in cands if c.get("place_id")
            ]
            entry["telemetry"] = {
                "activity_gated": result.get("telemetry", {}).get("activity_gated"),
                "bm25_backend": result.get("telemetry", {}).get("bm25_backend"),
            }
        except Exception as err:
            entry["error"] = str(err)[:300]

        rows.append(entry)

    payload = {
        "git_commit": _git_head(),
        "profile_count": len(profiles),
        "env_flags": {
            "COFIND_CROSS_ENCODER": os.environ.get("COFIND_CROSS_ENCODER"),
            "COFIND_ABSA_ENABLED": os.environ.get("COFIND_ABSA_ENABLED"),
            "COFIND_SEMANTIC_GATE": os.environ.get("COFIND_SEMANTIC_GATE"),
            "COFIND_BM25_BACKEND": os.environ.get("COFIND_BM25_BACKEND"),
        },
        "queries": rows,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Snapshot: {args.out} ({len(rows)} query, {len(profiles)} profil)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
"""
Catat baseline konfigurasi + daftar query eval (data/eval/eval_queries.json).

Usage:
  python scripts/eval/run_golden_baseline.py
  python scripts/eval/run_golden_baseline.py --out data/eval/baseline.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "data" / "eval" / "baseline.json"


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

    try:
        query_items = load_eval_queries(args.queries)
    except FileNotFoundError as err:
        print(err, file=sys.stderr)
        return 1
    from hybrid_retrieval import retrieval_top_k
    from cross_encoder_rerank import ce_rerank_enabled
    from postgres_fts import bm25_backend
    from semantic_match import model_name

    rows = []
    for item in query_items:
        rows.append({
            "id": item.get("id"),
            "route": item.get("route"),
            "input": item.get("input"),
            "source": item.get("source"),
            "verbatim": item.get("verbatim"),
        })

    payload = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_head(),
        "mode": {
            "ce_rerank": ce_rerank_enabled(),
            "bm25_backend": bm25_backend(),
            "embedding_model": model_name(),
            "retrieval_top_k": retrieval_top_k(),
            "COFIND_CROSS_ENCODER": os.getenv("COFIND_CROSS_ENCODER"),
            "COFIND_CE_RERANK_WEIGHT": os.getenv("COFIND_CE_RERANK_WEIGHT"),
            "COFIND_BM25_BACKEND": os.getenv("COFIND_BM25_BACKEND"),
        },
        "eval_query_count": len(rows),
        "queries": rows,
        "metrics_note": (
            "Baseline struktural: konfigurasi + daftar query calon pengguna. "
            "nDCG/MRR: relevance_judgments.json + relevance_metrics.py."
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Baseline tersimpan: {args.out} ({len(rows)} query)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

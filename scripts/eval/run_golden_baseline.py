#!/usr/bin/env python
"""
Jalankan golden_queries.json (retrieval-only / gate hints) dan simpan baseline metrik.

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
GOLDEN = ROOT / "tests" / "golden_queries.json"
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
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    from hybrid_retrieval import retrieval_top_k
    from llm_recommender import rerank_enabled as llm_rerank_enabled
    from postgres_fts import bm25_backend
    from semantic_match import model_name

    rows = []
    for item in golden.get("queries") or []:
        expect = item.get("expect") or {}
        rows.append({
            "id": item.get("id"),
            "route": item.get("route"),
            "input": item.get("input"),
            "expect_activity_gate": expect.get("activity_gate"),
            "expect_metadata_gate": expect.get("metadata_gate"),
            "tags": item.get("tags") or [],
        })

    payload = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_head(),
        "mode": {
            "llm_rerank": llm_rerank_enabled(),
            "bm25_backend": bm25_backend(),
            "embedding_model": model_name(),
            "retrieval_top_k": retrieval_top_k(),
            "COFIND_LLM_RERANK": os.getenv("COFIND_LLM_RERANK"),
            "COFIND_CROSS_ENCODER": os.getenv("COFIND_CROSS_ENCODER"),
            "COFIND_BM25_BACKEND": os.getenv("COFIND_BM25_BACKEND"),
        },
        "golden_query_count": len(rows),
        "queries": rows,
        "metrics_note": (
            "Baseline struktural: konfigurasi + daftar golden. "
            "Precision@k / citation precision butuh hit DB penuh (ragas_eval / E2E)."
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Baseline tersimpan: {args.out} ({len(rows)} query)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

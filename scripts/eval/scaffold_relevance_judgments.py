#!/usr/bin/env python
"""
Buat kerangka relevance_judgments.json dari snapshot retrieval (place_id nyata, grade belum diisi).

Usage:
  python scripts/eval/scaffold_relevance_judgments.py
  python scripts/eval/scaffold_relevance_judgments.py --snapshot data/eval/retrieval_snapshot.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SNAPSHOT = ROOT / "data" / "eval" / "retrieval_snapshot.json"
DEFAULT_OUT = ROOT / "data" / "eval" / "relevance_judgments.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--queries", type=str, default="", help="Comma-separated query_id; default=all")
    args = parser.parse_args()

    if not args.snapshot.is_file():
        print(f"Snapshot tidak ada: {args.snapshot}", flush=True)
        print("Jalankan: python scripts/eval/golden_retrieval_snapshot.py")
        return 1

    snap = json.loads(args.snapshot.read_text(encoding="utf-8"))
    filter_ids = {q.strip() for q in args.queries.split(",") if q.strip()}

    judgments = []
    for row in snap.get("queries") or []:
        qid = str(row.get("id") or "")
        if not qid or (filter_ids and qid not in filter_ids):
            continue
        if row.get("error"):
            continue
        labels = []
        for rank, pid in enumerate(row.get("place_ids") or [], start=1):
            pid = str(pid or "").strip()
            if not pid:
                continue
            labels.append({
                "place_id": pid,
                "grade": None,
                "annotator": "",
                "notes": f"Top-{rank} snapshot — isi grade 0–3 setelah baca ulasan vs intent query.",
            })
        judgments.append({"query_id": qid, "labels": labels})

    payload = {
        "schema_version": 1,
        "description": (
            "Label relevansi manual query×toko. Grade: 0=tidak relevan, 1=marjinal, "
            "2=relevan, 3=sangat relevan. Ganti grade null dengan angka sebelum eval."
        ),
        "protocol": {
            "annotators": 1,
            "align_queries": "query_id = data/eval/eval_queries.json",
            "source_snapshot": str(args.snapshot.relative_to(ROOT)).replace("\\", "/"),
        },
        "judgments": judgments,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Kerangka: {args.out} ({len(judgments)} query)")
    print("Isi field grade (0–3), lalu:")
    print("  python scripts/eval/relevance_metrics.py --judgments", args.out, "--run-retrieval")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

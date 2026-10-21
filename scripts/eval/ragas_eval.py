#!/usr/bin/env python
"""
Evaluasi offline RAGAS (opsional) — retrieval / konteks kutipan.

  pip install -r requirements-dev.txt
  python scripts/eval/ragas_eval.py --dataset scripts/eval/sample_ragas_dataset.json

Tanpa API LLM judge, skrip ini menghitung metrik sederhana (coverage golden).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "scripts" / "eval" / "sample_ragas_dataset.json"
DEFAULT_OUT = ROOT / "scripts" / "eval" / "ragas_report.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--use-ragas", action="store_true")
    args = parser.parse_args()

    if not args.dataset.is_file():
        print(f"Dataset tidak ada: {args.dataset}", file=sys.stderr)
        return 1

    data = json.loads(args.dataset.read_text(encoding="utf-8"))
    cases = data.get("cases") or []

    report = {
        "dataset": str(args.dataset),
        "case_count": len(cases),
        "ragas": None,
        "simple_coverage": [],
    }

    for case in cases:
        report["simple_coverage"].append({
            "id": case.get("id"),
            "has_gold_place": bool(case.get("gold_place_id")),
            "reference_snippets": len(case.get("reference_contexts") or []),
        })

    if args.use_ragas:
        try:
            from datasets import Dataset
            from ragas import evaluate
            from ragas.metrics import context_precision, context_recall

            rows = []
            for case in cases:
                rows.append({
                    "question": case.get("question") or "",
                    "contexts": case.get("contexts") or case.get("reference_contexts") or [],
                    "ground_truth": case.get("ground_truth") or "",
                })
            ds = Dataset.from_list(rows)
            result = evaluate(ds, metrics=[context_precision, context_recall])
            report["ragas"] = dict(result)
        except Exception as err:
            report["ragas_error"] = str(err)[:300]

    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Laporan: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

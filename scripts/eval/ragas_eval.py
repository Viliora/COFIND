#!/usr/bin/env python
"""
Evaluasi offline RAGAS (Gemini judge) — Faithfulness, Response Relevancy, Context P/R.

  pip install -r requirements-dev.txt
  python scripts/eval/ragas_eval.py --dataset scripts/eval/ragas_smoke_dataset.json --use-ragas

Tanpa --use-ragas: hanya coverage field (tanpa API).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = Path(__file__).resolve().parent
for _p in (ROOT, EVAL_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from ragas_dataset import coverage_summary, load_cases, normalize_case  # noqa: E402

DEFAULT_DATASET = ROOT / "scripts" / "eval" / "ragas_smoke_dataset.json"
DEFAULT_OUT = ROOT / "scripts" / "eval" / "ragas_report.json"

DEFAULT_METRICS = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
)


def _parse_metrics(raw: Optional[str]) -> List[str]:
    if not raw or not raw.strip():
        return list(DEFAULT_METRICS)
    return [m.strip().lower() for m in raw.split(",") if m.strip()]


def _build_metric_instances(names: List[str], llm, embeddings, *, context_relevance: bool):
    # Legacy Metric subclasses — kompatibel dengan evaluate() 0.4.3 (collections BaseMetric tidak).
    from ragas.metrics import (
        AnswerRelevancy,
        ContextPrecision,
        ContextRecall,
        ContextRelevance,
        Faithfulness,
    )

    registry = {
        "faithfulness": lambda: Faithfulness(llm=llm),
        "answer_relevancy": lambda: AnswerRelevancy(llm=llm, embeddings=embeddings),
        "context_precision": lambda: ContextPrecision(llm=llm),
        "context_recall": lambda: ContextRecall(llm=llm),
        "context_relevance": lambda: ContextRelevance(llm=llm),
    }
    selected = list(names)
    if context_relevance and "context_relevance" not in selected:
        selected.append("context_relevance")

    metrics = []
    for name in selected:
        factory = registry.get(name)
        if factory is None:
            raise ValueError(f"Metrik tidak dikenal: {name}")
        metrics.append(factory())
    return metrics


def _metric_means(scores_list: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    if not scores_list:
        return {}
    keys = scores_list[0].keys()
    means: Dict[str, Optional[float]] = {}
    for key in keys:
        values = []
        for row in scores_list:
            val = row.get(key)
            if isinstance(val, (int, float)) and val == val:
                values.append(float(val))
        means[key] = round(sum(values) / len(values), 4) if values else None
    return means


def run_ragas_eval(
    cases: List[Dict[str, Any]],
    metric_names: List[str],
    *,
    context_relevance: bool,
    max_workers: int,
) -> Dict[str, Any]:
    from datasets import Dataset
    from ragas import evaluate
    from ragas.run_config import RunConfig

    from ragas_gemini import (
        _load_project_env,
        build_ragas_embeddings,
        build_ragas_llm,
        judge_info,
    )

    _load_project_env()
    import ragas as ragas_pkg

    llm = build_ragas_llm()
    embeddings = build_ragas_embeddings()
    metrics = _build_metric_instances(
        metric_names, llm, embeddings, context_relevance=context_relevance,
    )

    rows = [normalize_case(c) for c in cases]
    ds = Dataset.from_list(rows)
    result = evaluate(
        ds,
        metrics=metrics,
        llm=llm,
        embeddings=embeddings,
        run_config=RunConfig(max_workers=max(1, max_workers), timeout=300),
        raise_exceptions=False,
    )

    scores_list = list(result.scores)
    judge_model, embed_model = judge_info()
    return {
        "ragas_version": getattr(ragas_pkg, "__version__", None),
        "judge_model": judge_model,
        "embedding_model": embed_model,
        "metrics_requested": metric_names + (["context_relevance"] if context_relevance else []),
        "metric_means": _metric_means(scores_list),
        "per_case_scores": scores_list,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Eval RAGAS offline (judge Gemini).")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--use-ragas", action="store_true")
    parser.add_argument("--metrics", type=str, default=None, help="Comma-separated metric names")
    parser.add_argument("--context-relevance", action="store_true")
    parser.add_argument("--max-workers", type=int, default=2)
    args = parser.parse_args()

    if not args.dataset.is_file():
        print(f"Dataset tidak ada: {args.dataset}", file=sys.stderr)
        return 1

    cases = load_cases(args.dataset)
    report: Dict[str, Any] = {
        "dataset": str(args.dataset),
        "case_count": len(cases),
        "simple_coverage": [coverage_summary(c) for c in cases],
        "ragas": None,
    }

    if args.use_ragas:
        try:
            metric_names = _parse_metrics(args.metrics)
            report["ragas"] = run_ragas_eval(
                cases,
                metric_names,
                context_relevance=args.context_relevance,
                max_workers=args.max_workers,
            )
        except Exception as err:
            report["ragas_error"] = str(err)[:800]
            print(f"RAGAS gagal: {err}", file=sys.stderr)
            args.out.write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return 1

    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Laporan: {args.out}")
    if report.get("ragas"):
        print("Mean:", report["ragas"].get("metric_means"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

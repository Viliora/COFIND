#!/usr/bin/env python
"""
Grid search terbatas pada env yang memengaruhi ranking; pilih kombinasi terbaik di dev judgments.

Usage:
  python scripts/eval/threshold_tuning.py --judgments data/eval/relevance_judgments.json
  python scripts/eval/threshold_tuning.py --dry-run
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JUDGMENTS = ROOT / "data" / "eval" / "relevance_judgments.json"
METRICS = ROOT / "scripts" / "eval" / "relevance_metrics.py"


def _grid() -> dict[str, list[str]]:
    return {
        "COFIND_RRF_K": ["40", "60", "80"],
        "COFIND_CE_RERANK_WEIGHT": ["0.4", "0.55", "0.7"],
        "COFIND_ACTIVITY_DENSE_MIN": ["0.45", "0.55", "0.65"],
        "COFIND_TAU_LOW": ["0.30", "0.35", "0.40"],
        "COFIND_TAU_HIGH": ["0.68", "0.72", "0.76"],
    }


def _run_combo(env_overrides: dict[str, str], judgments: Path, k: int) -> float | None:
    env = os.environ.copy()
    env.update(env_overrides)
    env["COFIND_CROSS_ENCODER"] = "false"
    proc = subprocess.run(
        [
            sys.executable,
            str(METRICS),
            "--judgments",
            str(judgments),
            "--run-retrieval",
            "--k",
            str(k),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        return None
    marker = "--- summary ---"
    if marker not in proc.stdout:
        return None
    summary_json = proc.stdout.split(marker, 1)[1].strip()
    try:
        summary = json.loads(summary_json)
    except json.JSONDecodeError:
        return None
    key = f"macro_ndcg@{k}"
    val = summary.get(key)
    return float(val) if val is not None else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--judgments", type=Path, default=DEFAULT_JUDGMENTS)
    parser.add_argument("--k", type=int, default=7)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-combos", type=int, default=24)
    args = parser.parse_args()

    keys = list(_grid().keys())
    values = [_grid()[k] for k in keys]
    combos = list(itertools.product(*values))[: args.max_combos]

    if args.dry_run:
        print(f"Grid: {len(list(itertools.product(*values)))} kombinasi penuh; akan uji {len(combos)}")
        for c in combos[:5]:
            print(dict(zip(keys, c)))
        return 0

    best_score = -1.0
    best_env: dict[str, str] | None = None
    for combo in combos:
        overrides = dict(zip(keys, combo))
        score = _run_combo(overrides, args.judgments, args.k)
        if score is None:
            continue
        print(json.dumps({"score": score, "env": overrides}, ensure_ascii=False))
        if score > best_score:
            best_score = score
            best_env = overrides

    if best_env is None:
        print("Tuning gagal — pastikan judgments berisi place_id nyata dan DATABASE_URL.", file=sys.stderr)
        return 1

    print("--- best ---")
    print(json.dumps({"macro_ndcg": best_score, "env": best_env}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

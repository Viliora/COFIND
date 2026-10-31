#!/usr/bin/env python
"""
Metrik drift sparse per pill (untuk before/after kurasi review_keywords).

  tokens        — unigram BM25 unik hasil perataan keyword (sumber query drift)
  broad_tokens  — token yang muncul di >= BROAD_SHARE review (terlalu umum)
  review_touch  — porsi review yang memuat minimal satu token pill
  broad_touch   — porsi review yang hanya tersentuh lewat token umum

Usage:
  python scripts/eval/pill_keyword_drift_report.py [--out data/eval/x.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
os.environ["COFIND_SEMANTIC_GATE"] = "false"

BROAD_SHARE = 0.08


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    from db_backend import get_connection
    from hybrid_retrieval import build_sparse_query_tokens, tokenize_for_match
    from pill_config import PILL_LABELS, PILL_MAPPING

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT review_text FROM reviews WHERE review_text IS NOT NULL")
        texts = [str(r[0] or "") for r in cur.fetchall()]
    finally:
        conn.close()

    docs = [set(tokenize_for_match(t)) for t in texts]
    n = len(docs)
    df: dict[str, int] = {}
    for d in docs:
        for tok in d:
            df[tok] = df.get(tok, 0) + 1

    rows = {}
    for pill, spec in PILL_MAPPING.items():
        toks = build_sparse_query_tokens([pill], pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING)
        seen = set(toks)
        broad = [t for t in toks if df.get(t, 0) / n >= BROAD_SHARE]
        touch = sum(1 for d in docs if d & seen)
        broad_only = sum(1 for d in docs if (d & seen) and not (d & (seen - set(broad))))
        rows[pill] = {
            "keywords": len(spec.get("review_keywords") or []),
            "tokens": len(toks),
            "broad_tokens": broad,
            "review_touch": round(touch / n, 3),
            "broad_only_touch": round(broad_only / n, 3),
        }

    total_tokens = sum(r["tokens"] for r in rows.values())
    total_broad = sum(len(r["broad_tokens"]) for r in rows.values())
    print(f"reviews={n} total_tokens={total_tokens} total_broad={total_broad}")
    for pill, r in rows.items():
        print(
            f"{pill:28s} kw={r['keywords']:2d} tok={r['tokens']:2d} "
            f"touch={r['review_touch']:.2f} broad_only={r['broad_only_touch']:.2f} "
            f"broad={r['broad_tokens']}"
        )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps({"reviews": n, "pills": rows}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

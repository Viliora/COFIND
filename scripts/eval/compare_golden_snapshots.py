#!/usr/bin/env python
"""Bandingkan dua golden_retrieval_snapshot.json (identik = exit 0)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("before")
    parser.add_argument("after")
    args = parser.parse_args()

    a = json.loads(Path(args.before).read_text(encoding="utf-8"))
    b = json.loads(Path(args.after).read_text(encoding="utf-8"))
    diffs = []
    by_a = {q["id"]: q for q in a.get("queries") or []}
    by_b = {q["id"]: q for q in b.get("queries") or []}
    for qid in sorted(set(by_a) | set(by_b)):
        pa = by_a.get(qid, {}).get("place_ids")
        pb = by_b.get(qid, {}).get("place_ids")
        if pa != pb:
            diffs.append({"id": qid, "before": pa, "after": pb})
    if diffs:
        print(json.dumps(diffs, ensure_ascii=False, indent=2))
        return 1
    print("identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

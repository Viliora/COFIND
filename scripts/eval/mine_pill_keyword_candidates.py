#!/usr/bin/env python
"""
Ekspansi sekali jalan: cari frasa informal nyata di review untuk tiap pill.

Keluaran (untuk kurasi manual, BUKAN auto-apply):
  1. keyword_stats  — df tiap review_keywords lama (0 hit / terlalu umum).
  2. candidates     — n-gram dengan lift tinggi di klausa yang dekat secara dense
                      ke definisi pill, belum ada di review_keywords.

Usage:
  python scripts/eval/mine_pill_keyword_candidates.py
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
os.environ.setdefault("COFIND_SEMANTIC_GATE", "true")

OUT = ROOT / "data" / "eval" / "pill_keyword_candidates.json"
TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP = frozenset(
    "yang dan di ke dari ini itu aku saya kami kita nya juga sih deh dong aja ada ga gak tidak "
    "nggak banget bgt sangat cukup lumayan untuk buat bisa jadi karena tapi tp atau dengan pada "
    "sama udah sudah lagi masih lebih sekali sini situ banyak sedikit agak the and is to of a "
    "ya yg dg dgn utk krn trs terus kalau kalo kl saat waktu pas habis abis mau akan sih lah kok "
    "cafe coffee shop kopi tempat tempatnya disini disana sini ke sana".split()
)
MIN_POS_DF = 2
MIN_LIFT = 2.5
TOP_FRAC = 0.12
MAX_PER_PILL = 25


def tokens(text: str) -> list[str]:
    return TOKEN_RE.findall((text or "").lower())


def ngrams(toks: list[str], n_max: int = 3) -> set[str]:
    out: set[str] = set()
    for n in range(1, n_max + 1):
        for i in range(len(toks) - n + 1):
            gram = toks[i : i + n]
            if gram[0] in STOP or gram[-1] in STOP:
                continue
            if n == 1 and (len(gram[0]) < 4 or gram[0].isdigit()):
                continue
            out.add(" ".join(gram))
    return out


def kw_regex(kw: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])" + re.escape(kw.lower()) + r"(?![a-z0-9])")


def main() -> int:
    import numpy as np

    from db_backend import get_connection
    from hybrid_retrieval import build_dense_query_text
    from pill_config import PILL_LABELS, PILL_MAPPING
    from semantic_match import embed_texts, split_clauses

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, review_text FROM reviews WHERE review_text IS NOT NULL")
        rows = cur.fetchall()
    finally:
        conn.close()

    review_texts = [str(t or "") for _, t in rows]
    review_lower = [t.lower() for t in review_texts]
    clauses: list[str] = []
    for text in review_texts:
        clauses.extend(split_clauses(text))
    clauses = list(dict.fromkeys(c for c in clauses if len(c) >= 8))
    print(f"reviews={len(review_texts)} clauses={len(clauses)}", flush=True)

    vecs = embed_texts(clauses)
    clause_list = [c for c in clauses if c in vecs]
    mat = np.vstack([np.asarray(vecs[c], dtype=np.float32) for c in clause_list])
    clause_grams = [ngrams(tokens(c)) for c in clause_list]
    all_df: Counter = Counter()
    for g in clause_grams:
        all_df.update(g)
    n_all = len(clause_list)

    report = {"reviews": len(review_texts), "clauses": n_all, "pills": {}}
    for pill, spec in PILL_MAPPING.items():
        qtext = build_dense_query_text(
            [pill], pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING,
        )
        qv = embed_texts([qtext]).get(qtext.strip())
        if qv is None:
            qv = next(iter(embed_texts([qtext]).values()), None)
        sims = mat @ np.asarray(qv, dtype=np.float32)
        k = max(8, int(n_all * TOP_FRAC))
        pos_idx = np.argsort(-sims)[:k]
        pos_df: Counter = Counter()
        for i in pos_idx:
            pos_df.update(clause_grams[i])

        existing = [str(x).lower() for x in (spec.get("review_keywords") or [])]
        existing_set = set(existing)
        stats = []
        for kw in existing:
            rx = kw_regex(kw)
            hits = sum(1 for t in review_lower if rx.search(t))
            stats.append({"keyword": kw, "review_hits": hits})

        cands = []
        for gram, pdf in pos_df.items():
            if pdf < MIN_POS_DF or gram in existing_set:
                continue
            lift = (pdf / k) / ((all_df[gram]) / n_all)
            if lift < MIN_LIFT:
                continue
            cands.append(
                {
                    "phrase": gram,
                    "pos_df": pdf,
                    "all_df": all_df[gram],
                    "lift": round(lift, 2),
                    "score": round(lift * math.log1p(pdf), 2),
                }
            )
        cands.sort(key=lambda r: -r["score"])
        report["pills"][pill] = {
            "pos_clauses": k,
            "keyword_stats": stats,
            "candidates": cands[:MAX_PER_PILL],
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    for pill, data in report["pills"].items():
        zero = [s["keyword"] for s in data["keyword_stats"] if s["review_hits"] == 0]
        broad = [
            f'{s["keyword"]}={s["review_hits"]}'
            for s in data["keyword_stats"]
            if s["review_hits"] >= 12
        ]
        print(f"\n[{pill}] zero_hit={zero}")
        print(f"  broad(>=12)={broad}")
        print("  cand:", ", ".join(f'{c["phrase"]}({c["pos_df"]}/{c["all_df"]})' for c in data["candidates"][:15]))
    print(f"\nJSON: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

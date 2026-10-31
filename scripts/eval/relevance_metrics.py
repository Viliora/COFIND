#!/usr/bin/env python
"""
Hitung nDCG@k, Recall@k, dan MRR@k dari label relevansi + ranking retrieval.

Usage:
  python scripts/eval/relevance_metrics.py --judgments data/eval/relevance_judgments.json
  python scripts/eval/relevance_metrics.py --judgments ... --snapshot data/eval/golden_retrieval_snapshot.json
  python scripts/eval/relevance_metrics.py --judgments ... --run-retrieval
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JUDGMENTS = ROOT / "data" / "eval" / "relevance_judgments.json"
DEFAULT_SNAPSHOT = ROOT / "data" / "eval" / "retrieval_snapshot.json"


def _load_judgments(path: Path) -> Dict[str, Dict[str, float]]:
    """query_id -> place_id -> graded relevance (0..3)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[str, Dict[str, float]] = {}
    for block in data.get("judgments") or []:
        qid = str(block.get("query_id") or "")
        if not qid:
            continue
        rel: Dict[str, float] = {}
        for row in block.get("labels") or []:
            pid = str(row.get("place_id") or "")
            if not pid or pid.startswith("PLACE_ID_CONTOH"):
                continue
            raw_grade = row.get("grade")
            if raw_grade is None or raw_grade == "":
                continue
            try:
                grade = float(raw_grade)
            except (TypeError, ValueError):
                continue
            rel[pid] = max(rel.get(pid, 0.0), grade)
        if rel:
            out[qid] = rel
    return out


def _dcg(relevances: Sequence[float]) -> float:
    total = 0.0
    for i, rel in enumerate(relevances, start=1):
        total += (2.0 ** rel - 1.0) / math.log2(i + 1)
    return total


def ndcg_at_k(ranked_ids: Sequence[str], rel_map: Dict[str, float], k: int) -> float:
    if not rel_map:
        return 0.0
    top = ranked_ids[:k]
    gains = [rel_map.get(pid, 0.0) for pid in top]
    ideal = sorted(rel_map.values(), reverse=True)[:k]
    idcg = _dcg(ideal)
    if idcg <= 0:
        return 0.0
    return _dcg(gains) / idcg


def recall_at_k(ranked_ids: Sequence[str], rel_map: Dict[str, float], k: int) -> float:
    relevant = {pid for pid, g in rel_map.items() if g >= 1.0}
    if not relevant:
        return 0.0
    hit = sum(1 for pid in ranked_ids[:k] if pid in relevant)
    return hit / len(relevant)


def mrr_at_k(ranked_ids: Sequence[str], rel_map: Dict[str, float], k: int) -> float:
    relevant = {pid for pid, g in rel_map.items() if g >= 1.0}
    if not relevant:
        return 0.0
    for i, pid in enumerate(ranked_ids[:k], start=1):
        if pid in relevant:
            return 1.0 / i
    return 0.0


def _rankings_from_snapshot(path: Path) -> Dict[str, List[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[str, List[str]] = {}
    for row in data.get("queries") or []:
        qid = str(row.get("id") or "")
        if qid:
            out[qid] = [str(x) for x in (row.get("place_ids") or [])]
    return out


def _rankings_from_retrieval() -> Dict[str, List[str]]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    os.environ.setdefault("COFIND_CROSS_ENCODER", "false")
    os.environ.setdefault("COFIND_ABSA_ENABLED", "false")
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    from facilities_store import load_facilities_index
    from hybrid_retrieval import retrieve_top_k, retrieve_top_k_by_text, retrieval_top_k
    from pill_config import PILL_LABELS, PILL_MAPPING
    from recommendation.helpers import _build_profiles_for_recommendation, _load_all_place_ids
    from recommendation.pipeline import _split_preference_pills

    _eval_dir = ROOT / "scripts" / "eval"
    if str(_eval_dir) not in sys.path:
        sys.path.insert(0, str(_eval_dir))
    from eval_queries_io import load_eval_queries

    query_items = load_eval_queries()
    if not query_items:
        raise RuntimeError(
            "eval_queries.json kosong — isi query calon pengguna sebelum --run-retrieval."
        )
    place_ids = _load_all_place_ids()
    if not place_ids:
        raise RuntimeError("Tidak ada place_id — periksa DATABASE_URL.")
    facilities_index = load_facilities_index()
    profiles, _ = _build_profiles_for_recommendation(
        place_ids, facilities_index=facilities_index,
    )
    quality_by_place = {str(p.get("place_id")): 0.5 for p in profiles if p.get("place_id")}
    top_k = retrieval_top_k()
    out: Dict[str, List[str]] = {}
    for item in query_items:
        qid = str(item.get("id") or "")
        route = item.get("route")
        inp = item.get("input") or {}
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
            continue
        cands = result.get("candidates") or []
        out[qid] = [str(c.get("place_id") or "") for c in cands if c.get("place_id")]
    return out


def _macro_avg(values: Iterable[float]) -> float:
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--judgments", type=Path, default=DEFAULT_JUDGMENTS)
    parser.add_argument("--snapshot", type=Path, default=None)
    parser.add_argument("--run-retrieval", action="store_true")
    parser.add_argument("--k", type=int, default=7)
    args = parser.parse_args()

    rel_by_query = _load_judgments(args.judgments)
    if not rel_by_query:
        print(
            "Belum ada label siap eval: semua place_id masih PLACE_ID_CONTOH_* "
            "atau grade masih null/kosong.",
            file=sys.stderr,
        )
        print(
            "Langkah: python scripts/eval/scaffold_relevance_judgments.py",
            file=sys.stderr,
        )
        print(
            "Lalu isi grade 0–3 per toko, jalankan ulang perintah ini.",
            file=sys.stderr,
        )
        return 0

    if args.run_retrieval:
        rankings = _rankings_from_retrieval()
    elif args.snapshot and args.snapshot.is_file():
        rankings = _rankings_from_snapshot(args.snapshot)
    elif DEFAULT_SNAPSHOT.is_file():
        rankings = _rankings_from_snapshot(DEFAULT_SNAPSHOT)
    else:
        print("Butuh --snapshot atau --run-retrieval.", file=sys.stderr)
        return 1

    rows = []
    for qid, rel_map in rel_by_query.items():
        ranked = rankings.get(qid) or []
        row = {
            "query_id": qid,
            f"ndcg@{args.k}": round(ndcg_at_k(ranked, rel_map, args.k), 4),
            f"recall@{args.k}": round(recall_at_k(ranked, rel_map, args.k), 4),
            f"mrr@{args.k}": round(mrr_at_k(ranked, rel_map, args.k), 4),
            "ranked_count": len(ranked),
            "labeled_places": len(rel_map),
        }
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False))

    summary = {
        "queries_evaluated": len(rows),
        f"macro_ndcg@{args.k}": round(_macro_avg(r[f"ndcg@{args.k}"] for r in rows), 4),
        f"macro_recall@{args.k}": round(_macro_avg(r[f"recall@{args.k}"] for r in rows), 4),
        f"macro_mrr@{args.k}": round(_macro_avg(r[f"mrr@{args.k}"] for r in rows), 4),
    }
    print("--- summary ---")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

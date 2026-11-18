#!/usr/bin/env python
"""
Ablation gerbang aktivitas: (A) hard, (B) off, (C) rrf_list saja.

Metrik: Recall@k, nDCG@k (relevance_judgments.json), FNR gate (toko relevan grade>=1
yang ditolak shop_passes_activity_gate), distribusi skor dense.

Usage:
  python scripts/eval/build_eval_relevance_judgments.py
  python scripts/eval/activity_gate_ablation.py --judgments data/eval/relevance_judgments.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JUDGMENTS = ROOT / "data" / "eval" / "relevance_judgments.json"

VARIANTS = {
    "A_hard_gate": "hard",
    "B_no_gate": "off",
    "C_rrf_list_only": "rrf_list",
}


def _load_judgments(path: Path) -> Dict[str, Dict[str, float]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[str, Dict[str, float]] = {}
    for block in data.get("judgments") or []:
        qid = str(block.get("query_id") or "")
        if not qid:
            continue
        rel: Dict[str, float] = {}
        for row in block.get("labels") or []:
            pid = str(row.get("place_id") or "")
            if not pid:
                continue
            try:
                grade = float(row.get("grade"))
            except (TypeError, ValueError):
                continue
            rel[pid] = max(rel.get(pid, 0.0), grade)
        if rel:
            out[qid] = rel
    return out


def _import_metrics():
    _eval = ROOT / "scripts" / "eval"
    if str(_eval) not in sys.path:
        sys.path.insert(0, str(_eval))
    from relevance_metrics import ndcg_at_k, recall_at_k

    return ndcg_at_k, recall_at_k


def _precompute_query_caches(
    profiles: Sequence[dict],
    query_items: Sequence[dict],
) -> Tuple[Dict[str, dict], dict]:
    """Satu kali BM25+dense per query; dipakai ulang untuk semua varian ablation."""
    from hybrid_retrieval import (
        build_dense_query_text,
        build_sparse_query_tokens,
        compile_activity_matcher,
        score_bm25_for_hybrid_retrieval,
        score_shops_dense,
    )
    from pill_config import PILL_LABELS, PILL_MAPPING
    from query_expansion import free_text_expansion_tokens, pill_query_expansion_tokens
    from recommendation.pipeline import _split_preference_pills

    caches: Dict[str, dict] = {}
    all_scores: List[float] = []
    per_query_dist: List[dict] = []

    for item in query_items:
        qid = str(item.get("id") or "")
        route = item.get("route")
        inp = item.get("input") or {}
        if route not in ("pill", "free_text"):
            continue

        activity_pills: List[str] = []
        attribute_pills: List[str] = []
        pills: List[str] = []
        bm25_tokens: List[str] = []
        dense_text = ""
        dense_tokens: List[str] = []
        matcher: Any = None
        activity_tokens: List[str] = []

        if route == "pill":
            pills = list(inp.get("pills") or [])
            activity_pills, attribute_pills = _split_preference_pills(pills)
            query_tokens = build_sparse_query_tokens(
                pills, pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING,
            )
            matcher = (
                compile_activity_matcher(
                    activity_pills, pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING,
                )
                if activity_pills
                else None
            )
            activity_tokens = list((matcher or {}).get("bm25_tokens") or [])
            bm25_tokens = activity_tokens if activity_pills else query_tokens
            dense_text = (
                build_dense_query_text(
                    activity_pills, pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING,
                )
                if activity_pills
                else build_dense_query_text(
                    pills, pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING,
                )
            )
            dense_tokens = query_tokens
        else:
            from hybrid_retrieval import sparse_tokens_from_keywords

            raw_kw = [
                str(t).strip() for t in (inp.get("keywords_mock") or []) if str(t or "").strip()
            ]
            bm25_tokens = sparse_tokens_from_keywords(raw_kw)
            dense_text = inp.get("dense_query_mock") or inp.get("query_text") or ""
            dense_tokens = bm25_tokens

        if route == "pill":
            expansion = pill_query_expansion_tokens(
                activity_pills or pills, original_tokens=bm25_tokens,
            )
        else:
            expansion = free_text_expansion_tokens(
                {"keyword_expansions": inp.get("keyword_expansions_mock") or []},
                original_tokens=bm25_tokens,
            )
        bm25_raw, bm25_meta = score_bm25_for_hybrid_retrieval(
            profiles, bm25_tokens, expansion_tokens=expansion,
        )
        dense_raw, dense_telemetry = score_shops_dense(
            profiles,
            dense_text,
            query_tokens=dense_tokens,
            primary_tokens=activity_tokens if route == "pill" and activity_pills else dense_tokens,
            activity_matcher=matcher if activity_pills else None,
        )
        vals = sorted(float(v) for v in dense_raw.values())
        if vals:
            all_scores.extend(vals)
            per_query_dist.append({
                "query_id": qid,
                "min": round(vals[0], 4),
                "p50": round(vals[len(vals) // 2], 4),
                "p95": round(vals[int(0.95 * (len(vals) - 1))], 4),
                "max": round(vals[-1], 4),
            })

        caches[qid] = {
            "route": route,
            "input": inp,
            "pills": pills,
            "activity_pills": activity_pills,
            "attribute_pills": attribute_pills,
            "bm25_raw": bm25_raw,
            "dense_raw": dense_raw,
            "dense_telemetry": dense_telemetry,
            "bm25_meta": bm25_meta,
        }

    def _pct(vals: List[float], p: float) -> float:
        if not vals:
            return 0.0
        idx = min(len(vals) - 1, max(0, int(p * (len(vals) - 1))))
        return round(vals[idx], 4)

    sorted_all = sorted(all_scores)
    dense_dist = {
        "n_scores": len(sorted_all),
        "global_p5": _pct(sorted_all, 0.05),
        "global_p50": _pct(sorted_all, 0.5),
        "global_p95": _pct(sorted_all, 0.95),
        "activity_dense_min_env": os.getenv("COFIND_ACTIVITY_DENSE_MIN", "0.55"),
        "per_query": per_query_dist,
    }
    return caches, dense_dist


def _patch_retrieval_scores(cache: dict):
    bm25_raw = cache["bm25_raw"]
    dense_raw = cache["dense_raw"]

    def fake_bm25_retrieval(_profiles, _tokens, **_kwargs):
        return bm25_raw, cache.get("bm25_meta") or {}

    def fake_dense(*_args, **_kwargs):
        return (dense_raw, cache.get("dense_telemetry") or {"pool": "cached"})

    return (
        patch(
            "hybrid_retrieval.score_bm25_for_hybrid_retrieval",
            side_effect=fake_bm25_retrieval,
        ),
        patch("hybrid_retrieval.score_shops_dense", side_effect=fake_dense),
    )


def _gate_fnr(
    profiles_by_pid: Dict[str, dict],
    rel_map: Dict[str, float],
    *,
    activity_pills: List[str],
    pill_labels,
    pill_mapping,
    dense_by_pid: Dict[str, float],
) -> Tuple[float, int, int]:
    from hybrid_retrieval import (
        compile_activity_matcher,
        shop_passes_activity_gate,
    )

    if not activity_pills:
        return 0.0, 0, 0
    relevant = {pid for pid, g in rel_map.items() if g >= 1.0}
    if not relevant:
        return 0.0, 0, 0
    matcher = compile_activity_matcher(
        activity_pills, pill_labels=pill_labels, pill_mapping=pill_mapping,
    )
    tokens = list(matcher.get("bm25_tokens") or [])
    phrases = list(matcher.get("phrases") or [])
    rejected = 0
    for pid in relevant:
        profile = profiles_by_pid.get(pid) or {}
        passed, _ = shop_passes_activity_gate(
            profile.get("reviews") or [],
            tokens,
            phrases,
            matcher,
            dense_activity_score=float(dense_by_pid.get(pid) or 0.0),
            place_id=pid,
        )
        if not passed:
            rejected += 1
    return rejected / len(relevant), rejected, len(relevant)


def _run_variant(
    gate_mode: str,
    *,
    profiles: Sequence[dict],
    query_caches: Dict[str, dict],
    rel_by_query: Dict[str, Dict[str, float]],
    k_values: Sequence[int],
    top_k_retrieval: int,
) -> dict:
    from hybrid_retrieval import retrieve_top_k, retrieve_top_k_by_text
    from pill_config import PILL_LABELS, PILL_MAPPING

    os.environ["COFIND_ACTIVITY_GATE_MODE"] = gate_mode
    quality = {str(p.get("place_id")): 0.5 for p in profiles if p.get("place_id")}
    profiles_by_pid = {
        str(p.get("place_id")): p for p in profiles if p.get("place_id")
    }

    ndcg_at_k, recall_at_k = _import_metrics()
    per_query = []
    fnr_total_rej = 0
    fnr_total_rel = 0

    for qid, cache in query_caches.items():
        rel_map = rel_by_query.get(qid) or {}
        if not rel_map:
            continue
        route = cache["route"]
        inp = cache["input"]
        dense_by_pid: Dict[str, float] = dict(cache["dense_raw"])
        activity_pills: List[str] = list(cache.get("activity_pills") or [])

        print(f"  {qid} ({gate_mode})", flush=True)
        patches = _patch_retrieval_scores(cache)
        with patches[0], patches[1]:
            if route == "pill":
                pills = cache.get("pills") or []
                attribute = cache.get("attribute_pills") or []
                result = retrieve_top_k(
                    profiles,
                    pills,
                    pill_labels=PILL_LABELS,
                    pill_mapping=PILL_MAPPING,
                    quality_by_place=quality,
                    top_k=top_k_retrieval,
                    activity_pills=activity_pills,
                    attribute_pills=attribute,
                )
            elif route == "free_text":
                keywords = inp.get("keywords_mock") or []
                dense = inp.get("dense_query_mock") or inp.get("query_text") or ""
                result = retrieve_top_k_by_text(
                    profiles,
                    query_tokens=keywords,
                    dense_query_text=dense,
                    quality_by_place=quality,
                    top_k=top_k_retrieval,
                )
            else:
                continue

        ranked = [
            str(c.get("place_id") or "")
            for c in (result.get("candidates") or [])
            if c.get("place_id")
        ]
        row = {
            "query_id": qid,
            "route": route,
            "ranked_count": len(ranked),
            "telemetry": result.get("telemetry") or {},
        }
        for k in k_values:
            row[f"recall@{k}"] = round(recall_at_k(ranked, rel_map, k), 4)
            row[f"ndcg@{k}"] = round(ndcg_at_k(ranked, rel_map, k), 4)

        if route == "pill" and activity_pills:
            fnr, rej, rel_n = _gate_fnr(
                profiles_by_pid,
                rel_map,
                activity_pills=list(activity_pills),
                pill_labels=PILL_LABELS,
                pill_mapping=PILL_MAPPING,
                dense_by_pid=dense_by_pid,
            )
            row["gate_fnr"] = round(fnr, 4)
            row["gate_rejected_relevant"] = rej
            row["gate_relevant_total"] = rel_n
            fnr_total_rej += rej
            fnr_total_rel += rel_n
        per_query.append(row)

    summary = {"queries": len(per_query)}
    for k in k_values:
        summary[f"macro_recall@{k}"] = round(
            sum(r[f"recall@{k}"] for r in per_query) / max(1, len(per_query)), 4,
        )
        summary[f"macro_ndcg@{k}"] = round(
            sum(r[f"ndcg@{k}"] for r in per_query) / max(1, len(per_query)), 4,
        )
    if fnr_total_rel:
        summary["gate_fnr_relevant"] = round(fnr_total_rej / fnr_total_rel, 4)
        summary["gate_rejected_relevant"] = fnr_total_rej
        summary["gate_relevant_total"] = fnr_total_rel
    else:
        summary["gate_fnr_relevant"] = 0.0

    return {"summary": summary, "per_query": per_query}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--judgments", type=Path, default=DEFAULT_JUDGMENTS)
    parser.add_argument("--k", type=int, nargs="+", default=[7, 30])
    parser.add_argument("--top-k", type=int, default=30, help="COFIND_RETRIEVAL_TOP_K override")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "eval" / "activity_gate_ablation.json")
    args = parser.parse_args()

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    os.environ["COFIND_CROSS_ENCODER"] = "false"
    os.environ["COFIND_ABSA_ENABLED"] = "false"
    os.environ["COFIND_RETRIEVAL_TOP_K"] = str(args.top_k)
    os.environ.setdefault("COFIND_DENSE_USE_ANN", "false")
    os.environ.setdefault("COFIND_BM25_BACKEND", "memory")
    os.environ.setdefault("COFIND_REVIEW_ACTIVITY_INDEX", "false")

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")

    rel_by_query = _load_judgments(args.judgments)
    if not rel_by_query:
        print(
            "Judgments kosong. Jalankan: python scripts/eval/build_eval_relevance_judgments.py",
            file=sys.stderr,
        )
        return 1

    from facilities_store import load_facilities_index
    from recommendation.helpers import _build_profiles_for_recommendation, _load_all_place_ids

    _eval_dir = ROOT / "scripts" / "eval"
    if str(_eval_dir) not in sys.path:
        sys.path.insert(0, str(_eval_dir))
    from eval_queries_io import load_eval_queries

    query_items = load_eval_queries()
    place_ids = _load_all_place_ids()
    if not place_ids:
        print("DATABASE_URL / place kosong", file=sys.stderr)
        return 1

    facilities_index = load_facilities_index()
    profiles, _ = _build_profiles_for_recommendation(
        place_ids, facilities_index=facilities_index,
    )

    print("Precompute BM25+dense per query...", flush=True)
    query_caches, dense_dist = _precompute_query_caches(profiles, query_items)
    results = {
        "config": {
            "judgments": str(args.judgments.resolve().relative_to(ROOT.resolve())).replace("\\", "/"),
            "k_values": args.k,
            "retrieval_top_k": args.top_k,
            "variants": VARIANTS,
        },
        "dense_score_distribution": dense_dist,
        "variants": {},
    }

    for label, mode in VARIANTS.items():
        print(f"=== {label} (COFIND_ACTIVITY_GATE_MODE={mode}) ===", flush=True)
        block = _run_variant(
            mode,
            profiles=profiles,
            query_caches=query_caches,
            rel_by_query=rel_by_query,
            k_values=args.k,
            top_k_retrieval=args.top_k,
        )
        results["variants"][label] = block
        print(json.dumps(block["summary"], ensure_ascii=False, indent=2))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
"""
Bandingkan jalur retrieval: dense-only → (opsional CE rerank) vs hybrid RRF (BM25+dense).

Tujuan: ukur recall@k / nDCG@k pada judgments, lalu hitung miss dense yang
「diselamatkan」 leksikal (ulasan mengandung token query / BM25 top-k).

Urutan disarankan:
  1. python scripts/eval/build_eval_relevance_judgments.py
  2. python scripts/eval/dense_vs_hybrid_ablation.py
  3. python scripts/eval/dense_vs_hybrid_ablation.py --with-rerank  # butuh CE lokal

Usage:
  python scripts/eval/dense_vs_hybrid_ablation.py --k 7 30
  python scripts/eval/dense_vs_hybrid_ablation.py --out data/eval/dense_vs_hybrid.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JUDGMENTS = ROOT / "data" / "eval" / "relevance_judgments.json"
DEFAULT_OUT = ROOT / "data" / "eval" / "dense_vs_hybrid_ablation.json"


def _eval_path() -> Path:
    return ROOT / "scripts" / "eval"


def _import_metrics():
    _dir = _eval_path()
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))
    from relevance_metrics import ndcg_at_k, rank_place_ids_by_score, recall_at_k

    return ndcg_at_k, rank_place_ids_by_score, recall_at_k


def _load_judgments(path: Path) -> Dict[str, Dict[str, float]]:
    from activity_gate_ablation import _load_judgments as load_j

    return load_j(path)


def _sparse_tokens_for_cache(cache: dict) -> List[str]:
    from hybrid_retrieval import build_sparse_query_tokens, compile_activity_matcher
    from pill_config import PILL_LABELS, PILL_MAPPING

    route = cache.get("route")
    inp = cache.get("input") or {}
    if route == "pill":
        pills = list(cache.get("pills") or [])
        activity = list(cache.get("activity_pills") or [])
        if activity:
            matcher = compile_activity_matcher(
                activity, pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING,
            )
            tokens = list(matcher.get("bm25_tokens") or [])
            if tokens:
                return tokens
        return build_sparse_query_tokens(
            pills, pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING,
        )
    from hybrid_retrieval import sparse_tokens_from_keywords

    raw = [
        str(t).strip() for t in (inp.get("keywords_mock") or []) if str(t or "").strip()
    ]
    return sparse_tokens_from_keywords(raw)


def _shop_lexical_hit(profile: dict, tokens: Sequence[str]) -> bool:
    from hybrid_retrieval import review_text, text_matches_tokens

    if not tokens:
        return False
    for row in profile.get("reviews") or []:
        if text_matches_tokens(review_text(row), tokens):
            return True
    return False


def _analyze_dense_misses(
    *,
    dense_ranked: List[str],
    bm25_raw: Dict[str, float],
    rel_map: Dict[str, float],
    profiles_by_pid: Dict[str, dict],
    sparse_tokens: List[str],
    k: int,
    rank_by_score,
) -> dict:
    relevant = {pid for pid, g in rel_map.items() if g >= 1.0}
    if not relevant:
        return {
            "relevant_count": 0,
            "missed_at_k": 0,
            "missed_with_lexical_in_reviews": 0,
            "missed_in_bm25_top_k": 0,
            "missed_place_ids": [],
        }
    top_dense = set(dense_ranked[:k])
    bm25_ranked = rank_by_score(bm25_raw, max(k, 30))
    bm25_top = set(bm25_ranked[:k])
    missed = [pid for pid in relevant if pid not in top_dense]
    lexical = 0
    bm25_rescue = 0
    for pid in missed:
        profile = profiles_by_pid.get(pid) or {}
        if _shop_lexical_hit(profile, sparse_tokens):
            lexical += 1
        if pid in bm25_top:
            bm25_rescue += 1
    return {
        "relevant_count": len(relevant),
        "missed_at_k": len(missed),
        "missed_with_lexical_in_reviews": lexical,
        "missed_in_bm25_top_k": bm25_rescue,
        "missed_place_ids": missed[:12],
    }


def _metrics_row(
    qid: str,
    route: str,
    ranked: List[str],
    rel_map: Dict[str, float],
    k_values: Sequence[int],
    *,
    ndcg_at_k,
    recall_at_k,
    extra: dict | None = None,
) -> dict:
    row = {"query_id": qid, "route": route, "ranked_count": len(ranked)}
    if extra:
        row.update(extra)
    for k in k_values:
        row[f"recall@{k}"] = round(recall_at_k(ranked, rel_map, k), 4)
        row[f"ndcg@{k}"] = round(ndcg_at_k(ranked, rel_map, k), 4)
    return row


def _macro_summary(per_query: List[dict], k_values: Sequence[int]) -> dict:
    summary = {"queries": len(per_query)}
    for k in k_values:
        summary[f"macro_recall@{k}"] = round(
            sum(r.get(f"recall@{k}", 0.0) for r in per_query) / max(1, len(per_query)),
            4,
        )
        summary[f"macro_ndcg@{k}"] = round(
            sum(r.get(f"ndcg@{k}", 0.0) for r in per_query) / max(1, len(per_query)),
            4,
        )
    return summary


def _run_dense_bm25_lanes(
    *,
    query_caches: Dict[str, dict],
    rel_by_query: Dict[str, Dict[str, float]],
    profiles_by_pid: Dict[str, dict],
    k_values: Sequence[int],
    top_k: int,
    primary_k: int,
) -> Tuple[dict, dict, List[dict], List[dict]]:
    ndcg_at_k, rank_by_score, recall_at_k = _import_metrics()
    dense_rows: List[dict] = []
    bm25_rows: List[dict] = []
    miss_dense: List[dict] = []

    for qid, cache in query_caches.items():
        rel_map = rel_by_query.get(qid) or {}
        if not rel_map:
            continue
        dense_ranked = rank_by_score(cache["dense_raw"], top_k)
        bm25_ranked = rank_by_score(cache["bm25_raw"], top_k)
        sparse = _sparse_tokens_for_cache(cache)
        miss = _analyze_dense_misses(
            dense_ranked=dense_ranked,
            bm25_raw=cache["bm25_raw"],
            rel_map=rel_map,
            profiles_by_pid=profiles_by_pid,
            sparse_tokens=sparse,
            k=primary_k,
            rank_by_score=rank_by_score,
        )
        miss["query_id"] = qid
        miss["sparse_tokens_sample"] = sparse[:10]
        miss_dense.append(miss)

        dense_rows.append(
            _metrics_row(
                qid, cache["route"], dense_ranked, rel_map, k_values,
                ndcg_at_k=ndcg_at_k, recall_at_k=recall_at_k,
            ),
        )
        bm25_rows.append(
            _metrics_row(
                qid, cache["route"], bm25_ranked, rel_map, k_values,
                ndcg_at_k=ndcg_at_k, recall_at_k=recall_at_k,
            ),
        )

    return (
        {"summary": _macro_summary(dense_rows, k_values), "per_query": dense_rows},
        {"summary": _macro_summary(bm25_rows, k_values), "per_query": bm25_rows},
        miss_dense,
        dense_rows,
    )


def _run_hybrid_lane(
    *,
    profiles: Sequence[dict],
    query_caches: Dict[str, dict],
    rel_by_query: Dict[str, Dict[str, float]],
    k_values: Sequence[int],
    top_k: int,
) -> dict:
    from activity_gate_ablation import VARIANTS, _run_variant

    os.environ["COFIND_ACTIVITY_GATE_MODE"] = VARIANTS["C_rrf_list_only"]
    return _run_variant(
        VARIANTS["C_rrf_list_only"],
        profiles=profiles,
        query_caches=query_caches,
        rel_by_query=rel_by_query,
        k_values=k_values,
        top_k_retrieval=top_k,
    )


def _run_dense_ce_rerank(
    *,
    profiles: Sequence[dict],
    query_caches: Dict[str, dict],
    rel_by_query: Dict[str, Dict[str, float]],
    k_values: Sequence[int],
    top_k: int,
    pool_k: int,
) -> dict:
    from cross_encoder_rerank import ce_rerank_candidates
    from hybrid_retrieval import build_dense_query_text, compile_activity_matcher
    from pill_config import PILL_LABELS, PILL_MAPPING

    ndcg_at_k, rank_by_score, recall_at_k = _import_metrics()
    profiles_by_pid = {
        str(p.get("place_id")): p for p in profiles if p.get("place_id")
    }
    per_query: List[dict] = []

    for qid, cache in query_caches.items():
        rel_map = rel_by_query.get(qid) or {}
        if not rel_map:
            continue
        dense_ranked = rank_by_score(cache["dense_raw"], pool_k)
        candidates = []
        for pid in dense_ranked:
            profile = profiles_by_pid.get(pid)
            if not profile:
                continue
            candidates.append({
                "place_id": pid,
                "name": profile.get("name") or pid,
                "score": float(cache["dense_raw"].get(pid) or 0.0),
                "profile": profile,
                "evidence": {},
            })
        route = cache["route"]
        inp = cache.get("input") or {}
        pills = list(cache.get("pills") or [])
        activity = list(cache.get("activity_pills") or [])
        keyword_line = ""
        activity_query_text = ""
        activity_matcher = None
        activity_tokens: List[str] = []
        if route == "pill":
            activity_query_text = build_dense_query_text(
                activity or pills,
                pill_labels=PILL_LABELS,
                pill_mapping=PILL_MAPPING,
            )
            keyword_line = ", ".join(_sparse_tokens_for_cache(cache)[:12])
            if activity:
                activity_matcher = compile_activity_matcher(
                    activity, pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING,
                )
                activity_tokens = list(activity_matcher.get("bm25_tokens") or [])
        else:
            keyword_line = ", ".join(inp.get("keywords_mock") or [])
            activity_query_text = str(inp.get("dense_query_mock") or inp.get("query_text") or "")

        rerank = ce_rerank_candidates(
            candidates,
            pills if route == "pill" else [],
            pill_labels=PILL_LABELS,
            keyword_line=keyword_line,
            activity_pills=activity,
            activity_tokens=activity_tokens,
            activity_matcher=activity_matcher,
            activity_query_text=activity_query_text,
            max_candidates=pool_k,
        )
        ranked_list = (rerank or {}).get("ranked") if rerank else None
        if ranked_list:
            ranked = [
                str(c.get("place_id") or "")
                for c in ranked_list
                if c.get("place_id")
            ]
        else:
            ranked = dense_ranked[:top_k]

        per_query.append(
            _metrics_row(
                qid, route, ranked, rel_map, k_values,
                ndcg_at_k=ndcg_at_k, recall_at_k=recall_at_k,
                extra={"rerank_backend": (rerank or {}).get("telemetry", {}).get("backend")},
            ),
        )

    return {"summary": _macro_summary(per_query, k_values), "per_query": per_query}


def _interpretation(summary: dict, miss_rows: List[dict], primary_k: int) -> str:
    dense = summary.get("dense_only", {}).get("summary", {})
    hybrid = summary.get("hybrid_rrf", {}).get("summary", {})
    bm25 = summary.get("bm25_only", {}).get("summary", {})
    rk = f"macro_recall@{primary_k}"
    d_rec = dense.get(rk, 0.0)
    h_rec = hybrid.get(rk, 0.0)
    b_rec = bm25.get(rk, 0.0)
    total_missed = sum(int(r.get("missed_at_k") or 0) for r in miss_rows)
    lexical_missed = sum(int(r.get("missed_with_lexical_in_reviews") or 0) for r in miss_rows)
    bm25_on_miss = sum(int(r.get("missed_in_bm25_top_k") or 0) for r in miss_rows)
    lines = [
        f"Recall@{primary_k}: dense_only={d_rec}, bm25_only={b_rec}, hybrid_rrf={h_rec}.",
        f"Hybrid vs dense delta recall@{primary_k}: {round(h_rec - d_rec, 4)}.",
    ]
    if total_missed:
        lines.append(
            f"Toko relevan (grade≥1) terlewat dense@{primary_k}: {total_missed} "
            f"(dari {sum(r.get('relevant_count', 0) for r in miss_rows)} relevan per-query). "
            f"Di antaranya {lexical_missed} punya hit leksikal di ulasan; "
            f"{bm25_on_miss} masuk BM25 top-{primary_k}."
        )
        if lexical_missed >= total_missed * 0.25 and h_rec > d_rec:
            lines.append(
                "BM25/hybrid layak: miss dense sering disertai sinyal kata kunci di korpus."
            )
        elif h_rec <= d_rec + 0.02:
            lines.append(
                "Hybrid belum mengungguli dense pada set ini; cek gate/RRF atau perkaya judgments."
            )
    return " ".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ablation dense-only vs hybrid RRF.")
    parser.add_argument("--judgments", type=Path, default=DEFAULT_JUDGMENTS)
    parser.add_argument("--k", type=int, nargs="+", default=[7, 30])
    parser.add_argument("--top-k", type=int, default=30, help="Panjang ranking retrieval")
    parser.add_argument("--miss-k", type=int, default=7, help="k untuk analisis miss dense")
    parser.add_argument("--with-rerank", action="store_true", help="Lane dense pool + CE rerank")
    parser.add_argument("--rerank-pool", type=int, default=30)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    _dir = _eval_path()
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

    os.environ.setdefault("COFIND_CROSS_ENCODER", "false")
    os.environ.setdefault("COFIND_ABSA_ENABLED", "false")
    os.environ["COFIND_RETRIEVAL_TOP_K"] = str(args.top_k)
    os.environ.setdefault("COFIND_DENSE_USE_ANN", "false")
    os.environ.setdefault("COFIND_BM25_BACKEND", "memory")
    os.environ.setdefault("COFIND_REVIEW_ACTIVITY_INDEX", "false")
    os.environ.setdefault("COFIND_ACTIVITY_GATE_MODE", "rrf_list")

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")

    rel_by_query = _load_judgments(args.judgments)
    if not rel_by_query:
        print(
            "Judgments kosong. Jalankan: python scripts/eval/build_eval_relevance_judgments.py",
            file=sys.stderr,
        )
        return 1

    from activity_gate_ablation import _precompute_query_caches
    from eval_queries_io import load_eval_queries
    from facilities_store import load_facilities_index
    from recommendation.helpers import _build_profiles_for_recommendation, _load_all_place_ids

    query_items = load_eval_queries()
    place_ids = _load_all_place_ids()
    if not place_ids:
        print("DATABASE_URL / place kosong", file=sys.stderr)
        return 1

    facilities_index = load_facilities_index()
    profiles, _ = _build_profiles_for_recommendation(
        place_ids, facilities_index=facilities_index,
    )
    profiles_by_pid = {
        str(p.get("place_id")): p for p in profiles if p.get("place_id")
    }

    print("Precompute BM25+dense per query...", flush=True)
    query_caches, dense_dist = _precompute_query_caches(profiles, query_items)

    dense_block, bm25_block, miss_rows, _ = _run_dense_bm25_lanes(
        query_caches=query_caches,
        rel_by_query=rel_by_query,
        profiles_by_pid=profiles_by_pid,
        k_values=args.k,
        top_k=args.top_k,
        primary_k=args.miss_k,
    )

    print("=== hybrid_rrf (BM25+dense RRF, gate rrf_list) ===", flush=True)
    hybrid_block = _run_hybrid_lane(
        profiles=profiles,
        query_caches=query_caches,
        rel_by_query=rel_by_query,
        k_values=args.k,
        top_k=args.top_k,
    )

    variants = {
        "dense_only": dense_block,
        "bm25_only": bm25_block,
        "hybrid_rrf": hybrid_block,
    }

    if args.with_rerank:
        os.environ["COFIND_CROSS_ENCODER"] = "true"
        print("=== dense_pool + cross_encoder rerank ===", flush=True)
        variants["dense_ce_rerank"] = _run_dense_ce_rerank(
            profiles=profiles,
            query_caches=query_caches,
            rel_by_query=rel_by_query,
            k_values=args.k,
            top_k=args.top_k,
            pool_k=args.rerank_pool,
        )

    payload = {
        "config": {
            "judgments": str(args.judgments.relative_to(ROOT)).replace("\\", "/"),
            "eval_queries": "data/eval/eval_queries.json",
            "query_count": len(query_items),
            "k_values": args.k,
            "retrieval_top_k": args.top_k,
            "miss_analysis_k": args.miss_k,
            "relevant_threshold": "grade >= 1",
        },
        "dense_score_distribution": dense_dist,
        "dense_miss_analysis": miss_rows,
        "variants": {name: block["summary"] for name, block in variants.items()},
        "per_query": {name: block["per_query"] for name, block in variants.items()},
        "interpretation": _interpretation(variants, miss_rows, args.miss_k),
    }

    for name, block in variants.items():
        print(f"--- {name} ---")
        print(json.dumps(block["summary"], ensure_ascii=False, indent=2))

    print("--- interpretation ---")
    print(payload["interpretation"])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
"""Audit: seberapa redundant review_keywords vs dense-only untuk ranking Fase 2 (RRF)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
os.environ.setdefault("COFIND_CROSS_ENCODER", "false")
os.environ.setdefault("COFIND_SEMANTIC_GATE", "false")


def _top_place_ids(result: dict, k: int) -> list[str]:
    out = []
    for c in result.get("candidates") or []:
        pid = str(c.get("place_id") or "").strip()
        if pid:
            out.append(pid)
        if len(out) >= k:
            break
    return out


def _overlap(a: list[str], b: list[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    return len(sa & sb) / max(len(sa), len(sb))


def main() -> int:
    from facilities_store import load_facilities_index
    from hybrid_retrieval import (
        _hybrid_retrieve_rrf_core,
        build_dense_query_text,
        build_sparse_query_tokens,
        compile_activity_matcher,
        empty_activity_matcher,
        retrieve_top_k,
        retrieval_top_k,
    )
    from pill_config import FACILITY_ATTRIBUTE_PILLS, PILL_LABELS, PILL_MAPPING
    from recommendation.helpers import _build_profiles_for_recommendation, _load_all_place_ids

    place_ids = _load_all_place_ids()
    if not place_ids:
        print("DATABASE_URL / place kosong", file=sys.stderr)
        return 1

    facilities_index = load_facilities_index()
    profiles, _ = _build_profiles_for_recommendation(
        place_ids, facilities_index=facilities_index,
    )
    quality = {str(p.get("place_id")): 0.5 for p in profiles if p.get("place_id")}
    k = retrieval_top_k()

    def run_variant(pills: list[str], *, bm25_tokens, dense_text: str, apply_gate: bool):
        activity_list = [p for p in pills if p not in FACILITY_ATTRIBUTE_PILLS]
        attribute_list = [p for p in pills if p in FACILITY_ATTRIBUTE_PILLS]
        query_tokens = build_sparse_query_tokens(
            pills, pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING,
        )
        activity_matcher = (
            compile_activity_matcher(
                activity_list, pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING,
            )
            if activity_list
            else empty_activity_matcher()
        )
        activity_tokens = list(activity_matcher.get("bm25_tokens") or [])
        activity_query_text = (
            build_dense_query_text(
                activity_list, pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING,
            )
            if activity_list
            else dense_text
        )
        telemetry: dict = {}
        return _hybrid_retrieve_rrf_core(
            profiles,
            bm25_tokens=bm25_tokens,
            dense_query_text=dense_text,
            quality_by_place=quality,
            top_k=k,
            dense_query_tokens=query_tokens,
            dense_primary_tokens=activity_tokens or query_tokens,
            activity_matcher=activity_matcher if activity_list else None,
            query_tokens_out=query_tokens,
            query_text_out=dense_text,
            activity_tokens_out=activity_tokens,
            attribute_tokens_out=[],
            activity_query_text_out=activity_query_text,
            activity_matcher_out=activity_matcher,
            telemetry=telemetry,
            pills=pills,
            pill_labels=PILL_LABELS,
            pill_mapping=PILL_MAPPING,
            attribute_pills=attribute_list,
            activity_pills=activity_list,
            activity_tokens_for_gate=activity_tokens,
            activity_phrase_list=list(activity_matcher.get("phrases") or []),
            apply_activity_gate=apply_gate and bool(activity_list),
        )

    rows = []
    for pill in sorted(PILL_MAPPING.keys()):
        pills = [pill]
        spec = PILL_MAPPING.get(pill) or {}
        n_kw = len(spec.get("review_keywords") or [])
        has_def = bool((spec.get("definition") or "").strip())
        is_attr = pill in FACILITY_ATTRIBUTE_PILLS

        full = retrieve_top_k(
            profiles,
            pills,
            pill_labels=PILL_LABELS,
            pill_mapping=PILL_MAPPING,
            quality_by_place=quality,
            top_k=k,
            activity_pills=[p for p in pills if p not in FACILITY_ATTRIBUTE_PILLS],
            attribute_pills=[p for p in pills if p in FACILITY_ATTRIBUTE_PILLS],
        )
        dense_q = str(full.get("activity_query_text") or full.get("query_text") or "")
        act = [p for p in pills if p not in FACILITY_ATTRIBUTE_PILLS]
        qt = build_sparse_query_tokens(
            pills, pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING,
        )
        if act:
            am = compile_activity_matcher(
                act, pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING,
            )
            bm25_prod = list(am.get("bm25_tokens") or [])
        else:
            bm25_prod = qt

        dense_only = run_variant(
            pills,
            bm25_tokens=[],
            dense_text=dense_q,
            apply_gate=True,
        )
        bm25_only = run_variant(
            pills,
            bm25_tokens=bm25_prod,
            dense_text="",
            apply_gate=True,
        )

        top_full = _top_place_ids(full, k)
        top_dense = _top_place_ids(dense_only, k)
        top_bm25 = _top_place_ids(bm25_only, k)

        ov_fd = _overlap(top_full, top_dense)
        ov_fb = _overlap(top_full, top_bm25)
        ov_db = _overlap(top_dense, top_bm25)

        if ov_fd >= 0.86 and n_kw >= 5:
            tier = "redundant_rrf"
        elif ov_fd >= 0.57:
            tier = "partial"
        else:
            tier = "keywords_matter"

        if not has_def and is_attr:
            tier = tier + "_short_dense"

        rows.append(
            {
                "pill": pill,
                "type": "attribute" if is_attr else "activity",
                "keyword_count": n_kw,
                "has_definition": has_def,
                "dense_query_chars": len(dense_q),
                "overlap_full_dense": round(ov_fd, 3),
                "overlap_full_bm25": round(ov_fb, 3),
                "overlap_dense_bm25": round(ov_db, 3),
                "tier": tier,
                "top_full": top_full,
                "top_dense_only": top_dense,
            }
        )

    rows.sort(key=lambda r: (r["tier"], -r["overlap_full_dense"]))

    out = ROOT / "data" / "eval" / "pill_keyword_redundancy_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"top_k": k, "profiles": len(profiles), "pills": rows}, indent=2), encoding="utf-8")

    redundant = [r for r in rows if r["tier"].startswith("redundant_rrf")]
    partial = [r for r in rows if r["tier"] == "partial" or r["tier"].startswith("partial")]
    matter = [r for r in rows if r["tier"] == "keywords_matter" or r["tier"].startswith("keywords_matter")]

    print(f"Profiles={len(profiles)} top_k={k}")
    print(f"REDUNDANT_RRF (overlap full~dense >= 6/{k}): {len(redundant)}")
    for r in redundant:
        print(f"  - {r['pill']} ({r['type']}) kw={r['keyword_count']} ov={r['overlap_full_dense']}")
    print(f"PARTIAL: {len(partial)}")
    for r in partial:
        print(f"  - {r['pill']} ov_fd={r['overlap_full_dense']} ov_fb={r['overlap_full_bm25']}")
    print(f"KEYWORDS_MATTER: {len(matter)}")
    for r in matter:
        print(f"  - {r['pill']} ov_fd={r['overlap_full_dense']} dense_chars={r['dense_query_chars']}")
    print(f"JSON: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

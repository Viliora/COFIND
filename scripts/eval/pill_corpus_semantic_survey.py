#!/usr/bin/env python
"""
Survei semantik review (DB) ↔ pill: cosine E5 antara dense_query pill
dan embedding ulasan (pgvector / cache), ambang = COFIND_SEMANTIC_THRESHOLD.

Bandingkan dengan hit leksikal (pill_corpus_survey) dan usulkan pill aktivitas
kandidat yang belum ada di pill_config.

Usage:
  set COFIND_EMBEDDING_STORE=pgvector
  python scripts/eval/pill_corpus_semantic_survey.py
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

# Pill aktivitas kandidat (belum di PILL_MAPPING) — dense_query gaya ulasan Pontianak
CANDIDATE_ACTIVITY_PILLS: Dict[str, dict] = {
    "live_music_akustik": {
        "label": "Live music/Akustik",
        "dense_query": "ada live music atau akustik, suasananya seru buat dengerin musik",
        "rationale": "Beberapa ulasan menyebut musik live; beda dari pill tenang/kerja.",
    },
    "kencan_pacaran": {
        "label": "Kencan/Pacaran",
        "dense_query": "cocok buat kencan atau date night berdua, romantis dan nyaman",
        "rationale": "Intent couple — jarang keyword eksplisit tapi muncul parafrase di review panjang.",
    },
    "kunjungan_singkat": {
        "label": "Grab-and-go / takeaway",
        "dense_query": "cocok buat mampir sebentar takeaway atau grab and go tanpa duduk lama",
        "rationale": "Melengkapi negative_scope Kerja/WFC; validasi intent kunjungan singkat.",
    },
    "event_komunitas": {
        "label": "Event/Komunitas",
        "dense_query": "sering ada acara komunitas workshop atau gathering di sini",
        "rationale": "Workshop/komunitas ≠ rapat kantor (meeting_sosialisasi).",
    },
}


def _pct(n: int, total: int) -> float:
    return round(100.0 * n / total, 2) if total else 0.0


def load_reviews() -> List[dict]:
    from db_backend import get_connection

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, place_id, review_text, COALESCE(review_source, 'unknown')
            FROM reviews
            WHERE review_text IS NOT NULL
            ORDER BY id
            """
        )
        out = []
        for rid, pid, text, src in cur.fetchall():
            t = str(text or "").strip()
            if len(t) >= 8:
                out.append(
                    {
                        "review_id": int(rid),
                        "place_id": str(pid or ""),
                        "text": t,
                        "source": str(src or ""),
                    }
                )
        return out
    finally:
        conn.close()


def _review_vectors(reviews: Sequence[dict]) -> Tuple[List[int], Any]:
    """Return (review_ids aligned, matrix float32 [n, dim])."""
    import numpy as np

    from review_embedding_store import (
        canonical_embedding_text,
        fetch_embeddings,
        model_name as stored_model_name,
        source_text_hash,
        upsert_review_embedding,
        use_pgvector_store,
    )
    from semantic_match import embed_texts, model_available

    if not model_available():
        raise RuntimeError("Model embedding tidak tersedia")

    ids: List[int] = []
    vecs: List[Any] = []
    expected = stored_model_name()

    if use_pgvector_store():
        fetched = fetch_embeddings([r["review_id"] for r in reviews])
    else:
        fetched = {}

    for r in reviews:
        rid = r["review_id"]
        raw = r["text"]
        canon = canonical_embedding_text(raw)
        if len(canon) < 6:
            continue
        vec = None
        th = source_text_hash(canon)
        hit = fetched.get(rid)
        if hit and hit[1] == th and hit[2] == expected:
            vec = hit[0]
        if vec is None:
            one = embed_texts([canon])
            vec = one.get(canon)
            if vec is not None and use_pgvector_store():
                upsert_review_embedding(rid, raw)
        if vec is None:
            continue
        ids.append(rid)
        vecs.append(np.asarray(vec, dtype=np.float32).reshape(-1))
    if not vecs:
        return [], None
    mat = np.vstack(vecs)
    return ids, mat


def _pill_query_vector(pill_key: str, mapping: Dict[str, dict], labels: Dict[str, str]):
    import numpy as np

    from hybrid_retrieval import build_dense_query_text
    from semantic_match import embed_query_vector

    qtext = build_dense_query_text(
        [pill_key], pill_labels=labels, pill_mapping=mapping,
    )
    q, _ = embed_query_vector(qtext)
    if q is None:
        return None, qtext
    return np.asarray(q, dtype=np.float32).reshape(-1), qtext


def survey_semantic(
    reviews: Sequence[dict],
    *,
    threshold: float,
    max_samples: int = 6,
) -> dict[str, Any]:
    import numpy as np

    from pill_config import FACILITY_ATTRIBUTE_PILLS, PILL_LABELS, PILL_MAPPING
    from scripts.eval.pill_corpus_survey import (
        activity_pill_keys,
        attribute_pill_keys,
        build_activity_matchers,
        match_activity_review,
        match_attribute_review,
    )
    from semantic_match import similarity_threshold

    thresh = threshold if threshold > 0 else similarity_threshold()
    merged_mapping = dict(PILL_MAPPING)
    merged_labels = dict(PILL_LABELS)
    for key, spec in CANDIDATE_ACTIVITY_PILLS.items():
        merged_mapping[key] = spec
        merged_labels[key] = spec.get("label", key)

    activity_existing = activity_pill_keys()
    attribute_existing = attribute_pill_keys()
    all_pills = list(PILL_MAPPING.keys()) + list(CANDIDATE_ACTIVITY_PILLS.keys())

    id_list, mat = _review_vectors(reviews)
    if mat is None or len(id_list) == 0:
        return {"error": "no_review_vectors", "threshold": thresh}

    rid_to_review = {r["review_id"]: r for r in reviews}
    matchers = build_activity_matchers()

    per_pill: Dict[str, dict] = {}
    best_pill_per_review: Dict[int, Tuple[str, float]] = {}

    for pill in all_pills:
        q, qtext = _pill_query_vector(pill, merged_mapping, merged_labels)
        if q is None:
            continue
        sims = mat @ q
        kind = (
            "candidate_activity"
            if pill in CANDIDATE_ACTIVITY_PILLS
            else (
                "activity"
                if pill in activity_existing
                else "attribute"
            )
        )
        hit_ids: List[int] = []
        samples: List[dict] = []
        shop_ids: set = set()
        lexical_ids: set = set()

        for idx, rid in enumerate(id_list):
            sim = float(sims[idx])
            if sim >= thresh:
                hit_ids.append(rid)
                rev = rid_to_review[rid]
                shop_ids.add(rev["place_id"])
                if len(samples) < max_samples:
                    samples.append(
                        {
                            "review_id": rid,
                            "place_id": rev["place_id"],
                            "cosine": round(sim, 4),
                            "excerpt": rev["text"][:320],
                        }
                    )
            prev = best_pill_per_review.get(rid)
            if prev is None or sim > prev[1]:
                best_pill_per_review[rid] = (pill, sim)

        for r in reviews:
            rid = r["review_id"]
            if rid not in id_list:
                continue
            if kind == "activity":
                if match_activity_review(r["text"], pill, matchers[pill]):
                    lexical_ids.add(rid)
            elif kind == "attribute":
                if match_attribute_review(r["text"], pill):
                    lexical_ids.add(rid)
            elif kind == "candidate_activity":
                pass

        sem_only = [i for i in hit_ids if i not in lexical_ids]
        both = [i for i in hit_ids if i in lexical_ids]
        n_vec = len(id_list)
        per_pill[pill] = {
            "pill_key": pill,
            "pill_label": merged_labels.get(pill, pill),
            "pill_kind": kind,
            "dense_query": qtext,
            "threshold": thresh,
            "reviews_with_embedding": n_vec,
            "semantic_hits": len(hit_ids),
            "pct_semantic": _pct(len(hit_ids), n_vec),
            "lexical_hits": len(lexical_ids),
            "pct_lexical": _pct(len(lexical_ids), n_vec),
            "semantic_only_hits": len(sem_only),
            "both_lex_and_sem": len(both),
            "shops_semantic": len(shop_ids),
            "sample_semantic": samples,
        }

    # Aktivitas: review tanpa leksikal existing tapi semantik kuat ke kandidat
    existing_activity_set = set(activity_existing)
    candidate_rank = []
    for pill, spec in CANDIDATE_ACTIVITY_PILLS.items():
        row = per_pill.get(pill) or {}
        candidate_rank.append(
            (
                pill,
                row.get("semantic_hits", 0),
                row.get("semantic_only_hits", 0),
                spec.get("rationale", ""),
            )
        )
    candidate_rank.sort(key=lambda x: (-x[1], -x[2]))

    def _has_existing_activity_semantic(rid: int) -> bool:
        for p in activity_existing:
            row = per_pill.get(p) or {}
            if rid in {s["review_id"] for s in row.get("sample_semantic") or []}:
                return True
        return False

    # Recompute: any existing activity semantic hit
    existing_act_sem: set = set()
    for p in activity_existing:
        q, _ = _pill_query_vector(p, merged_mapping, merged_labels)
        if q is None:
            continue
        sims = mat @ q
        for idx, rid in enumerate(id_list):
            if float(sims[idx]) >= thresh:
                existing_act_sem.add(rid)

    existing_act_lex: set = set()
    for r in reviews:
        for p in activity_existing:
            if match_activity_review(r["text"], p, matchers[p]):
                existing_act_lex.add(r["review_id"])

    uplift_reviews = []
    for idx, rid in enumerate(id_list):
        if rid in existing_act_lex:
            continue
        if rid not in existing_act_sem:
            continue
        pill, sim = best_pill_per_review.get(rid, ("", 0.0))
        if pill in existing_activity_set:
            uplift_reviews.append(
                {
                    "review_id": rid,
                    "best_existing_activity": pill,
                    "cosine": round(sim, 4),
                    "excerpt": rid_to_review[rid]["text"][:280],
                }
            )

    recommendations = []
    for pill, sem_hits, sem_only, rationale in candidate_rank:
        if sem_hits < 3:
            tier = "low_evidence"
        elif sem_only >= 5:
            tier = "strong_add"
        elif sem_hits >= 8:
            tier = "consider_add"
        else:
            tier = "monitor"
        recommendations.append(
            {
                "pill_key": pill,
                "label": CANDIDATE_ACTIVITY_PILLS[pill]["label"],
                "semantic_hits": sem_hits,
                "semantic_only_hits": sem_only,
                "tier": tier,
                "rationale": rationale,
            }
        )

    existing_activity_summary = [
        {
            "pill": p,
            "label": per_pill[p]["pill_label"],
            "semantic": per_pill[p]["semantic_hits"],
            "lexical": per_pill[p]["lexical_hits"],
            "semantic_only": per_pill[p]["semantic_only_hits"],
            "pct_semantic": per_pill[p]["pct_semantic"],
        }
        for p in activity_existing
        if p in per_pill
    ]
    existing_activity_summary.sort(key=lambda x: -x["semantic"])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "threshold": thresh,
        "reviews_usable": len(reviews),
        "reviews_with_vectors": len(id_list),
        "methodology": {
            "encoder": "COFIND_EMBEDDING_MODEL (E5 query/passage via embed_query_vector + pgvector)",
            "pill_text": "build_dense_query_text per pill (dense_query)",
            "threshold_env": "COFIND_SEMANTIC_THRESHOLD",
        },
        "existing_activity_summary": existing_activity_summary,
        "candidate_recommendations": recommendations,
        "semantic_uplift_over_lexical": {
            "count": len(uplift_reviews),
            "description": "Ulasan tanpa hit leksikal aktivitas, tapi cosine ≥ ambang ke pill aktivitas existing",
            "samples": uplift_reviews[:max_samples],
        },
        "per_pill": per_pill,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default=str(ROOT / "data" / "eval" / "pill_corpus_semantic_survey.json"),
    )
    parser.add_argument("--threshold", type=float, default=0.0)
    parser.add_argument("--max-samples", type=int, default=6)
    args = parser.parse_args()

    reviews = load_reviews()
    report = survey_semantic(
        reviews,
        threshold=args.threshold,
        max_samples=max(1, args.max_samples),
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Threshold: {report.get('threshold')}")
    print(f"Reviews: {report.get('reviews_usable')} (vectors: {report.get('reviews_with_vectors')})")
    print("\n=== Aktivitas existing (sem / lex / sem-only) ===")
    for row in report.get("existing_activity_summary") or []:
        print(
            f"  {row['label']}: sem={row['semantic']} lex={row['lexical']} "
            f"sem_only={row['semantic_only']} ({row['pct_semantic']}%)"
        )
    print("\n=== Rekomendasi pill aktivitas baru ===")
    for rec in report.get("candidate_recommendations") or []:
        print(
            f"  [{rec['tier']}] {rec['label']}: sem={rec['semantic_hits']} "
            f"sem_only={rec['semantic_only_hits']} — {rec['rationale'][:70]}..."
        )
    uplift = report.get("semantic_uplift_over_lexical") or {}
    print(f"\nUplift semantik vs leksikal (aktivitas existing): {uplift.get('count')} ulasan")
    print(f"Written: {out}")
    return 0 if "error" not in report else 1


if __name__ == "__main__":
    raise SystemExit(main())

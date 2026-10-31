#!/usr/bin/env python
"""
Survei traceability: seberapa banyak ulasan di DB menyebut setiap pill (bukti leksikal).

Metode aktivitas = sama dengan gerbang admisi pipeline:
  compile_activity_matcher + activity_text_score + extract_activity_support_text
  (pill_config.review_keywords + hybrid_retrieval _ACTIVITY_EXTRA_PHRASES / WHOLE_WORDS).

Metode atribut/fasilitas = pill_aspect_sentiment (keyword + bukan negasi eksplisit).

Keluaran JSON untuk lampiran penelitian / pengujian validitas pill.

Usage:
  python scripts/eval/pill_corpus_survey.py
  python scripts/eval/pill_corpus_survey.py --out data/eval/pill_corpus_survey.json
  python scripts/eval/pill_corpus_survey.py --max-samples 5
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

MIN_REVIEW_CHARS = 8


def activity_pill_keys() -> List[str]:
    from pill_config import FACILITY_ATTRIBUTE_PILLS, PILL_MAPPING

    return [k for k in PILL_MAPPING if k not in FACILITY_ATTRIBUTE_PILLS]


def attribute_pill_keys() -> List[str]:
    from pill_config import FACILITY_ATTRIBUTE_PILLS

    return sorted(FACILITY_ATTRIBUTE_PILLS)


def build_activity_matchers() -> Dict[str, dict]:
    from hybrid_retrieval import compile_activity_matcher
    from pill_config import PILL_LABELS, PILL_MAPPING

    out: Dict[str, dict] = {}
    for pill in activity_pill_keys():
        out[pill] = compile_activity_matcher(
            [pill],
            pill_labels=PILL_LABELS,
            pill_mapping=PILL_MAPPING,
        )
    return out


def match_activity_review(text: str, pill: str, matcher: dict) -> Optional[dict]:
    from hybrid_retrieval import (
        activity_text_score,
        extract_activity_support_text,
        text_has_activity_signal,
    )

    body = str(text or "").strip()
    if len(body) < MIN_REVIEW_CHARS:
        return None
    if not text_has_activity_signal(body, matcher):
        return None
    score = float(activity_text_score(body, matcher))
    support = extract_activity_support_text(body, matcher) or body[:280]
    return {
        "pill": pill,
        "layer": "activity_gate",
        "score": round(score, 3),
        "support_excerpt": support[:400],
    }


def match_attribute_review(text: str, pill: str) -> Optional[dict]:
    from pill_aspect_sentiment import review_sentiment_for_pill
    from pill_config import PILL_MAPPING
    from review_weakness import text_matches_any_keyword
    from pill_aspect_sentiment import expand_pill_keywords

    body = str(text or "").strip()
    if len(body) < MIN_REVIEW_CHARS:
        return None
    keywords = expand_pill_keywords(pill, PILL_MAPPING)
    if not text_matches_any_keyword(body, keywords):
        return None
    sent = review_sentiment_for_pill(body, pill, PILL_MAPPING, preference_keywords=keywords)
    if sent == "negative":
        return None
    return {
        "pill": pill,
        "layer": "attribute_keyword",
        "sentiment": sent,
        "support_excerpt": body[:400],
    }


def _pct(n: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(100.0 * n / total, 2)


def survey_all_reviews(
    rows: Sequence[tuple],
    *,
    max_samples: int = 8,
) -> dict[str, Any]:
    """
    rows: (review_id, place_id, review_text, source optional)
    """
    from pill_config import PILL_LABELS

    matchers = build_activity_matchers()
    activity_pills = activity_pill_keys()
    attribute_pills = attribute_pill_keys()

    usable = []
    for row in rows:
        rid, pid, text = row[0], row[1], row[2]
        t = str(text or "").strip()
        if len(t) >= MIN_REVIEW_CHARS:
            usable.append(
                {
                    "review_id": rid,
                    "place_id": pid,
                    "text": t,
                    "source": row[3] if len(row) > 3 else None,
                }
            )

    total = len(usable)
    by_id = {r["review_id"]: r for r in usable}

    per_pill: Dict[str, dict] = {}
    review_hits: Dict[int, List[str]] = {r["review_id"]: [] for r in usable}

    for pill in activity_pills:
        hit_ids: List[int] = []
        samples: List[dict] = []
        shop_ids: set = set()
        for r in usable:
            m = match_activity_review(r["text"], pill, matchers[pill])
            if not m:
                continue
            hit_ids.append(r["review_id"])
            shop_ids.add(r["place_id"])
            review_hits[r["review_id"]].append(pill)
            if len(samples) < max_samples:
                samples.append(
                    {
                        "review_id": r["review_id"],
                        "place_id": r["place_id"],
                        "score": m["score"],
                        "excerpt": m["support_excerpt"],
                    }
                )
        n = len(hit_ids)
        per_pill[pill] = {
            "pill_key": pill,
            "pill_label": PILL_LABELS.get(pill, pill),
            "pill_kind": "activity",
            "reviews_mentioning": n,
            "reviews_total": total,
            "pct_reviews": _pct(n, total),
            "shops_with_evidence": len(shop_ids),
            "match_method": "activity_gate (lexical+frasa khas, sama pipeline hybrid)",
            "sample_evidence": samples,
        }

    for pill in attribute_pills:
        hit_ids = []
        samples = []
        shop_ids = set()
        positive_only = 0
        for r in usable:
            m = match_attribute_review(r["text"], pill)
            if not m:
                continue
            hit_ids.append(r["review_id"])
            shop_ids.add(r["place_id"])
            review_hits[r["review_id"]].append(pill)
            if m.get("sentiment") == "positive":
                positive_only += 1
            if len(samples) < max_samples:
                samples.append(
                    {
                        "review_id": r["review_id"],
                        "place_id": r["place_id"],
                        "sentiment": m.get("sentiment"),
                        "excerpt": m["support_excerpt"],
                    }
                )
        n = len(hit_ids)
        per_pill[pill] = {
            "pill_key": pill,
            "pill_label": PILL_LABELS.get(pill, pill),
            "pill_kind": "attribute",
            "reviews_mentioning": n,
            "reviews_mentioning_positive_keyword": positive_only,
            "reviews_total": total,
            "pct_reviews": _pct(n, total),
            "shops_with_evidence": len(shop_ids),
            "match_method": "review_keywords + pill_aspect_sentiment (exclude explicit negative)",
            "sample_evidence": samples,
        }

    multi = sum(1 for pills in review_hits.values() if len(pills) > 1)
    any_activity = set()
    for pill in activity_pills:
        for r in usable:
            if match_activity_review(r["text"], pill, matchers[pill]):
                any_activity.add(r["review_id"])

    no_pill = [rid for rid, pills in review_hits.items() if not pills]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "corpus": {
            "reviews_in_db": len(rows),
            "reviews_usable_min_chars": total,
            "reviews_matching_any_activity_pill": len(any_activity),
            "pct_any_activity": _pct(len(any_activity), total),
            "reviews_matching_any_pill": total - len(no_pill),
            "reviews_multi_pill": multi,
            "reviews_no_pill_match": len(no_pill),
        },
        "activity_pills_summary": [
            {
                "pill": p,
                "label": per_pill[p]["pill_label"],
                "x": per_pill[p]["reviews_mentioning"],
                "y": total,
                "pct": per_pill[p]["pct_reviews"],
                "shops": per_pill[p]["shops_with_evidence"],
            }
            for p in activity_pills
        ],
        "per_pill": per_pill,
        "methodology": {
            "activity": "hybrid_retrieval.compile_activity_matcher per pill (keywords + extra phrases)",
            "attribute": "pill_aspect_sentiment.review_sentiment_for_pill; hits count non-negative keyword mention",
            "note": "Satu ulasan bisa menghitung di beberapa pill. Dense/semantic gate tidak termasuk (hanya bukti leksikal traceable).",
        },
    }


def load_reviews_from_db() -> List[tuple]:
    from db_backend import get_connection

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, place_id, review_text, COALESCE(review_source, 'unknown')
            FROM reviews
            WHERE review_text IS NOT NULL
            """
        )
        return list(cur.fetchall())
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        type=str,
        default=str(ROOT / "data" / "eval" / "pill_corpus_survey.json"),
    )
    parser.add_argument("--max-samples", type=int, default=8)
    args = parser.parse_args()

    rows = load_reviews_from_db()
    report = survey_all_reviews(rows, max_samples=max(1, args.max_samples))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    corp = report["corpus"]
    print(f"Reviews usable: {corp['reviews_usable_min_chars']} / {corp['reviews_in_db']}")
    print("--- Aktivitas (x dari y ulasan, %) ---")
    for row in report["activity_pills_summary"]:
        print(
            f"  {row['label']}: {row['x']}/{row['y']} = {row['pct']}% "
            f"({row['shops']} toko)"
        )
    print(f"Written: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

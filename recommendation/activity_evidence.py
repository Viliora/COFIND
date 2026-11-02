"""
Bukti aktivitas tunggal: matcher, skor, kutipan, kontradiksi.

Wrap hybrid_retrieval — leksikon tetap di activity_lexicon.json.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from hybrid_retrieval import (
    activity_text_score,
    compile_activity_matcher,
    extract_activity_support_text,
    review_text,
    shop_has_activity_signal,
    text_has_activity_signal,
    text_rejects_requested_activity,
)


def compile_matcher(
    activity_pills: Sequence[str],
    *,
    pill_labels: Optional[Dict[str, str]] = None,
    pill_mapping: Optional[Dict[str, dict]] = None,
) -> dict:
    return compile_activity_matcher(
        activity_pills,
        pill_labels=pill_labels,
        pill_mapping=pill_mapping,
    )


def score_support(text: str, matcher: Optional[dict]) -> float:
    return activity_text_score(text, matcher)


def extract_support(
    text: str,
    matcher: Optional[dict],
    activity_tokens: Optional[Sequence[str]] = None,
) -> str:
    return extract_activity_support_text(
        text, matcher=matcher, activity_tokens=activity_tokens,
    )


def text_has_support(text: str, matcher: Optional[dict]) -> bool:
    return text_has_activity_signal(text, matcher)


def shop_has_support(
    reviews: Sequence[object],
    activity_tokens: Sequence[str],
    *,
    matcher: Optional[dict] = None,
    place_id: Optional[str] = None,
) -> bool:
    tokens = list(matcher.get('bm25_tokens') or []) if matcher else list(activity_tokens or [])
    return shop_has_activity_signal(
        reviews,
        tokens,
        activity_matcher=matcher,
        place_id=place_id,
    )


def shop_has_contradiction(
    reviews: Sequence[object],
    matcher: Optional[dict],
    activity_tokens: Optional[Sequence[str]] = None,
) -> bool:
    if not matcher:
        return False
    tokens = list(activity_tokens or [])
    for row in reviews or []:
        text = review_text(row)
        if not text:
            continue
        if text_rejects_requested_activity(text, matcher, activity_tokens=tokens):
            return True
    return False

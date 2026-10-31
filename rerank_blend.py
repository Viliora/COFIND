"""Utilitas pencampuran skor Fase 3 (cross-encoder rerank)."""

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Sequence

from hybrid_retrieval import extract_activity_support_text


def _env_int(name: str, default: int, *, min_value: int, max_value: int) -> int:
    raw = (os.getenv(name) or '').strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(min_value, min(max_value, value))


def rerank_candidate_pool() -> int:
    """Jumlah kandidat dinilai cross-encoder (default 7)."""
    return _env_int('COFIND_CE_RERANK_CANDIDATES', 7, min_value=2, max_value=20)


def blend_rerank_scores(
    pool: Sequence[Dict[str, object]],
    fits: Dict[str, Dict[str, object]],
    *,
    telemetry: Dict[str, object],
    weight: Optional[float] = None,
    default_weight: float = 0.6,
) -> Dict[str, object]:
    """Campur fit rerank (0–10) dengan skor hybrid lalu urutkan."""
    w = default_weight if weight is None else max(0.0, min(1.0, float(weight)))
    ranked: List[Dict[str, object]] = []
    for position, candidate in enumerate(pool):
        place_id = str(candidate.get('place_id'))
        hybrid_score = float(candidate.get('score') or 0.0)
        fit = fits.get(place_id)
        entry = dict(candidate)
        if fit is None:
            entry['final_score'] = round(hybrid_score, 4)
            entry['llm_fit'] = None
        else:
            blended = w * (float(fit.get('fit_score') or 0.0) / 10.0) + (1.0 - w) * hybrid_score
            entry['final_score'] = round(blended, 4)
            entry['llm_fit'] = dict(fit, hybrid_score=round(hybrid_score, 4))
        entry['hybrid_rank'] = position + 1
        ranked.append(entry)

    ranked.sort(key=lambda item: (-(item.get('final_score') or 0.0), item.get('hybrid_rank') or 0))
    for position, entry in enumerate(ranked, 1):
        entry['llm_rank'] = position
        if isinstance(entry.get('llm_fit'), dict):
            entry['llm_fit']['rank'] = position
            entry['llm_fit']['hybrid_rank'] = entry['hybrid_rank']

    return {
        'ranked': ranked,
        'fits': fits,
        'telemetry': dict(
            telemetry,
            weight=w,
            order_changed=any(entry['llm_rank'] != entry['hybrid_rank'] for entry in ranked),
        ),
    }


def matched_pills_from_stats(candidate: Dict[str, object], valid_pills: set) -> List[str]:
    """Pill dengan bukti keyword di review kandidat (pill_stats)."""
    matched = []
    for stat in ((candidate.get('evidence') or {}).get('pill_stats') or []):
        if not isinstance(stat, dict):
            continue
        pill = str(stat.get('pill') or '').strip().lower()
        if pill in valid_pills and pill not in matched and (stat.get('keyword_review_hits') or 0) > 0:
            matched.append(pill)
    return matched


def quote_candidates_for_prompt(
    evidence: Dict[str, object],
    *,
    limit: int,
    quote_chars: int,
    activity_matcher: Optional[dict] = None,
    activity_tokens: Optional[Sequence[str]] = None,
) -> List[Dict[str, object]]:
    """Kutipan review untuk satu kandidat — utamakan bukti aktivitas."""
    ordered_keys = (
        'review_quotes',
        'positive_review_quotes',
        'negative_review_quotes',
        'search_keyword_matches',
        'semantic_matches',
    )
    quotes: List[Dict[str, object]] = []
    seen = set()
    for key in ordered_keys:
        for row in (evidence or {}).get(key) or []:
            if not isinstance(row, dict):
                continue
            text = re.sub(r'\s+', ' ', str(row.get('quote') or row.get('text') or '')).strip()
            if len(text) < 6:
                continue
            dedupe_key = re.sub(r'\s+', ' ', text).strip().lower()
            if not dedupe_key or dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            if len(text) > quote_chars:
                text = text[: quote_chars - 3].rstrip() + '...'
            support = extract_activity_support_text(
                text, activity_matcher, activity_tokens,
            )
            quotes.append({
                'text': text,
                'rating': row.get('rating'),
                'activity_support': bool(support),
            })
    quotes.sort(key=lambda row: int(bool(row.get('activity_support'))), reverse=True)
    return quotes[:limit]

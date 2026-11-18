"""
Statistik keyword / semantic untuk evidence UI — bukan skor ranking (RRF).

Ranking Fase 2 hanya dari hybrid_retrieval (BM25 + dense → RRF).
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence, Set

from pill_config import FACILITY_ATTRIBUTE_PILLS, PILL_LABELS, PILL_MAPPING


def _coverage_semantic_min() -> float:
    raw = (os.getenv('COFIND_COVERAGE_SEMANTIC_MIN') or '').strip()
    if not raw:
        return 0.65
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        return 0.65


def build_evidence_keyword_detail(
    profile: dict,
    pills: Sequence[str],
    *,
    search_keywords: Optional[Sequence[str]] = None,
) -> dict:
    """
    Hitung per_pill_stats, kutipan keyword, opsional semantic gate untuk evidence.
    Tidak mengubah skor retrieval.
    """
    from recommendation.helpers import (
        _expand_pill_to_keywords,
        _filter_overbroad_meeting_keywords,
        _has_semantic_family_signal,
        _light_keyword_phrase_list,
        _matches_keyword_phrase,
        _pick_keyword_matched_reviews,
        _pick_semantic_matched_reviews,
        _preference_keywords_for_evidence,
        _review_quote_detail_fields,
        _review_rating_category_scores,
        _semantic_reference_terms,
        _semantic_term_owner_pills,
        _truncate_evidence_text,
    )
    from recommendation.wiring import ensure_recommendation_wiring

    ensure_recommendation_wiring()
    from recommendation.helpers import _quote_is_caveat  # after wiring

    from semantic_match import semantic_gate_enabled

    _PROMPT_EVIDENCE_CHAR_LIMIT = 320

    reviews = profile.get('reviews') or []
    review_count = len(reviews)
    pill_list = list(pills or [])
    search_keywords = _filter_overbroad_meeting_keywords(
        _light_keyword_phrase_list(search_keywords or []),
        pill_list,
    )

    empty = {
        'per_pill_stats': {},
        'expanded_keyword_matches': [],
        'search_keywords': search_keywords,
        'category_detail': {},
        'semantic_matches': [],
        'semantic_telemetry': {},
        'covered_pills': [],
        'uncovered_pills': list(pill_list),
        'review_count': review_count,
    }
    if review_count == 0 or not pill_list:
        return empty

    per_pill_stats: Dict[str, dict] = {}
    lexical_matched_ids: Set[int] = set()

    for pill in pill_list:
        keywords = _expand_pill_to_keywords(pill)
        keyword_review_hits = 0
        sample_quotes: List[dict] = []

        for review_idx, review in enumerate(reviews):
            text = (review.get('text') or '').strip()
            matched_terms: List[str] = []
            if text:
                matched_terms = [kw for kw in keywords if _matches_keyword_phrase(text, kw)]
                if pill == 'keluarga' and not matched_terms:
                    has_family_signal, _ = _has_semantic_family_signal(text)
                    if has_family_signal:
                        matched_terms = ['kebersamaan keluarga']
                if matched_terms:
                    keyword_review_hits += 1
                    lexical_matched_ids.add(review_idx)

            if matched_terms and text and len(text) >= 15 and len(sample_quotes) < 3:
                sample_quotes.append({
                    'quote': _truncate_evidence_text(text, _PROMPT_EVIDENCE_CHAR_LIMIT),
                    'rating': review.get('rating'),
                    'username': review.get('username') or review.get('full_name'),
                    'matched_terms': matched_terms,
                    **_review_quote_detail_fields(review),
                })

        kw_norm = min(1.0, keyword_review_hits / max(1, min(review_count, 5)))
        per_pill_stats[pill] = {
            'pill': pill,
            'pill_label': PILL_LABELS.get(pill, pill),
            'keyword_review_hits': keyword_review_hits,
            'review_count': review_count,
            'keyword_score': round(kw_norm, 4),
            'sample_quotes': sample_quotes,
        }

    _, category_detail = _review_rating_category_scores(reviews, pill_list)
    expanded_keyword_matches = _pick_keyword_matched_reviews(
        reviews, search_keywords, limit=3,
    )

    semantic_matches: List[dict] = []
    semantic_telemetry: dict = {}
    if semantic_gate_enabled():
        unmatched = [
            review for idx, review in enumerate(reviews)
            if idx not in lexical_matched_ids and (review.get('text') or '').strip()
        ]
        if unmatched:
            semantic_matches, semantic_telemetry = _pick_semantic_matched_reviews(
                unmatched,
                _semantic_reference_terms(pill_list, search_keywords),
                limit=3,
            )

    pref_kws = _preference_keywords_for_evidence(pill_list, search_keywords)

    def _is_supporting_quote(row: object) -> bool:
        text = str((row or {}).get('quote') or '')
        return len(text.strip()) >= 10 and not _quote_is_caveat(text, pref_kws)

    semantic_owners = _semantic_term_owner_pills(pill_list)
    covered_pills: Set[str] = set()
    for pill in pill_list:
        quotes = (per_pill_stats.get(pill) or {}).get('sample_quotes') or []
        if any(_is_supporting_quote(sq) for sq in quotes):
            covered_pills.add(pill)
    semantic_min = _coverage_semantic_min()
    for match in semantic_matches:
        if not _is_supporting_quote(match):
            continue
        try:
            match_confidence = float(match.get('semantic_score') or 0.0)
        except (TypeError, ValueError):
            match_confidence = 0.0
        if match_confidence < semantic_min:
            continue
        for term in match.get('matched_terms') or []:
            owner = semantic_owners.get(str(term or '').strip().lower())
            if owner:
                covered_pills.add(owner)

    return {
        'per_pill_stats': per_pill_stats,
        'expanded_keyword_matches': expanded_keyword_matches,
        'search_keywords': search_keywords,
        'category_detail': category_detail,
        'semantic_matches': semantic_matches,
        'semantic_telemetry': semantic_telemetry,
        'covered_pills': sorted(covered_pills),
        'uncovered_pills': [p for p in pill_list if p not in covered_pills],
        'review_count': review_count,
    }


def _score_shop_by_user_reviews(
    profile,
    pills,
    search_keywords=None,
    bm25_norm=None,
    bm25_raw=None,
):
    """Alias legacy: evidence stats saja (bm25_* diabaikan — ranking dari RRF)."""
    _ = bm25_norm, bm25_raw
    return build_evidence_keyword_detail(
        profile, pills, search_keywords=search_keywords,
    )

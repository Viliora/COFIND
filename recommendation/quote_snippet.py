"""Kutipan modal: klausa relevan + batas panjang seragam untuk API dan UI."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence

from hybrid_retrieval import (
    extract_activity_support_text,
    lexical_review_score,
    text_has_activity_signal,
    _sentence_has_rejection_phrase,
)
from semantic_match import split_clauses

# Sama dengan frontend-cofind/src/constants/evidenceQuotes.js
MODAL_QUOTE_CHAR_LIMIT = 280


def truncate_modal_quote(text: object, limit: int = MODAL_QUOTE_CHAR_LIMIT) -> str:
    cleaned = re.sub(r'\s+', ' ', str(text or '')).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + '...'


def _score_clause(
    clause: str,
    *,
    activity_matcher: Optional[dict],
    activity_tokens: Optional[Sequence[str]],
    preference_keywords: Sequence[str],
    match_keyword,
) -> float:
    score = 0.0
    if activity_matcher and activity_matcher.get('pills'):
        if text_has_activity_signal(clause, activity_matcher):
            score += 3.0
    elif activity_tokens and lexical_review_score(clause, activity_tokens) > 0:
        score += 2.0
    for kw in preference_keywords or []:
        k = str(kw or '').strip()
        if k and match_keyword(clause, k):
            score += 2.0
    return score


def snippet_for_modal_quote(
    text: object,
    *,
    activity_matcher: Optional[dict] = None,
    activity_tokens: Optional[Sequence[str]] = None,
    preference_keywords: Optional[Sequence[str]] = None,
) -> str:
    """
    Ambil satu klausa/snippet dari ulasan untuk tampilan modal (bukan ulasan penuh).
    """
    from recommendation.helpers import _matches_keyword_phrase, _normalize_whitespace

    raw = _normalize_whitespace(text)
    if not raw:
        return ''

    keywords = [str(k).strip() for k in (preference_keywords or []) if str(k).strip()]
    clauses = split_clauses(raw) or [raw]

    activity_span = ''
    if activity_matcher or activity_tokens:
        activity_span = (
            extract_activity_support_text(raw, activity_matcher, activity_tokens) or ''
        ).strip()
        if activity_span:
            sub_clauses = split_clauses(activity_span) or [activity_span]
            if len(sub_clauses) == 1:
                return truncate_modal_quote(sub_clauses[0])
            clauses = sub_clauses

    scored: List[tuple] = []
    for clause in clauses:
        clause = clause.strip()
        if len(clause) < 6:
            continue
        if _sentence_has_rejection_phrase(clause):
            sc = _score_clause(
                clause,
                activity_matcher=activity_matcher,
                activity_tokens=activity_tokens,
                preference_keywords=keywords,
                match_keyword=_matches_keyword_phrase,
            )
            if sc <= 0:
                continue
        sc = _score_clause(
            clause,
            activity_matcher=activity_matcher,
            activity_tokens=activity_tokens,
            preference_keywords=keywords,
            match_keyword=_matches_keyword_phrase,
        )
        scored.append((sc, clause))

    if scored:
        scored.sort(key=lambda item: (-item[0], -len(item[1])))
        return truncate_modal_quote(scored[0][1])

    for clause in clauses:
        if not _sentence_has_rejection_phrase(clause):
            return truncate_modal_quote(clause)
    return truncate_modal_quote(clauses[0])


def _preference_keywords(pills, search_keywords=None):
    from recommendation.helpers import (
        _expand_pill_to_keywords,
        _light_keyword_phrase_list,
    )

    preference_keywords = []
    for pill in pills or []:
        preference_keywords.extend(_expand_pill_to_keywords(pill))
    preference_keywords.extend(_light_keyword_phrase_list(search_keywords or []))
    return list(dict.fromkeys(preference_keywords))


def apply_snippet_to_quote_row(
    row: dict,
    *,
    activity_matcher: Optional[dict] = None,
    activity_tokens: Optional[Sequence[str]] = None,
    preference_keywords: Optional[Sequence[str]] = None,
) -> dict:
    if not isinstance(row, dict):
        return row
    out = dict(row)
    quote = str(out.get('quote') or out.get('text') or '').strip()
    if not quote:
        return out
    prefs = list(preference_keywords or [])
    if not prefs and out.get('matched_terms'):
        prefs = [str(t).strip() for t in (out.get('matched_terms') or []) if str(t).strip()]
    out['quote'] = snippet_for_modal_quote(
        quote,
        activity_matcher=activity_matcher,
        activity_tokens=activity_tokens,
        preference_keywords=prefs,
    )
    out.pop('text', None)
    return out


_QUOTE_LIST_KEYS = (
    'modal_display_quotes',
    'modal_caveat_quotes',
    'review_quotes',
    'positive_review_quotes',
    'negative_review_quotes',
    'search_keyword_matches',
    'semantic_matches',
)


def normalize_evidence_quotes_for_modal(
    evidence: Optional[dict],
    *,
    pills=None,
    search_keywords=None,
    activity_matcher: Optional[dict] = None,
    activity_tokens: Optional[Sequence[str]] = None,
) -> dict:
    """Pastikan semua kutipan di evidence berupa snippet dengan panjang seragam."""
    ev = dict(evidence or {})
    pref_kw = _preference_keywords(pills, search_keywords)
    for key in _QUOTE_LIST_KEYS:
        rows = ev.get(key)
        if not isinstance(rows, list):
            continue
        ev[key] = [
            apply_snippet_to_quote_row(
                row,
                activity_matcher=activity_matcher,
                activity_tokens=activity_tokens,
                preference_keywords=pref_kw,
            )
            for row in rows
            if isinstance(row, dict)
        ]
    return ev
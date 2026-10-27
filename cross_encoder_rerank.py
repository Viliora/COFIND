"""Rerank kandidat Fase 3 via Jina cross-encoder (lokal)."""

from __future__ import annotations

import os
import re
import time
from typing import Dict, List, Optional, Sequence

from cross_encoder import cross_encoder_enabled, score_pairs
from hybrid_retrieval import extract_activity_support_text, min_fit_score, review_text, text_rejects_requested_activity
from llm_recommender import (
    _blend_rerank_scores,
    _matched_pills_from_stats,
    _quote_candidates_for_prompt,
    rerank_candidate_pool,
    rerank_weight,
)

logger = __import__('logging_config', fromlist=['get_logger']).get_logger('recommend')


def _env_flag(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or '').strip().lower()
    if not raw:
        return default
    return raw in ('1', 'true', 'yes', 'on')


def ce_rerank_enabled() -> bool:
    if not _env_flag('COFIND_CE_RERANK', True):
        return False
    return cross_encoder_enabled()


def ce_rerank_weight() -> float:
    raw = (os.getenv('COFIND_CE_RERANK_WEIGHT') or os.getenv('COFIND_LLM_RERANK_WEIGHT') or '0.6').strip()
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        return 0.6


def ce_rerank_min_raw_score() -> float:
    raw = (os.getenv('COFIND_CE_RERANK_MIN_SCORE') or '-2').strip()
    try:
        return float(raw)
    except ValueError:
        return -2.0


def _build_query_text(
    *,
    activity_query_text: str,
    keyword_line: str,
    pill_labels: Dict[str, str],
    activity_pills: Sequence[str],
) -> str:
    parts = []
    act = str(activity_query_text or '').strip()
    if act:
        parts.append(act)
    labels = [str(pill_labels.get(p, p)) for p in (activity_pills or []) if p]
    if labels:
        parts.append(', '.join(labels))
    kw = str(keyword_line or '').strip()
    if kw:
        parts.append(kw[:400])
    return ' — '.join(p for p in parts if p) or 'coffee shop cocok preferensi'


def _short_reason(text: str, *, max_words: int = 18) -> str:
    words = re.sub(r'\s+', ' ', str(text or '')).strip().split()
    if not words:
        return 'cocok dengan preferensi'
    snippet = ' '.join(words[:max_words])
    if len(words) > max_words:
        snippet += '…'
    return snippet


def _normalize_scores(raw_scores: List[float]) -> List[float]:
    if not raw_scores:
        return []
    lo = min(raw_scores)
    hi = max(raw_scores)
    if hi - lo < 1e-6:
        mid = max(0.0, min(10.0, (hi + 1.0) * 5.0))
        return [mid] * len(raw_scores)
    return [max(0.0, min(10.0, 10.0 * (s - lo) / (hi - lo))) for s in raw_scores]


def ce_rerank_candidates(
    candidates: Sequence[Dict[str, object]],
    pills: Sequence[str],
    *,
    pill_labels: Dict[str, str],
    user_taste_block: str = '',
    keyword_line: str = '',
    max_candidates: Optional[int] = None,
    quotes_per_candidate: int = 6,
    quote_chars: int = 280,
    cached_fits: Optional[Dict[str, Dict[str, object]]] = None,
    activity_pills: Optional[Sequence[str]] = None,
    activity_tokens: Optional[Sequence[str]] = None,
    activity_matcher: Optional[dict] = None,
    activity_query_text: str = '',
    **kwargs,
) -> Optional[Dict[str, object]]:
    _ = user_taste_block, kwargs
    if not candidates or not ce_rerank_enabled():
        return None

    pool_size = max_candidates if max_candidates is not None else rerank_candidate_pool()
    pool = list(candidates)[:pool_size]
    if not pool:
        return None

    pool_place_ids = {str(c.get('place_id')) for c in pool if c.get('place_id')}
    reusable_fits = {
        place_id: fit
        for place_id, fit in (cached_fits or {}).items()
        if place_id in pool_place_ids and isinstance(fit, dict)
    }
    if reusable_fits:
        return _blend_rerank_scores(
            pool,
            reusable_fits,
            telemetry={
                'backend': 'cache',
                'candidates': len(pool),
                'scored_by_ce': 0,
                'scored_from_cache': len(reusable_fits),
                'latency_ms': 0.0,
            },
            weight=ce_rerank_weight(),
        )

    query = _build_query_text(
        activity_query_text=activity_query_text,
        keyword_line=keyword_line,
        pill_labels=pill_labels,
        activity_pills=activity_pills or pills,
    )
    act_tokens = list(activity_tokens or [])
    activity_required = bool(
        act_tokens or (activity_matcher and activity_matcher.get('pills'))
    )
    min_raw = ce_rerank_min_raw_score()
    started = time.perf_counter()
    fits: Dict[str, Dict[str, object]] = dict(reusable_fits)

    for candidate in pool:
        place_id = str(candidate.get('place_id') or '')
        if not place_id or place_id in fits:
            continue
        quotes = _quote_candidates_for_prompt(
            candidate.get('evidence') or {},
            limit=quotes_per_candidate,
            quote_chars=quote_chars,
            activity_matcher=activity_matcher,
            activity_tokens=act_tokens,
        )
        texts = [str(q.get('text') or '') for q in quotes if str(q.get('text') or '').strip()]
        if not texts:
            for row in (candidate.get('profile') or {}).get('reviews') or []:
                raw = review_text(row)
                if len(raw) >= 12:
                    texts.append(raw[:quote_chars])
                if len(texts) >= quotes_per_candidate:
                    break

        if not texts:
            fits[place_id] = {
                'fit_score': 0.0,
                'reason': 'tidak ada kutipan',
                'evidence_quote': '',
                'caveat_quote': '',
                'selected': False,
                'matched_pills': _matched_pills_from_stats(candidate, set(pills or [])),
            }
            continue

        raw_scores = score_pairs(query, texts)
        if not raw_scores or len(raw_scores) != len(texts):
            fits[place_id] = {
                'fit_score': float(candidate.get('score') or 0) * 10.0,
                'reason': _short_reason(texts[0]),
                'evidence_quote': texts[0],
                'caveat_quote': '',
                'selected': True,
                'matched_pills': _matched_pills_from_stats(candidate, set(pills or [])),
            }
            continue

        norm = _normalize_scores(raw_scores)
        ranked_idx = sorted(range(len(texts)), key=lambda i: raw_scores[i], reverse=True)
        best_i = ranked_idx[0]
        best_text = texts[best_i]
        best_raw = raw_scores[best_i]
        fit_score = norm[best_i]

        activity_supported = True
        if activity_required:
            span = extract_activity_support_text(best_text, activity_matcher, act_tokens)
            if span:
                best_text = span
            else:
                activity_supported = False
                for idx in ranked_idx:
                    alt = texts[idx]
                    span = extract_activity_support_text(alt, activity_matcher, act_tokens)
                    if span:
                        best_text = span
                        fit_score = norm[idx]
                        best_raw = raw_scores[idx]
                        activity_supported = True
                        break

        caveat_quote = ''
        if activity_required and text_rejects_requested_activity(
            best_text, activity_matcher, act_tokens,
        ):
            activity_supported = False

        for idx in reversed(ranked_idx):
            if raw_scores[idx] <= min_raw:
                continue
            t = texts[idx]
            if text_rejects_requested_activity(t, activity_matcher, act_tokens):
                caveat_quote = t
                break

        selected = best_raw >= min_raw
        corpus_floor = min(min_fit_score(), 4.0)
        if activity_required and not activity_supported:
            selected = False
            fit_score = min(fit_score, 3.0)
        elif activity_required and activity_supported:
            selected = True
            fit_score = max(fit_score, corpus_floor)

        fits[place_id] = {
            'fit_score': round(fit_score, 2),
            'reason': _short_reason(best_text),
            'evidence_quote': best_text,
            'evidence_grounded': True,
            'caveat_quote': caveat_quote,
            'selected': selected,
            'matched_pills': _matched_pills_from_stats(candidate, set(pills or [])),
        }

    if not fits:
        return {
            'ranked': None,
            'telemetry': {
                'backend': 'cross_encoder_failed',
                'error': 'no_fits',
                'latency_ms': round((time.perf_counter() - started) * 1000, 1),
            },
        }

    return _blend_rerank_scores(
        pool,
        fits,
        telemetry={
            'backend': 'cross_encoder',
            'candidates': len(pool),
            'scored_by_ce': len(fits),
            'latency_ms': round((time.perf_counter() - started) * 1000, 1),
        },
        weight=ce_rerank_weight(),
    )

"""Triase klausa (bi-encoder + cross-encoder) sebelum ABSA — tanpa LLM."""

from __future__ import annotations

import os
from typing import Dict, List, Sequence, Tuple

from semantic_triage import tau_high, tau_low, triage_clause


def _env_flag(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or '').strip().lower()
    if not raw:
        return default
    return raw in ('1', 'true', 'yes', 'on')


def clause_triage_enabled() -> bool:
    return _env_flag('COFIND_CLAUSE_TRIAGE', True)


def bi_encoder_scores(preference_line: str, clauses: Sequence[str]) -> Dict[str, float]:
    from semantic_match import _clean_clause, embed_texts
    import numpy as np

    pref = str(preference_line or '').strip()
    items = [str(c).strip() for c in clauses if str(c).strip()]
    if not pref or not items:
        return {}
    pref_key = _clean_clause(pref)
    q_map = embed_texts([pref], role='query')
    pref_vec = q_map.get(pref_key)
    if pref_vec is None:
        return {}
    p_map = embed_texts(items, role='passage')
    pv = np.asarray(pref_vec, dtype=np.float32)
    out: Dict[str, float] = {}
    for clause in items:
        key = _clean_clause(clause)
        vec = p_map.get(key)
        if vec is None:
            continue
        out[clause] = float(np.dot(pv, np.asarray(vec, dtype=np.float32)))
    return out


def apply_clause_triage(
    pending: List[str],
    preference_line: str,
    telemetry: Dict[str, object],
) -> Tuple[List[str], Dict[str, dict]]:
    """Kurangi beban ABSA via bi-encoder + cross-encoder triase."""
    from cross_encoder import cross_encoder_enabled, score_pairs

    if not pending:
        return [], {}
    if not clause_triage_enabled():
        return list(pending), {}

    bi_scores = bi_encoder_scores(preference_line, pending)
    auto: Dict[str, dict] = {}
    need_absa: List[str] = []
    ambiguous: List[str] = []
    lo, hi = tau_low(), tau_high()
    for clause in pending:
        bi = bi_scores.get(clause)
        if bi is not None and bi < lo:
            auto[clause] = {'relevant': False, 'sentiment': 'netral', 'source': 'triaged_reject'}
            telemetry['triaged_reject'] = int(telemetry.get('triaged_reject') or 0) + 1
            continue
        if bi is not None and bi >= hi:
            need_absa.append(clause)
            telemetry['triaged_relevant_absa'] = int(telemetry.get('triaged_relevant_absa') or 0) + 1
            continue
        ambiguous.append(clause)

    cross_scores: Dict[str, float] = {}
    if ambiguous and cross_encoder_enabled():
        scores = score_pairs(preference_line, ambiguous)
        if scores and len(scores) == len(ambiguous):
            cross_scores = dict(zip(ambiguous, scores))
            telemetry['cross_encoder_scored'] = len(cross_scores)

    for clause in ambiguous:
        decision = triage_clause(bi_scores.get(clause), cross_scores.get(clause))
        if decision == 'accept':
            need_absa.append(clause)
            telemetry['triaged_relevant_absa'] = int(telemetry.get('triaged_relevant_absa') or 0) + 1
        elif decision == 'reject':
            auto[clause] = {'relevant': False, 'sentiment': 'netral', 'source': 'triaged_reject'}
            telemetry['triaged_reject'] = int(telemetry.get('triaged_reject') or 0) + 1
        else:
            need_absa.append(clause)
            telemetry['triaged_absa'] = int(telemetry.get('triaged_absa') or 0) + 1

    return need_absa, auto

"""Triase accept / reject / needs_llm untuk pasangan (aspek, klausa)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal, Optional

TriageDecision = Literal['accept', 'reject', 'needs_llm']


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or '').strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def tau_low() -> float:
    return _env_float('COFIND_TAU_LOW', _threshold_from_file('tau_low', 0.35))


def tau_high() -> float:
    return _env_float('COFIND_TAU_HIGH', _threshold_from_file('tau_high', 0.72))


def _threshold_from_file(key: str, default: float) -> float:
    path = Path(os.getenv('COFIND_THRESHOLD_FILE') or 'data/eval/thresholds.json')
    if not path.is_file():
        return default
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        val = data.get(key)
        return float(val) if val is not None else default
    except Exception:
        return default


def triage_clause(
    bi_encoder_score: Optional[float],
    cross_encoder_score: Optional[float],
) -> TriageDecision:
    """
    Gunakan cross-encoder bila ada; jika tidak, bi-encoder saja.
    Di pita ambigu (tau_low..tau_high) butuh LLM kecuali cross score jelas.
    """
    score = cross_encoder_score if cross_encoder_score is not None else bi_encoder_score
    if score is None:
        return 'needs_llm'
    lo, hi = tau_low(), tau_high()
    if score >= hi:
        return 'accept'
    if score < lo:
        return 'reject'
    if cross_encoder_score is not None:
        return 'needs_llm'
    return 'needs_llm'

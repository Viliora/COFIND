"""Agregasi rating dengan prior (Bayesian) untuk sampel kecil."""

from __future__ import annotations

import math
from typing import Optional


def bayesian_average(
    raw: float,
    count: int,
    *,
    prior_mean: float = 4.0,
    prior_weight: int = 10,
) -> float:
    """Mean posterior dengan prior Gaussian-like (prior_weight pseudo-count)."""
    n = max(0, int(count or 0))
    if n <= 0:
        return float(prior_mean)
    return (prior_weight * prior_mean + n * float(raw)) / (prior_weight + n)


def rating_to_unit_score(raw: float, *, floor: float = 3.0, ceiling: float = 5.0) -> float:
    """Map rating 1–5 ke [0, 1]; di bawah floor → 0."""
    span = max(1e-6, ceiling - floor)
    return max(0.0, min(1.0, (float(raw) - floor) / span))


def bayesian_rating_unit_score(
    raw: Optional[float],
    count: int,
    *,
    prior_mean: float = 4.0,
    prior_weight: int = 10,
    floor: float = 3.0,
) -> Optional[float]:
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    smoothed = bayesian_average(value, count, prior_mean=prior_mean, prior_weight=prior_weight)
    return round(rating_to_unit_score(smoothed, floor=floor), 4)


def wilson_lower_bound(positive: float, total: int, z: float = 1.96) -> float:
    """Wilson score interval (lower bound) untuk proporsi positif."""
    n = max(0, int(total or 0))
    if n <= 0:
        return 0.0
    p = max(0.0, min(1.0, float(positive) / n))
    z2 = z * z
    denom = 1.0 + z2 / n
    centre = p + z2 / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n)
    return max(0.0, (centre - margin) / denom)

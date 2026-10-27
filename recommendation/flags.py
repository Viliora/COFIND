"""Feature flags pipeline rekomendasi (env, tanpa import berat)."""

from __future__ import annotations

import os


def recommendation_overall_experience_enabled() -> bool:
    """
    Overall Experience (slider shop_votes) dalam ranking/prompt rekomendasi.
    Default: false — matikan sampai dievaluasi ulang.
    """
    raw = (os.getenv('COFIND_RECOMMEND_USE_OVERALL_EXPERIENCE') or 'false').strip().lower()
    return raw in ('1', 'true', 'yes', 'on')

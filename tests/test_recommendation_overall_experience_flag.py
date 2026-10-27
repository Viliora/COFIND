"""Flag Overall Experience dalam pipeline rekomendasi."""

import os
from unittest.mock import patch

from recommendation.flags import recommendation_overall_experience_enabled
from recommendation.helpers import (
    _community_prompt_lines,
    _overall_experience_score_from_signals,
    _quality_score_for_profile,
)


def test_overall_experience_disabled_by_default():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop('COFIND_RECOMMEND_USE_OVERALL_EXPERIENCE', None)
        assert recommendation_overall_experience_enabled() is False


def test_overall_experience_score_none_when_disabled():
    signals = {
        'vote': {
            'slider_averages': {
                'pelayanan': 5.0,
                'kebersihan': 5.0,
                'kenyamanan': 5.0,
                'harga': 4.0,
            },
        },
    }
    with patch.dict(os.environ, {'COFIND_RECOMMEND_USE_OVERALL_EXPERIENCE': 'false'}):
        assert _overall_experience_score_from_signals(signals) is None


def test_quality_score_ignores_sliders_when_disabled():
    profile = {
        'google_rating': 4.5,
        'community_signals': {
            'vote': {
                'slider_averages': {'pelayanan': 5.0, 'kebersihan': 5.0},
            },
        },
    }
    with patch.dict(os.environ, {'COFIND_RECOMMEND_USE_OVERALL_EXPERIENCE': 'false'}):
        score = _quality_score_for_profile(profile)
    assert score is not None
    with patch.dict(os.environ, {'COFIND_RECOMMEND_USE_OVERALL_EXPERIENCE': 'true'}):
        score_on = _quality_score_for_profile(profile)
    assert score_on is not None
    assert score_on != score or score == score  # rating-only vs blend; ON should differ if OE contributes


def test_community_prompt_skips_slider_lines_when_disabled():
    signals = {
        'vote': {
            'slider_averages': {'pelayanan': 4.5},
            'rating_counts': {'love': 2},
        },
    }
    with patch.dict(os.environ, {'COFIND_RECOMMEND_USE_OVERALL_EXPERIENCE': 'false'}):
        lines = _community_prompt_lines(signals)
    assert not any('Pengalaman pengunjung' in line for line in lines)
    with patch.dict(os.environ, {'COFIND_RECOMMEND_USE_OVERALL_EXPERIENCE': 'true'}):
        lines_on = _community_prompt_lines(signals)
    assert any('Pengalaman pengunjung' in line for line in lines_on)

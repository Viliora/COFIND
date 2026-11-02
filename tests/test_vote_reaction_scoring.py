"""Rating toko untuk ablation; vote komunitas tidak memengaruhi skor."""

from recommendation.helpers import (
    _coffee_shop_rating_score,
    _combined_shop_rating_signal,
    _quality_score_for_profile,
    _vote_reaction_unit_score,
)


def test_vote_reaction_unit_score_weighted():
    score = _vote_reaction_unit_score({'love': 2, 'like': 0, 'ok': 0, 'dislike': 0, 'hate': 0})
    assert score == 1.0
    mixed = _vote_reaction_unit_score({'love': 1, 'hate': 1})
    assert mixed == 0.5


def test_shop_rating_signal_ignores_community_vote():
    profile = {
        'google_rating': 5.0,
        'google_total_reviews': 100,
        'community_signals': {
            'vote': {
                'rating_counts': {'love': 2, 'like': 0, 'ok': 0, 'dislike': 0, 'hate': 0},
            },
        },
    }
    star_only = _coffee_shop_rating_score(profile)
    assert star_only is not None
    assert _combined_shop_rating_signal(profile) == star_only
    assert _quality_score_for_profile(profile) == star_only

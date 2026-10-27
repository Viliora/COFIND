"""Pastikan wiring modul rekomendasi mengekspor simbol internal pipeline."""

from __future__ import annotations

import unittest


class RecommendationWiringTests(unittest.TestCase):
    def test_helpers_evidence_cross_symbols(self):
        from recommendation.wiring import ensure_recommendation_wiring

        ensure_recommendation_wiring()
        import recommendation.helpers as h
        import recommendation.evidence as e

        self.assertTrue(callable(getattr(h, '_facilities_tab_display_for_intent', None)))
        self.assertTrue(callable(getattr(h, '_quote_is_caveat', None)))
        self.assertEqual(getattr(e, '_MIN_QUOTE_CHARS', None), getattr(h, '_MIN_QUOTE_CHARS', None))
        self.assertTrue(callable(getattr(h, '_split_preference_pills', None)))

    def test_pipeline_namespace_has_progress_map(self):
        import recommendation.pipeline as pipeline
        from recommendation.wiring import assert_pipeline_symbols

        assert_pipeline_symbols(pipeline.__dict__)
        prog = pipeline._recommendation_progress('start')
        self.assertEqual(prog[0], 'progress')
        self.assertIn('percent', prog[1])

    def test_pill_scoring_path_no_name_error(self):
        """Jalur Fase 2 pill memanggil _score_shop_by_user_reviews (regresi NameError)."""
        import os

        from recommendation.wiring import ensure_recommendation_wiring

        os.environ.setdefault('COFIND_SEMANTIC_GATE', 'false')
        ensure_recommendation_wiring()
        from recommendation.helpers import _score_shop_by_user_reviews

        profile = {
            'place_id': 'test-shop',
            'reviews': [
                {'text': 'Tempat instagrammable dan AC dingin, toilet bersih.', 'rating': 5},
            ],
            'community_signals': {'rating_counts': {'love': 2, 'like': 1}},
        }
        pills = ['instagrammable', 'ruangan_ac', 'toilet_bersih']
        detail = _score_shop_by_user_reviews(profile, pills, search_keywords=['instagrammable'])
        self.assertIn('total_score', detail)
        self.assertIn('per_pill_stats', detail)


if __name__ == '__main__':
    unittest.main()

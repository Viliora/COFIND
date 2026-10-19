"""Regression: corpus pipeline rekomendasi mencakup Cofind + Google Places."""

from __future__ import annotations

import inspect
import unittest

from review_utils import (
    PIPELINE_REVIEW_SOURCES,
    REVIEW_SOURCE_COFIND,
    REVIEW_SOURCE_GOOGLE_PLACES,
    _pipeline_review_source_sql,
    _review_row_to_api_dict,
    get_reviews_for_recommendation_batch,
)


class ReviewPipelineSourceTests(unittest.TestCase):
    def test_pipeline_sources_include_cofind_and_google(self):
        self.assertIn(REVIEW_SOURCE_COFIND, PIPELINE_REVIEW_SOURCES)
        self.assertIn(REVIEW_SOURCE_GOOGLE_PLACES, PIPELINE_REVIEW_SOURCES)

    def test_pipeline_sql_predicate_allows_google_places(self):
        pred = _pipeline_review_source_sql('r')
        self.assertIn('google_places', pred)
        self.assertIn('cofind', pred)
        self.assertNotIn("= 'cofind'", pred.replace(' ', ''))

    def test_batch_loader_documents_all_sources(self):
        doc = inspect.getdoc(get_reviews_for_recommendation_batch) or ''
        self.assertIn('Google', doc)

    def test_review_dict_carries_text_for_google_rows(self):
        row = {
            'id': 1,
            'user_id': None,
            'shop_id': 9,
            'place_id': 'ChIJtest',
            'rating': 5,
            'review_text': 'wifi kencang tempat nyaman',
            'created_at': '2026-01-01',
            'updated_at': '2026-01-01',
            'review_source': REVIEW_SOURCE_GOOGLE_PLACES,
            'author_display_name': 'Pengulas Google',
            'relative_time': '1 bulan lalu',
            'display_name': 'Pengulas Google',
        }
        out = _review_row_to_api_dict(row)
        self.assertEqual(out['review_source'], REVIEW_SOURCE_GOOGLE_PLACES)
        self.assertEqual(out['text'], 'wifi kencang tempat nyaman')
        self.assertEqual(out['username'], 'Pengulas Google')


if __name__ == '__main__':
    unittest.main()

"""Unit test RRF hybrid retrieval dan ekstraksi intent free text (tanpa LLM asli)."""

from __future__ import annotations

import json
import os
import unittest

os.environ.setdefault('COFIND_SEMANTIC_GATE', 'false')
os.environ['COFIND_FREE_TEXT_INTENT'] = 'true'

from free_text_intent import extract_search_intent
from hybrid_retrieval import reciprocal_rank_fusion

PILL_LABELS = {
    'kerja': 'Kerja/WFC',
    'wifi_kencang': 'Wifi kencang',
}
PILL_MAPPING = {
    'kerja': {
        'definition': 'Tempat nyaman untuk bekerja dengan laptop.',
        'review_keywords': ['kerja', 'wfc', 'laptop'],
    },
    'wifi_kencang': {
        'definition': 'Koneksi internet stabil dan cepat.',
        'review_keywords': ['wifi kencang', 'internet'],
    },
}


class ReciprocalRankFusionTests(unittest.TestCase):
    def test_dual_list_boosts_overlap_and_orders_by_score(self):
        bm25_ranked = ['shop-a', 'shop-b', 'shop-c']
        dense_ranked = ['shop-b', 'shop-d', 'shop-a']
        fused = reciprocal_rank_fusion([bm25_ranked, dense_ranked], k=60)

        self.assertEqual(list(fused.keys()), sorted(fused, key=fused.get, reverse=True))
        self.assertGreater(fused['shop-b'], fused['shop-a'])
        self.assertGreater(fused['shop-b'], fused['shop-c'])
        self.assertGreater(fused['shop-b'], fused['shop-d'])
        self.assertGreater(fused['shop-a'], fused['shop-c'])
        self.assertGreater(fused['shop-a'], fused['shop-d'])


class ExtractSearchIntentTests(unittest.TestCase):
    def test_parses_llm_json_without_pill_match(self):
        calls = []

        def fake_chat(**kwargs):
            calls.append(kwargs)
            return json.dumps({
                'matched_pill': None,
                'matched_attribute_pills': [],
                'keywords': ['tenang', 'wifi'],
                'dense_query': 'coffee shop tenang dengan wifi baik',
            })

        result = extract_search_intent(
            'tenang wifi',
            pill_labels=PILL_LABELS,
            pill_mapping=PILL_MAPPING,
            chat_fn=fake_chat,
        )
        self.assertEqual(len(calls), 1)
        self.assertIsNone(result['matched_pill'])
        self.assertEqual(result['keywords'], ['tenang', 'wifi'])
        self.assertEqual(result['dense_query'], 'coffee shop tenang dengan wifi baik')
        self.assertEqual(result['telemetry']['backend'], 'llm')

    def test_llm_exception_falls_back_to_keywords(self):
        def exploding_chat(**kwargs):
            raise RuntimeError('LLM down')

        result = extract_search_intent(
            'colokan banyak',
            pill_labels=PILL_LABELS,
            pill_mapping=PILL_MAPPING,
            chat_fn=exploding_chat,
        )
        self.assertIsNone(result['matched_pill'])
        self.assertEqual(result['keywords'], ['colokan', 'banyak'])
        self.assertEqual(result['telemetry']['backend'], 'fallback')
        self.assertIn('error', result['telemetry'])

    def test_empty_text_skips_chat_and_returns_empty_keywords(self):
        calls = []

        def should_not_run(**kwargs):
            calls.append(kwargs)
            raise AssertionError('chat_fn must not be called for empty input')

        result = extract_search_intent(
            '   ',
            pill_labels=PILL_LABELS,
            pill_mapping=PILL_MAPPING,
            chat_fn=should_not_run,
        )
        self.assertEqual(calls, [])
        self.assertEqual(result['keywords'], [])
        self.assertIsNone(result['matched_pill'])
        self.assertEqual(result['telemetry']['backend'], 'empty')


if __name__ == '__main__':
    unittest.main()

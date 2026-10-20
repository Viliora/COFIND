"""Uji penanganan query free text (tanpa LLM pipeline penuh)."""

from __future__ import annotations

import unittest

from free_text_query_handling import (
    QUERY_CLASS_NEGATIVE,
    QUERY_CLASS_OFF_DOMAIN,
    QUERY_CLASS_FALSE_PRESUP,
    classify_query_heuristic,
    merge_query_classification,
)


class FreeTextQueryHandlingTests(unittest.TestCase):
    def test_heuristic_negative_superlative(self):
        self.assertEqual(
            classify_query_heuristic('coffee shop paling jelek'),
            QUERY_CLASS_NEGATIVE,
        )

    def test_heuristic_off_domain_gibberish(self):
        self.assertEqual(classify_query_heuristic('xyzqwrtp'), QUERY_CLASS_OFF_DOMAIN)

    def test_merge_respects_llm_false_presupposition(self):
        merged = merge_query_classification(
            'Coffee shop yang ada dinosaurus',
            llm_query_class='false_presupposition',
            impossible_detail='dinosaurus',
            alternative_keywords=['unik', 'estetik', 'tema'],
        )
        self.assertEqual(merged['query_class'], QUERY_CLASS_FALSE_PRESUP)
        self.assertIn('dinosaurus', merged['response_message'] or '')
        self.assertIn('unik', merged['response_message'] or '')

    def test_merge_off_domain_early_exit(self):
        merged = merge_query_classification(
            'xyzqwrtp',
            llm_query_class='off_domain',
        )
        self.assertTrue(merged['early_exit'])
        self.assertIsNotNone(merged['response_message'])

    def test_negative_framing_message(self):
        merged = merge_query_classification(
            'paling jelek',
            llm_query_class='standard',
        )
        self.assertEqual(merged['query_class'], QUERY_CLASS_NEGATIVE)
        self.assertIn('berdasarkan rating', (merged['response_message'] or '').lower())


if __name__ == '__main__':
    unittest.main()

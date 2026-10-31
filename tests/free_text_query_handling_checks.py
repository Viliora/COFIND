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
            llm_classification_trusted=True,
            impossible_detail='dinosaurus',
            alternative_keywords=['unik', 'estetik', 'tema'],
        )
        self.assertEqual(merged['query_class'], QUERY_CLASS_FALSE_PRESUP)
        self.assertIn('dinosaurus', merged['response_message'] or '')
        self.assertIn('unik', merged['response_message'] or '')
        pv = merged.get('presupposition_verification') or {}
        self.assertFalse(pv.get('verified'))
        qr = merged.get('query_relaxation') or {}
        self.assertTrue(qr.get('applied'))
        self.assertIn('unik', qr.get('relaxed_keywords') or [])

    def test_merge_off_domain_early_exit_llm(self):
        merged = merge_query_classification(
            'xyzqwrtp',
            llm_query_class='off_domain',
            llm_classification_trusted=True,
        )
        self.assertEqual(merged['query_class_source'], 'llm')
        self.assertTrue(merged['early_exit'])
        self.assertIsNotNone(merged['response_message'])
        self.assertEqual(
            (merged.get('query_relaxation') or {}).get('strategy'),
            'domain_reformulation',
        )

    def test_merge_heuristic_fallback_gibberish(self):
        merged = merge_query_classification('xyzqwrtp')
        self.assertEqual(merged['query_class_source'], 'heuristic')
        self.assertEqual(merged['query_class'], QUERY_CLASS_OFF_DOMAIN)
        self.assertTrue(merged['early_exit'])

    def test_llm_standard_not_overridden_by_heuristic_gibberish(self):
        merged = merge_query_classification(
            'xyzqwrtp',
            llm_query_class='standard',
            llm_classification_trusted=True,
        )
        self.assertEqual(merged['query_class'], 'standard')
        self.assertFalse(merged['early_exit'])

    def test_negative_early_exit_llm_trusted(self):
        merged = merge_query_classification(
            'paling jelek',
            llm_query_class='negative_sentiment',
            llm_classification_trusted=True,
        )
        self.assertEqual(merged['query_class_source'], 'llm')
        self.assertEqual(merged['query_class'], QUERY_CLASS_NEGATIVE)
        self.assertTrue(merged['early_exit'])
        self.assertIn('abstention', (merged['response_message'] or '').lower())
        self.assertEqual(
            (merged.get('query_relaxation') or {}).get('strategy'),
            'abstention_with_reformulation',
        )

    def test_negative_early_exit_heuristic_fallback(self):
        merged = merge_query_classification('coffee shop paling jelek')
        self.assertEqual(merged['query_class_source'], 'heuristic')
        self.assertEqual(merged['query_class'], QUERY_CLASS_NEGATIVE)
        self.assertTrue(merged['early_exit'])


if __name__ == '__main__':
    unittest.main()

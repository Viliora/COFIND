"""Validasi normalisasi input free text (panjang + charset)."""

from __future__ import annotations

import unittest

from free_text_intent import (
    MAX_FREE_TEXT_CHARS,
    is_valid_free_text_query,
    normalize_free_text_query,
)


class FreeTextInputTests(unittest.TestCase):
    def test_max_length(self):
        self.assertEqual(MAX_FREE_TEXT_CHARS, 100)
        raw = 'a' * 120
        self.assertEqual(len(normalize_free_text_query(raw)), 100)

    def test_strips_disallowed_chars(self):
        self.assertEqual(
            normalize_free_text_query('wifi kencang! @#$'),
            'wifi kencang',
        )
        self.assertEqual(normalize_free_text_query('wfc, nyaman musholla'), 'wfc, nyaman musholla')

    def test_is_valid(self):
        self.assertTrue(is_valid_free_text_query('wifi kencang'))
        self.assertFalse(is_valid_free_text_query('wifi-kencang'))
        self.assertFalse(is_valid_free_text_query('a' * 101))


if __name__ == '__main__':
    unittest.main()

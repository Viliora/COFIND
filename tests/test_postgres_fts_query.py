"""Sanity: token FTS query memakai to_tsquery AND."""

import unittest

from postgres_fts import score_shops_fts


class TestPostgresFtsQuery(unittest.TestCase):
    def test_empty_tokens_returns_empty(self):
        self.assertEqual(score_shops_fts(["p1"], []), {})


if __name__ == "__main__":
    unittest.main()

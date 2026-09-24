"""Unit test: kutipan fasilitas dari korpus penuh masuk evidence retrieval."""
import unittest

from app import (
    _attribute_quotes_from_reviews,
    _build_retrieval_evidence,
    _merge_quote_rows,
)


class RecommendationEvidenceTests(unittest.TestCase):
    def test_attribute_quotes_scan_full_corpus(self):
        reviews = [
            {'text': 'Suasana tenang cocok belajar.', 'rating': 5},
            {'text': 'Ada colokan di beberapa meja, nyaman ngecas.', 'rating': 4},
        ]
        rows, matches = _attribute_quotes_from_reviews(
            reviews,
            ['banyak_colokan_terminal'],
            limit_per_pill=2,
        )
        self.assertEqual(len(rows), 1)
        self.assertIn('colokan', rows[0]['quote'].lower())
        self.assertEqual(rows[0]['pill'], 'banyak_colokan_terminal')
        self.assertEqual(len(matches), 1)

    def test_retrieval_evidence_unions_ranked_and_attribute(self):
        profile = {
            'reviews': [
                {'text': 'Tempat kondusif untuk belajar dan nugas skripsi.', 'rating': 5},
                {'text': 'Wifi kencang dan colokan cukup di meja saya.', 'rating': 5},
            ],
            'review_count': 2,
            'avg_user_rating': 5.0,
            'avg_category_ratings': {},
            'facilities_tab': {},
        }
        ev = _build_retrieval_evidence(
            profile,
            ['belajar', 'wifi_kencang', 'banyak_colokan_terminal'],
            query_text='belajar wifi colokan',
            query_tokens=['belajar', 'wifi', 'colokan'],
            activity_tokens=['belajar', 'nugas'],
            activity_pills=['belajar'],
            attribute_pills=['wifi_kencang', 'banyak_colokan_terminal'],
        )
        quotes = ev.get('review_quotes') or []
        blob = ' '.join(str(q.get('quote') or '') for q in quotes).lower()
        self.assertIn('belajar', blob)
        self.assertIn('colokan', blob)
        pills = {str(q.get('pill')) for q in quotes}
        self.assertIn('banyak_colokan_terminal', pills)

    def test_merge_quote_rows_dedupes(self):
        a = [{'quote': 'Sama persis di sini.', 'pill': 'belajar'}]
        b = [
            {'quote': 'Sama persis di sini.', 'pill': 'belajar'},
            {'quote': 'Kutipan lain unik.', 'pill': 'wifi_kencang'},
        ]
        merged = _merge_quote_rows(a, b)
        self.assertEqual(len(merged), 2)


if __name__ == '__main__':
    unittest.main()

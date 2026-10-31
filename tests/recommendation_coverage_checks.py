"""Unit test coverage pill: metadata helper, jam buka helper, keyword hits."""

import unittest

from recommendation_coverage import (
    hours_indicate_24_7,
    merge_pill_coverage,
    pills_covered_by_opening_hours,
    pills_with_review_keyword_hits,
)


class RecommendationCoverageTests(unittest.TestCase):
    def test_hours_24_7(self):
        self.assertTrue(hours_indicate_24_7('Buka 24 jam setiap hari'))
        self.assertTrue(hours_indicate_24_7('Open 24/7'))
        self.assertFalse(hours_indicate_24_7('Senin–Jumat 08:00–22:00'))

    def test_opening_hours_covers_24h_pill(self):
        shop = {
            'profile': {'opening_hours_display': '24 jam'},
            'evidence': {},
        }
        got = pills_covered_by_opening_hours(shop, ['buka_sampai_malam_24_hours', 'belajar'])
        self.assertIn('buka_sampai_malam_24_hours', got)

    def test_keyword_hits_cover_pill(self):
        shop = {
            'score_detail': {
                'per_pill_stats': {
                    'banyak_colokan_terminal': {'keyword_review_hits': 2},
                },
            },
        }
        got = pills_with_review_keyword_hits(shop, ['banyak_colokan_terminal', 'wifi_kencang'])
        self.assertIn('banyak_colokan_terminal', got)
        self.assertNotIn('wifi_kencang', got)

    def test_merge_uses_review_keyword_hits_only(self):
        shop = {
            'profile': {'opening_hours_display': '24 jam'},
            'score_detail': {
                'per_pill_stats': {
                    'banyak_colokan_terminal': {'keyword_review_hits': 1},
                },
            },
            'evidence': {},
        }
        pills = ['belajar', 'wifi_kencang', 'banyak_colokan_terminal', 'buka_sampai_malam_24_hours']
        covered, uncovered = merge_pill_coverage(
            shop,
            pills,
            covered=['belajar'],
            uncovered=['wifi_kencang', 'banyak_colokan_terminal', 'buka_sampai_malam_24_hours'],
            facility_attribute_pills={'wifi_kencang', 'banyak_colokan_terminal', 'buka_sampai_malam_24_hours'},
        )
        self.assertIn('belajar', covered)
        self.assertIn('banyak_colokan_terminal', covered)
        self.assertNotIn('wifi_kencang', covered)
        self.assertNotIn('buka_sampai_malam_24_hours', covered)
        self.assertEqual(uncovered, ['wifi_kencang', 'buka_sampai_malam_24_hours'])


if __name__ == '__main__':
    unittest.main()

"""Regression: sentimen pill generik (bukan patch frasa per kasus)."""

import unittest

import app as A
from pill_aspect_sentiment import (
    aggregate_reviews_sentiment,
    review_negates_pill,
    review_sentiment_for_pill,
)


class PillAspectSentimentTests(unittest.TestCase):
    def test_parking_variants_without_exact_phrase_in_dict(self):
        mapping = A.PILL_MAPPING
        cases = [
            'Parkirnya ribet banget buat mobil.',
            'Tempat parkir minim, susah cari slot.',
            'utk parkiran agak susah ya apalg khusus mobil.',
        ]
        for text in cases:
            with self.subTest(text=text[:40]):
                self.assertEqual(
                    review_sentiment_for_pill(text, 'parkir_luas', mapping),
                    'negative',
                )

    def test_wifi_slow_near_keyword(self):
        text = 'Suasana oke, tapi wifinya lemot buat kerja.'
        self.assertTrue(review_negates_pill(text, 'wifi_kencang', A.PILL_MAPPING))

    def test_toilet_complaint_near_keyword(self):
        text = 'Kopinya enak, toiletnya jorok parah.'
        self.assertTrue(review_negates_pill(text, 'toilet_bersih', A.PILL_MAPPING))

    def test_neutral_mention_without_weakness_not_negative(self):
        text = 'Ada area parkir di depan, tapi saya naik ojek.'
        self.assertNotEqual(
            review_sentiment_for_pill(text, 'parkir_luas', A.PILL_MAPPING),
            'negative',
        )

    def test_positive_parking(self):
        text = 'Parkir luas dan mudah untuk mobil.'
        self.assertEqual(
            aggregate_reviews_sentiment([{'text': text}], 'parkir_luas', A.PILL_MAPPING),
            'positive',
        )


if __name__ == '__main__':
    unittest.main()

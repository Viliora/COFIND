"""Regression: badge fasilitas hanya saat sentimen ulasan positif atau netral + metadata."""

import unittest

import app as A
from metadata_prior import evaluate_metadata_gate, facility_pill_negative_in_review


class FacilityBadgeSentimentTests(unittest.TestCase):
    def test_parking_complaint_blocks_badge(self):
        text = (
            'Menu enak. utk parkiran agak susah ya apalg khusus mobil.'
        )
        self.assertTrue(
            facility_pill_negative_in_review(text, 'parkir_luas', A.PILL_MAPPING),
        )
        gate = evaluate_metadata_gate(
            {
                'facilities_raw': {'parking': {'lots_of_parking': True}},
                'reviews': [{'text': text}],
            },
            ['kerja', 'parkir_luas'],
            pill_mapping=A.PILL_MAPPING,
            pill_labels=A.PILL_LABELS,
            attribute_pills=['parkir_luas'],
        )
        detail = {
            'attribute_pills': ['parkir_luas'],
            'covered_pills': ['kerja', 'parkir_luas'],
        }
        pills, _ = A._matched_facility_from_gate(
            gate, detail, reviews=[{'text': text}],
        )
        self.assertNotIn('parkir_luas', pills)

    def test_parking_praise_allows_badge(self):
        text = 'Parkir luas dan mudah untuk mobil.'
        gate = evaluate_metadata_gate(
            {
                'facilities_raw': {'parking': {'lots_of_parking': True}},
                'reviews': [{'text': text}],
            },
            ['parkir_luas'],
            pill_mapping=A.PILL_MAPPING,
            pill_labels=A.PILL_LABELS,
            attribute_pills=['parkir_luas'],
        )
        detail = {'attribute_pills': ['parkir_luas'], 'covered_pills': ['parkir_luas']}
        pills, _ = A._matched_facility_from_gate(
            gate, detail, reviews=[{'text': text}],
        )
        self.assertIn('parkir_luas', pills)


if __name__ == '__main__':
    unittest.main()

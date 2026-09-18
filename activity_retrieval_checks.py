"""Gerbang aktivitas: nge-charge bukan nge-game; main ML / mabar harus lolos."""

import os
import unittest

os.environ.setdefault('COFIND_SEMANTIC_GATE', 'false')

from hybrid_retrieval import (
    compile_activity_matcher,
    retrieve_top_k,
    shop_has_activity_signal,
    text_has_activity_signal,
)


PILL_LABELS = {'bermain game': 'Bermain game'}
PILL_MAPPING = {
    'bermain game': {
        'review_keywords': [
            'main game', 'gaming', 'game', 'ngegame', 'nge-game', 'nge game',
            'mobile legends', 'mabar', 'push rank', 'bermain game',
        ],
    }
}


def _matcher():
    return compile_activity_matcher(
        ['bermain game'],
        pill_labels=PILL_LABELS,
        pill_mapping=PILL_MAPPING,
    )


class ActivityMatcherTests(unittest.TestCase):
    def setUp(self):
        self.matcher = _matcher()

    def test_rejects_nge_charge_wfc_review(self):
        text = (
            'Lunch after jemput anak, tempatnya cozy dan lumayan tenang untuk ngobrol, '
            'musiknya oke tidak terlalu keras. Area untuk WFC atau nugas juga banyak, '
            'nge-charge laptop hp bisa dimana saja.'
        )
        self.assertFalse(text_has_activity_signal(text, self.matcher))

    def test_rejects_ngecas_without_game(self):
        self.assertFalse(text_has_activity_signal('colokan banyak, ngecas laptop lancar', self.matcher))

    def test_accepts_nge_game_hyphen(self):
        self.assertTrue(text_has_activity_signal('asik nge-game bareng temen di sini', self.matcher))

    def test_accepts_mabar(self):
        self.assertTrue(text_has_activity_signal('Sering mabar sampe malam, colokan banyak', self.matcher))

    def test_accepts_main_ml_with_context(self):
        self.assertTrue(text_has_activity_signal('Cocok main ML sama temen di outdoor', self.matcher))

    def test_rejects_bare_ml_without_context(self):
        self.assertFalse(text_has_activity_signal('pesan kopi 250 ml dingin', self.matcher))

    def test_accepts_push_rank(self):
        self.assertTrue(text_has_activity_signal('sambil push rank wifi masih kuat', self.matcher))


class RetrieveTopKActivityGateTests(unittest.TestCase):
    def test_kokotuku_false_positive_dropped_aming_kept(self):
        profiles = [
            {
                'place_id': 'kokotuku',
                'name': 'KOKOTUKU',
                'reviews': [
                    {
                        'text': (
                            'Lunch after jemput anak, tempatnya cozy. Area untuk WFC atau nugas '
                            'juga banyak, nge-charge laptop hp bisa dimana saja.'
                        )
                    }
                ],
            },
            {
                'place_id': 'aming-ilham',
                'name': 'Aming Coffee Ilham',
                'reviews': [
                    {'text': 'Tempatnya luas, cocok mabar sama temen. Colokan outdoor banyak.'},
                    {'text': 'Sering main ML di sini sampe malam, wifi aman push rank.'},
                ],
            },
        ]
        result = retrieve_top_k(
            profiles,
            ['bermain game'],
            pill_labels=PILL_LABELS,
            pill_mapping=PILL_MAPPING,
            quality_by_place={'kokotuku': 0.9, 'aming-ilham': 0.7},
            top_k=7,
            activity_pills=['bermain game'],
            attribute_pills=[],
        )
        ids = [c['place_id'] for c in result['candidates']]
        self.assertIn('aming-ilham', ids)
        self.assertNotIn('kokotuku', ids)
        self.assertTrue(
            shop_has_activity_signal(
                profiles[1]['reviews'],
                result['activity_tokens'],
                activity_matcher=result['activity_matcher'],
            )
        )


if __name__ == '__main__':
    unittest.main()

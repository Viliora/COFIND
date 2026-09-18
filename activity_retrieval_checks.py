"""Gerbang aktivitas: nge-charge bukan nge-game; main ML / mabar harus lolos."""

import os
import unittest

os.environ.setdefault('COFIND_SEMANTIC_GATE', 'false')

from hybrid_retrieval import (
    compile_activity_matcher,
    extract_activity_support_text,
    retrieve_top_k,
    shop_has_activity_signal,
    text_has_activity_signal,
    text_rejects_requested_activity,
)


PILL_LABELS = {
    'bermain game': 'Bermain game',
    'belajar': 'Belajar',
    'kerja': 'Kerja/WFC',
    'meeting_sosialisasi': 'Meeting/Pertemuan',
    'keluarga': 'Keluarga',
    'instagrammable': 'Instagrammable',
    'wifi_kencang': 'Wifi kencang',
    'banyak_colokan_terminal': 'Banyak colokan / terminal',
}
PILL_MAPPING = {
    'bermain game': {
        'review_keywords': [
            'main game', 'gaming', 'game', 'ngegame', 'nge-game', 'nge game',
            'mobile legends', 'mabar', 'push rank', 'bermain game',
        ],
    },
    'belajar': {
        'review_keywords': [
            'belajar', 'tugas', 'nugas', 'skripsi', 'baca buku', 'kuliah',
        ],
    },
    'kerja': {
        'review_keywords': [
            'kerja', 'wfc', 'work from cafe', 'laptopan', 'ngantor',
        ],
    },
    'meeting_sosialisasi': {
        'review_keywords': ['meeting', 'rapat', 'diskusi', 'untuk rapat'],
    },
    'keluarga': {
        'review_keywords': ['keluarga', 'ramah keluarga', 'ramah anak', 'family'],
    },
    'instagrammable': {
        'review_keywords': ['instagrammable', 'spot foto', 'estetik'],
    },
    'wifi_kencang': {
        'review_keywords': ['wifi kencang', 'wifi lancar', 'wifi'],
    },
    'banyak_colokan_terminal': {
        'review_keywords': ['colokan', 'banyak colokan', 'ngecas'],
    },
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

    def test_mixed_family_caveat_still_supports_main_game(self):
        text = (
            'Selalu ramai anak remaja nongkrong main game, anak kuliahan mengerjakan tugas, '
            'maupun nongkrong disini. Jika untuk berkumpul dengan keluarga kurang disarankan'
        )
        self.assertTrue(text_has_activity_signal(text, self.matcher))
        support = extract_activity_support_text(text, self.matcher)
        self.assertIn('main game', support.lower())
        self.assertNotIn('kurang disarankan', support.lower())
        self.assertFalse(text_rejects_requested_activity(text, self.matcher))

    def test_accepts_bermain_game_bersama_teman(self):
        text = 'Tempat yg enak untuk nongkrong atau bermain game bersama teman-teman'
        self.assertTrue(text_has_activity_signal(text, self.matcher))
        support = extract_activity_support_text(text, self.matcher)
        self.assertIn('bermain game', support.lower())
        self.assertFalse(text_rejects_requested_activity(text, self.matcher))

    def test_rejects_activity_only_when_same_clause_rejects_game(self):
        text = 'Kafe ini tidak cocok untuk main game, terlalu sepi dan dilarang ribut.'
        self.assertTrue(text_rejects_requested_activity(text, self.matcher))
        self.assertFalse(extract_activity_support_text(text, self.matcher))


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

    def test_mixed_game_and_family_review_keeps_shop(self):
        profiles = [
            {
                'place_id': 'game-family',
                'name': 'Kafe Campur',
                'reviews': [
                    {
                        'text': (
                            'Selalu ramai anak remaja nongkrong main game, anak kuliahan '
                            'mengerjakan tugas, maupun nongkrong disini. Jika untuk berkumpul '
                            'dengan keluarga kurang disarankan'
                        )
                    },
                    {
                        'text': 'Tempat yg enak untuk nongkrong atau bermain game bersama teman-teman'
                    },
                ],
            },
            {
                'place_id': 'charge-only',
                'name': 'WFC Spot',
                'reviews': [
                    {'text': 'Colokan banyak, nge-charge laptop nyaman, WFC seharian.'},
                ],
            },
        ]
        result = retrieve_top_k(
            profiles,
            ['bermain game'],
            pill_labels=PILL_LABELS,
            pill_mapping=PILL_MAPPING,
            quality_by_place={'game-family': 0.6, 'charge-only': 0.9},
            top_k=7,
            activity_pills=['bermain game'],
            attribute_pills=[],
        )
        ids = [c['place_id'] for c in result['candidates']]
        self.assertIn('game-family', ids)
        self.assertNotIn('charge-only', ids)
        self.assertTrue(
            shop_has_activity_signal(
                profiles[0]['reviews'],
                result['activity_tokens'],
                activity_matcher=result['activity_matcher'],
            )
        )


class AllActivityPillGateTests(unittest.TestCase):
    def test_game_word_does_not_count_as_belajar(self):
        matcher = compile_activity_matcher(
            ['belajar'], pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING,
        )
        self.assertFalse(text_has_activity_signal('asik nge-game bareng temen', matcher))
        self.assertTrue(text_has_activity_signal('enak nugas skripsi di sini', matcher))

    def test_activity_only_shop_kept_when_others_have_facilities(self):
        profiles = [
            {
                'place_id': 'belajar-only',
                'name': 'Kafe Tugas',
                'reviews': [
                    {'text': 'Tempatnya enak untuk nugas skripsi sampai malam.'},
                ],
            },
            {
                'place_id': 'wifi-only',
                'name': 'Kafe Wifi',
                'reviews': [
                    {'text': 'Wifi kencang, colokan banyak, nge-charge laptop nyaman.'},
                ],
            },
            {
                'place_id': 'belajar-wifi',
                'name': 'Kafe Lengkap',
                'reviews': [
                    {'text': 'Cocok belajar skripsi. Wifi kencang dan colokan di tiap meja.'},
                ],
            },
        ]
        result = retrieve_top_k(
            profiles,
            ['belajar', 'wifi_kencang', 'banyak_colokan_terminal'],
            pill_labels=PILL_LABELS,
            pill_mapping=PILL_MAPPING,
            quality_by_place={
                'belajar-only': 0.5,
                'wifi-only': 0.95,
                'belajar-wifi': 0.7,
            },
            top_k=7,
            activity_pills=['belajar'],
            attribute_pills=['wifi_kencang', 'banyak_colokan_terminal'],
        )
        ids = [c['place_id'] for c in result['candidates']]
        self.assertIn('belajar-only', ids)
        self.assertIn('belajar-wifi', ids)
        self.assertNotIn('wifi-only', ids)
        self.assertEqual(ids[0], 'belajar-wifi')

    def test_kerja_review_without_facilities_still_gates(self):
        matcher = compile_activity_matcher(
            ['kerja'], pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING,
        )
        self.assertTrue(text_has_activity_signal('santai wfc seharian di sini', matcher))
        self.assertFalse(text_has_activity_signal('colokan banyak ngecas laptop', matcher))
        profiles = [
            {
                'place_id': 'wfc-only',
                'name': 'WFC Corner',
                'reviews': [{'text': 'Nyaman wfc dan ngerjain kerjaan kantor.'}],
            },
            {
                'place_id': 'colokan-only',
                'name': 'Charge Cafe',
                'reviews': [{'text': 'Banyak colokan, ngecas laptop aman.'}],
            },
        ]
        result = retrieve_top_k(
            profiles,
            ['kerja', 'banyak_colokan_terminal'],
            pill_labels=PILL_LABELS,
            pill_mapping=PILL_MAPPING,
            top_k=7,
            activity_pills=['kerja'],
            attribute_pills=['banyak_colokan_terminal'],
        )
        ids = [c['place_id'] for c in result['candidates']]
        self.assertEqual(ids, ['wfc-only'])

    def test_meeting_and_keluarga_phrases(self):
        meeting = compile_activity_matcher(
            ['meeting_sosialisasi'], pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING,
        )
        family = compile_activity_matcher(
            ['keluarga'], pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING,
        )
        self.assertTrue(text_has_activity_signal('ruangnya pas untuk rapat tim', meeting))
        self.assertTrue(text_has_activity_signal('ramah anak, cocok kumpul keluarga', family))
        self.assertFalse(text_has_activity_signal('wifi kencang colokan banyak', meeting))


if __name__ == '__main__':
    unittest.main()

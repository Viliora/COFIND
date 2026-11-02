import unittest

from recommendation.activity_evidence import (
    compile_matcher,
    score_support,
    shop_has_contradiction,
    shop_has_support,
)


class ActivityEvidenceTests(unittest.TestCase):
    def test_game_mabar_has_support(self):
        matcher = compile_matcher(['bermain game'])
        reviews = [{'text': 'seru buat mabar bareng temen'}]
        self.assertTrue(shop_has_support(reviews, ['mabar'], matcher=matcher))
        self.assertGreater(score_support('mabar mobile legends', matcher), 0)

    def test_rejection_is_contradiction(self):
        matcher = compile_matcher(['bermain game'])
        reviews = [{'text': 'Tidak cocok untuk main game di sini, terlalu sepi.'}]
        self.assertTrue(shop_has_contradiction(reviews, matcher, activity_tokens=['game']))


if __name__ == '__main__':
    unittest.main()

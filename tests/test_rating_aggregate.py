"""Unit test agregasi rating Bayesian / Wilson."""

import unittest

from rating_aggregate import bayesian_average, bayesian_rating_unit_score, wilson_lower_bound


class TestRatingAggregate(unittest.TestCase):
    def test_bayesian_pulls_toward_prior_with_few_reviews(self):
        smoothed = bayesian_average(5.0, 1, prior_mean=4.0, prior_weight=10)
        self.assertLess(smoothed, 5.0)
        self.assertGreater(smoothed, 4.0)

    def test_bayesian_unit_score_none_when_no_rating(self):
        self.assertIsNone(bayesian_rating_unit_score(None, 5))

    def test_wilson_zero_when_no_votes(self):
        self.assertEqual(wilson_lower_bound(0, 0), 0.0)


if __name__ == "__main__":
    unittest.main()

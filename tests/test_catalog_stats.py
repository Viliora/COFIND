import unittest
from unittest.mock import MagicMock

from coffee_shop_serialize import fetch_catalog_stats


class CatalogStatsTests(unittest.TestCase):
    def test_fetch_catalog_stats_runs_aggregate_queries(self):
        cursor = MagicMock()
        cursor.execute.side_effect = [
            MagicMock(fetchone=MagicMock(return_value=(3,))),
            MagicMock(fetchone=MagicMock(return_value=(4.25,))),
            MagicMock(fetchone=MagicMock(return_value=(2,))),
            MagicMock(fetchone=MagicMock(return_value=(42,))),
            MagicMock(fetchone=MagicMock(return_value=(1000,))),
        ]
        out = fetch_catalog_stats(cursor)
        self.assertEqual(out['total_shops'], 3)
        self.assertEqual(out['avg_rating'], 4.2)
        self.assertEqual(out['top_rated'], 2)
        self.assertEqual(out['total_cofind_reviews'], 42)
        self.assertEqual(out['total_google_reviews'], 1000)


if __name__ == '__main__':
    unittest.main()

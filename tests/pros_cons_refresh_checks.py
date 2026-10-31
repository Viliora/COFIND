"""Unit test: refresh_pros_cons force vs lazy skip."""
import unittest
from unittest.mock import MagicMock, patch

from pros_cons_utils import refresh_pros_cons


class ProsConsRefreshTests(unittest.TestCase):
    def _patch_db(self):
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        return patch('pros_cons_utils.get_db_connection', return_value=conn)

    def test_lazy_skip_when_not_due(self):
        with self._patch_db():
            with patch('pros_cons_utils._get_review_stats', return_value=(['ulasan'], 10)):
                with patch(
                    'pros_cons_utils._get_meta',
                    return_value={'last_generated_at': '2026-01-01T00:00:00', 'review_count_at_last_generation': 10},
                ):
                    with patch('pros_cons_utils._should_refresh', return_value=False):
                        with patch('pros_cons_utils._count_points', return_value=(2, 1)):
                            result = refresh_pros_cons('place-a', 'Toko A', force=False)
        self.assertTrue(result['skipped'])
        self.assertEqual(result['reason'], 'not_due')
        self.assertEqual(result['pro_count'], 2)
        self.assertEqual(result['con_count'], 1)

    def test_force_runs_llm_and_succeeds(self):
        with self._patch_db() as mock_conn:
            conn = mock_conn.return_value
            with patch('pros_cons_utils._get_review_stats', return_value=(['wifi kencang'], 3)):
                with patch('pros_cons_utils._get_meta', return_value=None):
                    with patch('pros_cons_utils.llm_is_available', return_value=True):
                        with patch(
                            'pros_cons_utils._generate_pros_cons_via_llm',
                            return_value=(['wifi kencang'], ['parkir sempit']),
                        ) as gen:
                            with patch('pros_cons_utils._replace_points'):
                                with patch('pros_cons_utils._count_points', return_value=(1, 1)):
                                    result = refresh_pros_cons('place-b', 'Toko B', force=True)
            gen.assert_called_once()
            conn.commit.assert_called()
        self.assertTrue(result['ok'])
        self.assertFalse(result['skipped'])
        self.assertEqual(result['pro_count'], 1)
        self.assertEqual(result['con_count'], 1)

    def test_no_reviews_skipped(self):
        with self._patch_db():
            with patch('pros_cons_utils._get_review_stats', return_value=([], 0)):
                with patch('pros_cons_utils._get_meta', return_value=None):
                    result = refresh_pros_cons('place-c', 'Toko C', force=True)
        self.assertTrue(result['skipped'])
        self.assertEqual(result['reason'], 'no_reviews')


if __name__ == '__main__':
    unittest.main()

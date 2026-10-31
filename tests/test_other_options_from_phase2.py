import unittest

from recommendation.helpers import _build_other_options_from_phase2


class OtherOptionsFromPhase2Tests(unittest.TestCase):
    def test_excludes_recommended_and_keeps_phase2_order(self):
        candidates = [
            {'place_id': 'a', 'name': 'A', 'profile': {}},
            {'place_id': 'b', 'name': 'B', 'profile': {}},
            {'place_id': 'c', 'name': 'C', 'profile': {}},
            {'place_id': 'd', 'name': 'D', 'profile': {'address': 'Jl. 1'}},
        ]
        out = _build_other_options_from_phase2(
            candidates,
            ['a', 'b', 'c'],
            limit=7,
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['place_id'], 'd')
        self.assertEqual(out[0]['address'], 'Jl. 1')


if __name__ == '__main__':
    unittest.main()

import unittest

from activity_lexicon import (
    ACTIVITY_PILL_KEYS,
    activity_terms,
    apply_activity_lexicon_to_mapping,
    load_activity_lexicon,
    review_keywords_for_activity_pill,
)
from pill_config import PILL_MAPPING


class ActivityLexiconTests(unittest.TestCase):
    def test_lexicon_loads_all_activity_pills(self):
        data = load_activity_lexicon()
        pills = data.get("pills") or {}
        for pill in ACTIVITY_PILL_KEYS:
            self.assertIn(pill, pills)
            terms = pills[pill].get("terms") or []
            self.assertTrue(terms, f"{pill} terms kosong")

    def test_mapping_synced_from_lexicon(self):
        for pill in ACTIVITY_PILL_KEYS:
            expected = review_keywords_for_activity_pill(pill)
            actual = list((PILL_MAPPING.get(pill) or {}).get("review_keywords") or [])
            self.assertEqual(actual, expected, pill)

    def test_terms_alias_matches_review_keywords_helper(self):
        for pill in ACTIVITY_PILL_KEYS:
            self.assertEqual(activity_terms(pill), review_keywords_for_activity_pill(pill))

    def test_apply_idempotent(self):
        snap = {
            pill: list((PILL_MAPPING.get(pill) or {}).get("review_keywords") or [])
            for pill in ACTIVITY_PILL_KEYS
        }
        apply_activity_lexicon_to_mapping(PILL_MAPPING)
        for pill in ACTIVITY_PILL_KEYS:
            self.assertEqual(
                list((PILL_MAPPING.get(pill) or {}).get("review_keywords") or []),
                snap[pill],
            )


if __name__ == "__main__":
    unittest.main()

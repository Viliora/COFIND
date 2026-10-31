"""Teks retrieval pill: dense_query, pemisahan label UI dari sparse, dan facility_fields."""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("COFIND_SEMANTIC_GATE", "false")

from hybrid_retrieval import (
    activity_text_score,
    build_dense_query_text,
    build_sparse_query_tokens,
    compile_activity_matcher,
    text_matches_tokens,
)
from pill_config import FACILITY_ATTRIBUTE_PILLS, PILL_LABELS, PILL_MAPPING

MAX_DENSE_QUERY_CHARS = 150
# Negasi diembed buruk: "bukan bar" justru mendekatkan vektor ke "bar".
NEGATION_TOKENS = frozenset({"bukan", "tidak", "nggak", "ngga", "gak", "ga", "tanpa", "jangan"})
# Grup coffee_shops.facilities (Google Places legacy).
KNOWN_FACILITY_GROUPS = frozenset({
    "accessibility", "amenities", "atmosphere", "children", "crowd", "dining_options",
    "highlights", "offerings", "parking", "payments", "pets", "planning", "popular_for",
    "service_options",
})


def _sparse(pill: str) -> list:
    return build_sparse_query_tokens([pill], pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING)


class DenseQueryTests(unittest.TestCase):
    def test_every_pill_has_short_dense_query(self):
        for pill, spec in PILL_MAPPING.items():
            text = str(spec.get("dense_query") or "").strip()
            self.assertTrue(text, f"{pill} belum punya dense_query")
            self.assertLessEqual(len(text), MAX_DENSE_QUERY_CHARS, pill)

    def test_dense_query_has_no_negation(self):
        for pill, spec in PILL_MAPPING.items():
            words = set(str(spec.get("dense_query") or "").lower().replace(",", " ").split())
            self.assertFalse(words & NEGATION_TOKENS, f"{pill}: negasi {sorted(words & NEGATION_TOKENS)}")

    def test_dense_query_follows_label_meaning(self):
        expected = {
            "makanan_berat": {"menu", "minuman"},       # "Menu Lengkap (Makanan & Minuman)"
            "ruangan_ac": {"sejuk"},                    # "Ruangan sejuk"
            "buka_sampai_malam_24_hours": {"24"},       # "24 hours"
            "ruang_privat": {"meeting"},                # "Ruang privat / meeting"
            "banyak_colokan_terminal": {"terminal"},    # "Banyak colokan / terminal"
            "meeting_sosialisasi": {"pertemuan"},       # "Meeting/Pertemuan"
            "instagrammable": {"feed"},                 # "Feeds Hunter"
        }
        for pill, words in expected.items():
            text = str(PILL_MAPPING[pill]["dense_query"]).lower().replace(",", " ")
            missing = {w for w in words if w not in text.split()}
            self.assertFalse(missing, f"{pill}: dense_query belum mencerminkan label {sorted(missing)}")

    def test_dense_text_uses_dense_query_without_shared_prefix(self):
        text = build_dense_query_text(["wifi_kencang"], pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING)
        self.assertEqual(text, PILL_MAPPING["wifi_kencang"]["dense_query"])
        self.assertNotIn("Cari coffee shop", text)

    def test_dense_text_joins_multiple_pills(self):
        text = build_dense_query_text(["belajar", "keluarga"], pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING)
        self.assertIn(PILL_MAPPING["belajar"]["dense_query"], text)
        self.assertIn(PILL_MAPPING["keluarga"]["dense_query"], text)

    def test_dense_text_falls_back_to_label(self):
        mapping = {"x": {"label": "Contoh"}}
        text = build_dense_query_text(["x"], pill_labels={"x": "Contoh"}, pill_mapping=mapping)
        self.assertEqual(text, "Contoh")


class SparseLabelSeparationTests(unittest.TestCase):
    def test_ui_label_and_pill_key_not_in_sparse_tokens(self):
        cases = {
            "instagrammable": {"feeds", "hunter"},
            "musholla": {"ada"},
            "makanan_berat": {"menu", "lengkap", "minuman"},
            "buka_sampai_malam_24_hours": {"buka", "sampai", "malam"},
            "wifi_kencang": {"kencang"},
            "parkir_luas": {"luas"},
            "toilet_bersih": {"bersih"},
            "banyak_colokan_terminal": {"banyak", "terminal"},
            "suasana_tenang": {"suasana"},
        }
        for pill, leaked in cases.items():
            bad = set(_sparse(pill)) & leaked
            self.assertFalse(bad, f"{pill}: label/key bocor ke sparse {sorted(bad)}")

    def test_label_fallback_when_no_keywords(self):
        tokens = build_sparse_query_tokens(["x"], pill_labels={"x": "Rooftop"}, pill_mapping={"x": {}})
        self.assertEqual(tokens, ["rooftop"])

    def test_generic_ada_review_is_not_musholla_evidence(self):
        self.assertFalse(text_matches_tokens("Ada banyak kursi di lantai dua", _sparse("musholla")))
        self.assertTrue(text_matches_tokens("ada mushola yang bersih", _sparse("musholla")))

    def test_activity_matcher_ignores_persona_label(self):
        matcher = compile_activity_matcher(["instagrammable"], pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING)
        self.assertFalse({"feeds", "hunter"} & set(matcher["bm25_tokens"]))

    def test_core_activity_words_still_pass_gate(self):
        for pill, text in {
            "kerja": "Asik untuk sambil belajar atau kerja",
            "belajar": "Cocok buat belajar",
            "keluarga": "cocok buat keluarga",
            "meeting_sosialisasi": "nyaman buat meeting",
        }.items():
            matcher = compile_activity_matcher([pill], pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING)
            self.assertGreater(activity_text_score(text, matcher), 0.0, pill)


class FacilityFieldsTests(unittest.TestCase):
    def test_activity_pills_have_no_facility_fields(self):
        """Prior metadata hanya dari pill atribut; aktivitas dinilai dari ulasan."""
        for pill in PILL_MAPPING:
            if pill not in FACILITY_ATTRIBUTE_PILLS:
                self.assertNotIn("facility_fields", PILL_MAPPING[pill], pill)

    def test_attribute_facility_groups_are_known(self):
        for pill in FACILITY_ATTRIBUTE_PILLS:
            groups = set((PILL_MAPPING[pill].get("facility_fields") or {}).keys())
            self.assertFalse(groups - KNOWN_FACILITY_GROUPS, f"{pill}: grup asing {groups - KNOWN_FACILITY_GROUPS}")

    def test_semantic_mismatches_removed(self):
        ff = {p: PILL_MAPPING[p].get("facility_fields") or {} for p in FACILITY_ATTRIBUTE_PILLS}
        self.assertEqual(set(ff["parkir_luas"]["parking"]), {"lots_of_parking", "plenty_of_parking"})
        self.assertNotIn("planning", ff["ruang_privat"])
        self.assertEqual(ff["suasana_tenang"]["atmosphere"], ["tenang"])
        # "Ruangan sejuk": "nyaman" (15/15 toko) bukan bukti sejuk.
        self.assertEqual(ff["ruangan_ac"]["atmosphere"], ["sejuk"])

    def test_attribute_pills_keep_supporting_fields(self):
        """Field atribut hanya penguat; tetap ada walau datanya belum tersedia."""
        for pill in FACILITY_ATTRIBUTE_PILLS:
            self.assertTrue(PILL_MAPPING[pill].get("facility_fields"), pill)


if __name__ == "__main__":
    unittest.main()

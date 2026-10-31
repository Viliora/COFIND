"""Kebijakan kurasi review_keywords: sparse = jangkar leksikal, bukan parafrase (itu tugas dense)."""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("COFIND_SEMANTIC_GATE", "false")

from hybrid_retrieval import tokenize_for_match
from pill_config import FACILITY_ATTRIBUTE_PILLS, PILL_MAPPING

MAX_KEYWORDS_ACTIVITY = 8
MAX_KEYWORDS_ATTRIBUTE = 7

# BM25 meratakan frasa jadi unigram: modifier/kata umum ini membawa query ke aspek lain.
# Contoh nyata: "kopi susunya manis banget" (dessert), "nge-charge laptop" (kerja),
# "luar biasa" (outdoor), "tanggal 24" (24 jam), "kopi dingin" (AC).
DRIFT_TOKENS = frozenset({
    "laptop", "manis", "kantor", "bisnis", "dokumen", "taman", "dingin", "cepat",
    "lancar", "stabil", "kencang", "bersih", "luas", "kenyang", "luar", "terbuka",
    "malam", "siang", "bersama", "ber", "produktif", "deadline", "buku",
})
# Kata fungsi dari frasa seperti "untuk rapat" / "bisa merokok" / "banyak colokan"
# menyentuh 40-70% review (baseline audit) tanpa membawa makna aspek.
FUNCTION_TOKENS = frozenset({
    "untuk", "buat", "di", "bisa", "ada", "banyak", "tidak", "enggak", "ga", "gak",
    "nggak", "cocok", "yang", "dan", "dengan", "tempat", "suasana", "menu",
})
# Token pendek hanya boleh bila memang istilah khas.
SHORT_TOKEN_ALLOW = frozenset({"ac", "wc", "ml", "24"})


def _keywords(pill: str) -> list:
    return list((PILL_MAPPING.get(pill) or {}).get("review_keywords") or [])


def _flat_tokens(pill: str) -> set:
    out = set()
    for kw in _keywords(pill):
        out.update(tokenize_for_match(kw))
    return out


class PillKeywordCurationTests(unittest.TestCase):
    def test_keyword_count_capped(self):
        for pill in PILL_MAPPING:
            cap = MAX_KEYWORDS_ATTRIBUTE if pill in FACILITY_ATTRIBUTE_PILLS else MAX_KEYWORDS_ACTIVITY
            self.assertLessEqual(len(_keywords(pill)), cap, f"{pill} melebihi {cap} keyword")

    def test_no_duplicate_after_normalization(self):
        """Varian ejaan yang dilipat slang normalizer = pekerjaan ganda untuk sparse."""
        for pill in PILL_MAPPING:
            seen = {}
            for kw in _keywords(pill):
                key = tuple(tokenize_for_match(kw))
                self.assertNotIn(key, seen, f"{pill}: '{kw}' duplikat '{seen.get(key)}'")
                seen[key] = kw

    def test_no_drift_prone_unigrams(self):
        for pill in PILL_MAPPING:
            bad = _flat_tokens(pill) & DRIFT_TOKENS
            self.assertFalse(bad, f"{pill}: token rawan drift {sorted(bad)}")

    def test_no_function_word_tokens(self):
        for pill in PILL_MAPPING:
            bad = _flat_tokens(pill) & FUNCTION_TOKENS
            self.assertFalse(bad, f"{pill}: kata fungsi {sorted(bad)}")

    def test_no_junk_short_tokens(self):
        for pill in PILL_MAPPING:
            bad = {t for t in _flat_tokens(pill) if len(t) < 3 and t not in SHORT_TOKEN_ALLOW}
            self.assertFalse(bad, f"{pill}: token pendek {sorted(bad)}")

    def test_distinctive_anchors_retained(self):
        # Bentuk kanonik setelah slang normalizer (wfc -> work from cafe, mabar -> main bareng,
        # colokan -> stopkontak).
        required = {
            "kerja": {"work", "cafe", "laptopan"},
            "bermain game": {"bareng", "mlbb"},
            "belajar": {"nugas", "skripsi"},
            "nongkrong_hangout": {"nongkrong", "hangout", "mengobrol"},
            "wifi_kencang": {"wifi"},
            "banyak_colokan_terminal": {"stopkontak"},
            "musholla": {"musholla"},
            "parkir_luas": {"parkir"},
            "dessert": {"cheesecake"},
            "smoking_area": {"smoking"},
            "toilet_bersih": {"toilet"},
        }
        for pill, anchors in required.items():
            missing = anchors - _flat_tokens(pill)
            self.assertFalse(missing, f"{pill} kehilangan jangkar {sorted(missing)}")

    def test_informal_terms_from_real_reviews_present(self):
        """Hasil ekspansi sekali jalan dari ulasan nyata (bukan parafrase generik)."""
        required = {
            "instagrammable": {"aesthetic"},
            "keluarga": {"babychair"},
            "banyak_colokan_terminal": {"charger"},
            "suasana_tenang": {"ketenangan"},
            "meeting_sosialisasi": {"berdiskusi"},
            "area_outdoor": {"semi"},
            "dessert": {"cake", "brownies"},
        }
        for pill, anchors in required.items():
            missing = anchors - _flat_tokens(pill)
            self.assertFalse(missing, f"{pill} belum memuat {sorted(missing)}")

    def test_keywords_follow_label_meaning(self):
        """Label = makna yang dituju; key hanya identitas teknis."""
        required = {
            "ruangan_ac": {"sejuk", "adem"},          # "Ruangan sejuk", bukan hanya AC
            "meeting_sosialisasi": {"pertemuan"},     # "Meeting/Pertemuan"
            "instagrammable": {"selfie"},             # "Feeds Hunter": foto untuk feed sosmed
        }
        for pill, anchors in required.items():
            missing = anchors - _flat_tokens(pill)
            self.assertFalse(missing, f"{pill} belum memuat {sorted(missing)}")


if __name__ == "__main__":
    unittest.main()

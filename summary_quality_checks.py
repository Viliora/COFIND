"""Unit test: validasi panjang ringkasan Step 5 (Gemini fallback)."""
import unittest

from app import (
    COFIND_SUMMARY_MIN_CHARS,
    _coerce_step5_summary_text,
    _extract_summary_field_loose,
    _invalid_llm_summary_reason,
    _plain_summary_from_llm_raw,
    _summary_sentence_count,
)


class SummaryQualityTests(unittest.TestCase):
    def test_rejects_ultra_short_gemini_json(self):
        shop = {'place_id': 'p1', 'name': 'Aming Coffee Podomoro'}
        raw = '{"summary":"Aming Coffee Podomoro dinilai cocok."}'
        summary = _coerce_step5_summary_text(raw, shop)
        reason = _invalid_llm_summary_reason(summary, shop, [shop])
        self.assertTrue(reason)
        self.assertIn('pendek', reason.lower())

    def test_accepts_multi_sentence_json(self):
        shop = {'place_id': 'p1', 'name': 'Haruna Cafe'}
        body = (
            'Haruna Cafe cocok untuk belajar karena suasananya tenang dan wifi stabil. '
            'Pengunjung menyebut colokan cukup di beberapa meja. '
            'Pelayanan ramah meski saat jam sibuk antrian sedikit panjang.'
        )
        raw = f'{{"summary":"{body}"}}'
        summary = _coerce_step5_summary_text(raw, shop)
        self.assertGreaterEqual(len(summary), COFIND_SUMMARY_MIN_CHARS)
        self.assertIsNone(_invalid_llm_summary_reason(summary, shop, [shop]))

    def test_loose_json_summary_extraction(self):
        body = (
            'Haruna Cafe cocok untuk belajar karena suasananya tenang dan wifi stabil. '
            'Pengunjung menyebut colokan cukup di beberapa meja.'
        )
        raw = f'```json\n{{"summary":"{body}"}}\n```'
        extracted = _extract_summary_field_loose(raw)
        self.assertIn('Haruna Cafe', extracted)
        self.assertGreaterEqual(len(extracted), 40)

    def test_plain_prose_coercion_when_long_enough(self):
        shop = {'place_id': 'p2', 'name': 'NUTRICULA'}
        prose = (
            'NUTRICULA menawarkan area kerja yang nyaman dengan pencahayaan cukup terang. '
            'Beberapa ulasan memuji kopi susu dan roti sebagai camilan saat nugas. '
            'Suasana umumnya kondusif meski kadang musik agak keras di sore hari.'
        )
        self.assertGreaterEqual(len(prose), COFIND_SUMMARY_MIN_CHARS)
        self.assertGreaterEqual(_summary_sentence_count(prose), 2)
        plain = _plain_summary_from_llm_raw(prose, shop)
        self.assertEqual(plain, prose)


if __name__ == '__main__':
    unittest.main()

"""Triase klausa: relevansi tinggi tidak boleh otomatis positif."""

import unittest
from unittest.mock import patch

from clause_triage import apply_clause_triage


class TestClauseTriageSentiment(unittest.TestCase):
    @patch("clause_triage.clause_triage_enabled", return_value=True)
    @patch("clause_triage.bi_encoder_scores")
    @patch("cross_encoder.cross_encoder_enabled", return_value=False)
    def test_high_bi_score_routes_to_absa_not_auto_positive(self, _ce, mock_bi, _enabled):
        clause = "wifi lemot tidak cocok untuk kerja"
        mock_bi.return_value = {clause: 0.95}
        telemetry: dict = {}
        need_absa, auto = apply_clause_triage([clause], "tempat kerja tenang", telemetry)
        self.assertIn(clause, need_absa)
        self.assertNotIn(clause, auto)
        self.assertGreaterEqual(int(telemetry.get("triaged_relevant_absa") or 0), 1)


if __name__ == "__main__":
    unittest.main()

"""Schema data/eval/eval_queries.json (query dari calon pengguna, bukan fixture dev)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

EVAL_QUERIES = Path(__file__).resolve().parents[1] / "data" / "eval" / "eval_queries.json"


class EvalQueriesSchemaTests(unittest.TestCase):
    def test_eval_queries_file_exists_and_schema(self):
        self.assertTrue(EVAL_QUERIES.is_file(), "data/eval/eval_queries.json wajib ada")
        data = json.loads(EVAL_QUERIES.read_text(encoding="utf-8"))
        self.assertEqual(data.get("schema_version"), 1)
        queries = data.get("queries")
        self.assertIsInstance(queries, list)
        ids = []
        for q in queries:
            self.assertIn(q.get("route"), ("pill", "free_text"))
            self.assertIn("input", q)
            qid = q.get("id")
            self.assertTrue(qid)
            ids.append(qid)
        self.assertEqual(len(ids), len(set(ids)), "id query harus unik")


if __name__ == "__main__":
    unittest.main()

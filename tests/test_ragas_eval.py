"""Unit test normalisasi dataset RAGAS (tanpa panggilan API)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "scripts" / "eval"
for _p in (ROOT, EVAL_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from ragas_dataset import load_cases, normalize_case  # noqa: E402


def test_normalize_case_maps_fields():
    case = {
        "id": "x1",
        "question": "  Q?  ",
        "contexts": ["a", "  b  "],
        "answer": "A",
        "ground_truth": "GT",
    }
    row = normalize_case(case)
    assert row["user_input"] == "Q?"
    assert row["retrieved_contexts"] == ["a", "b"]
    assert row["response"] == "A"
    assert row["reference"] == "GT"
    assert row["id"] == "x1"


def test_load_cases_json_wrapper(tmp_path):
    path = tmp_path / "data.json"
    path.write_text(
        json.dumps({"cases": [{"question": "hi", "answer": "ho"}]}),
        encoding="utf-8",
    )
    cases = load_cases(path)
    assert len(cases) == 1
    assert normalize_case(cases[0])["user_input"] == "hi"


def test_load_cases_jsonl(tmp_path):
    path = tmp_path / "data.jsonl"
    path.write_text('{"question": "a"}\n{"question": "b"}\n', encoding="utf-8")
    assert len(load_cases(path)) == 2


def test_ragas_smoke_dataset_file_exists():
    path = ROOT / "scripts" / "eval" / "ragas_smoke_dataset.json"
    cases = load_cases(path)
    assert len(cases) >= 3
    assert all(normalize_case(c)["user_input"] for c in cases)

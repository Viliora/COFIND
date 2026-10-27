"""Muat dan normalisasi case eval RAGAS (format Cofind → kolom RAGAS 0.4.x)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Union


def _as_str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        out: List[str] = []
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                out.append(text)
        return out
    text = str(value).strip()
    return [text] if text else []


def load_cases(path: Union[str, Path]) -> List[Dict[str, Any]]:
    """JSON `{ \"cases\": [...] }` atau JSONL (satu objek per baris)."""
    path = Path(path)
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []

    if path.suffix.lower() == ".jsonl":
        cases: List[Dict[str, Any]] = []
        for line_no, line in enumerate(raw.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as err:
                raise ValueError(f"JSONL baris {line_no} tidak valid: {err}") from err
            if isinstance(row, dict):
                cases.append(row)
        return cases

    data = json.loads(raw)
    if isinstance(data, list):
        return [c for c in data if isinstance(c, dict)]
    if isinstance(data, dict):
        cases = data.get("cases")
        if isinstance(cases, list):
            return [c for c in cases if isinstance(c, dict)]
    raise ValueError(f"Format dataset tidak dikenali: {path}")


def normalize_case(case: Dict[str, Any]) -> Dict[str, Any]:
    """
    Satu baris untuk HuggingFace Dataset / RAGAS SingleTurnSample.

    Kolom: user_input, retrieved_contexts, response, reference (+ id opsional).
    """
    user_input = (
        case.get("user_input")
        or case.get("question")
        or ""
    ).strip()

    contexts = _as_str_list(
        case.get("retrieved_contexts")
        or case.get("contexts")
        or case.get("reference_contexts")
    )

    response = (
        case.get("response")
        or case.get("answer")
        or ""
    ).strip()

    reference = (
        case.get("reference")
        or case.get("ground_truth")
        or ""
    ).strip()

    row: Dict[str, Any] = {
        "user_input": user_input,
        "retrieved_contexts": contexts,
        "response": response,
        "reference": reference,
    }
    if case.get("id") is not None:
        row["id"] = case.get("id")
    return row


def coverage_summary(case: Dict[str, Any]) -> Dict[str, Any]:
    """Ringkasan field untuk laporan tanpa memanggil RAGAS."""
    norm = normalize_case(case)
    return {
        "id": case.get("id"),
        "has_user_input": bool(norm["user_input"]),
        "has_response": bool(norm["response"]),
        "context_count": len(norm["retrieved_contexts"]),
        "has_reference": bool(norm["reference"]),
        "has_gold_place": bool(case.get("gold_place_id")),
    }

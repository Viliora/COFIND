"""Muat daftar query evaluasi (bukan fixture pytest)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVAL_QUERIES = ROOT / "data" / "eval" / "eval_queries.json"


def load_eval_queries(
    path: Optional[Path] = None,
    *,
    limit: Optional[int] = None,
    ids: Optional[List[str]] = None,
    pill_only: bool = False,
) -> List[Dict[str, Any]]:
    queries_path = path or DEFAULT_EVAL_QUERIES
    if not queries_path.is_file():
        raise FileNotFoundError(
            f"File query eval tidak ada: {queries_path}. "
            "Buat dari wawancara calon pengguna (lihat schema di file contoh)."
        )
    data = json.loads(queries_path.read_text(encoding="utf-8"))
    queries = list(data.get("queries") or [])
    if pill_only:
        queries = [q for q in queries if q.get("route") == "pill"]
    if ids:
        id_set = set(ids)
        queries = [q for q in queries if q.get("id") in id_set]
    if limit is not None:
        queries = queries[: max(0, limit)]
    return queries

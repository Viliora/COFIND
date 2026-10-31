"""Setiap COFIND_* di .env.example (non-komentar) harus dibaca di repo."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = ROOT / ".env.example"

# Env dokumentasi saja / legacy coverage — tidak wajib ada pembaca *.py
ALLOW_UNREFERENCED = frozenset({
    "COFIND_COVERAGE_BONUS",
    "COFIND_ACTIVITY_COVERAGE_SHARE",
    "COFIND_COVERAGE_SEMANTIC_MIN",
})

DEPRECATED_IN_COMMENTS = re.compile(r"Legacy|tidak dibaca", re.I)


def _env_names_from_example() -> set[str]:
    names: set[str] = set()
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key.startswith("COFIND_"):
            names.add(key)
    return names


def _grep_repo(pattern: str) -> bool:
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in {".py", ".md", ".jsx", ".tsx", ".js", ".ts"}:
            continue
        if "node_modules" in path.parts or ".venv" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if pattern in text:
            return True
    return False


def test_cofind_env_example_has_readers():
    missing = []
    for name in sorted(_env_names_from_example()):
        if name in ALLOW_UNREFERENCED:
            continue
        if not _grep_repo(name):
            missing.append(name)
    assert not missing, f"COFIND_* di .env.example tanpa referensi kode: {missing}"

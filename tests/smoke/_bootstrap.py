"""Bootstrap path untuk smoke test manual.

Smoke test hidup di tests/smoke/ tetapi mengimpor modul backend yang ada di root
repo (app, semantic_match, ...). Modul ini menaruh root repo di sys.path supaya
skrip bisa dijalankan langsung (`python tests/smoke/smoke_pipeline.py`) maupun
sebagai modul (`python -m tests.smoke.smoke_pipeline`).
"""

from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def repo_path(*parts: str) -> str:
    """Path absolut di dalam repo, tidak bergantung pada cwd saat dijalankan."""
    return os.path.join(REPO_ROOT, *parts)

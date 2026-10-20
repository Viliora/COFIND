"""Konfigurasi pytest: taruh root repo di sys.path.

Modul backend (app, llm_recommender, semantic_match, ...) ada di root repo,
sementara test hidup di tests/. Tanpa ini `import llm_recommender` gagal saat
pytest dijalankan dari root.
"""

from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

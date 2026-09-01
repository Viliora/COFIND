"""Lokasi bersama untuk cache runtime Cofind.

Folder cache/ di-gitignore. Dipakai rerank LLM, embedding semantik, dan
verdict sentimen klausa. Bukan source tree frontend.
"""

from __future__ import annotations

import os

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')

# Umur cache penilaian rerank LLM (hari). Satu ulasan baru pada kandidat
# sudah mengubah sidik jari, jadi masa berlaku ini hanya batas atas.
RERANK_CACHE_EXPIRY_DAYS = 7

"""
DEPRECATED — tidak dipakai pipeline rekomendasi aktif.

Pipeline Cofind sekarang: seed pill → BM25 hybrid → top-N (tanpa rerank).
File ini dipertahankan hanya untuk referensi historis / eksperimen lokal.
Jangan import dari app.py.
"""

from __future__ import annotations

import os
import threading
import math
from typing import List, Sequence, Tuple

_reranker_lock = threading.Lock()
_reranker = None
_reranker_model_id = None

RERANK_MODEL_ID = os.getenv(
    "COFIND_RERANK_MODEL",
    "cross-encoder/ms-marco-MiniLM-L-6-v2",
).strip()


def _ensure_reranker(model_id: str):
    global _reranker, _reranker_model_id
    with _reranker_lock:
        if _reranker is not None and _reranker_model_id == model_id:
            return _reranker
        from sentence_transformers import CrossEncoder

        _reranker = CrossEncoder(model_id)
        _reranker_model_id = model_id
        return _reranker


def rerank_candidates(query: str, candidates: Sequence[str], top_k: int | None = None) -> List[Tuple[int, float]]:
    """
    Return pasangan (candidate_index, score) diurutkan desc.
    """
    texts = [str(c or "") for c in candidates]
    if not texts:
        return []
    model = _ensure_reranker(RERANK_MODEL_ID)
    pairs = [[query, t] for t in texts]
    scores = model.predict(pairs)
    ranked = []
    for idx, score in enumerate(scores):
        raw = float(score)
        normalized = 1.0 / (1.0 + math.exp(-raw))
        ranked.append((idx, normalized))
    ranked.sort(key=lambda item: item[1], reverse=True)
    if top_k is not None and top_k > 0:
        ranked = ranked[:top_k]
    return ranked

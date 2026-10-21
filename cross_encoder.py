"""Cross-encoder reranker untuk triase klausa (opsional, COFIND_CROSS_ENCODER)."""

from __future__ import annotations

import os
import threading
from typing import List, Sequence

from logging_config import get_logger

logger = get_logger('semantic')

_model = None
_model_error: str | None = None
_lock = threading.Lock()


def cross_encoder_enabled() -> bool:
    raw = (os.getenv('COFIND_CROSS_ENCODER') or 'false').strip().lower()
    return raw in ('1', 'true', 'yes', 'on')


def cross_encoder_model_name() -> str:
    return (
        os.getenv('COFIND_CROSS_ENCODER_MODEL') or 'BAAI/bge-reranker-v2-m3'
    ).strip()


def _load_model():
    global _model, _model_error
    if _model is not None or _model_error is not None:
        return _model
    with _lock:
        if _model is not None or _model_error is not None:
            return _model
        try:
            from sentence_transformers import CrossEncoder

            _model = CrossEncoder(cross_encoder_model_name())
        except Exception as err:
            _model_error = str(err)[:200]
            logger.warning('CrossEncoder tidak dimuat: %s', _model_error)
        return _model


def score_pairs(query: str, texts: Sequence[str]) -> List[float]:
    """Skor relevansi query–teks; kosong jika modul mati atau gagal load."""
    if not cross_encoder_enabled() or not texts:
        return []
    model = _load_model()
    if model is None:
        return []
    q = str(query or '').strip()
    if not q:
        return []
    pairs = [[q, str(t or '')] for t in texts]
    try:
        scores = model.predict(pairs)
        return [float(s) for s in scores]
    except Exception as err:
        logger.warning('CrossEncoder predict gagal: %s', str(err)[:160])
        return []

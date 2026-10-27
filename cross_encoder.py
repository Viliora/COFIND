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
        os.getenv('COFIND_CROSS_ENCODER_MODEL')
        or 'jinaai/jina-reranker-v2-base-multilingual'
    ).strip()


def _is_jina_reranker_model(model_name: str) -> bool:
    lowered = (model_name or '').lower()
    return 'jina' in lowered and 'reranker' in lowered


def _patch_transformers_for_jina_reranker() -> None:
    """Jina v2 custom code masih mengimpor helper yang dihapus di transformers 5.x."""
    try:
        import torch
        from transformers.models.xlm_roberta import modeling_xlm_roberta as mod
    except Exception:
        return
    if hasattr(mod, 'create_position_ids_from_input_ids'):
        return

    def create_position_ids_from_input_ids(input_ids, padding_idx):
        mask = input_ids.ne(padding_idx).int()
        return (torch.cumsum(mask, dim=1) - 1) * mask

    mod.create_position_ids_from_input_ids = create_position_ids_from_input_ids


def _cross_encoder_trust_remote_code(model_name: str) -> bool:
    raw = (os.getenv('COFIND_CROSS_ENCODER_TRUST_REMOTE_CODE') or '').strip().lower()
    if raw in ('1', 'true', 'yes', 'on'):
        return True
    if raw in ('0', 'false', 'no', 'off'):
        return False
    return _is_jina_reranker_model(model_name)


def _load_model():
    global _model, _model_error
    if _model is not None or _model_error is not None:
        return _model
    with _lock:
        if _model is not None or _model_error is not None:
            return _model
        try:
            from sentence_transformers import CrossEncoder

            name = cross_encoder_model_name()
            kwargs = {}
            if _cross_encoder_trust_remote_code(name):
                kwargs['trust_remote_code'] = True
            if _is_jina_reranker_model(name):
                _patch_transformers_for_jina_reranker()
                kwargs.setdefault('model_kwargs', {'torch_dtype': 'auto'})
            _model = CrossEncoder(name, **kwargs)
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
        predict_kwargs = {}
        if _is_jina_reranker_model(cross_encoder_model_name()):
            predict_kwargs['convert_to_tensor'] = True
        scores = model.predict(pairs, **predict_kwargs)
        if hasattr(scores, 'detach'):
            scores = scores.detach().float().cpu().tolist()
        return [float(s) for s in scores]
    except Exception as err:
        logger.warning('CrossEncoder predict gagal: %s', str(err)[:160])
        return []

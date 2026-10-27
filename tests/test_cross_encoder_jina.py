"""Cross-encoder Jina: shim transformers + trust_remote_code (tanpa download jika model gagal)."""

import os
from unittest.mock import patch

from cross_encoder import (
    _cross_encoder_trust_remote_code,
    _is_jina_reranker_model,
    _patch_transformers_for_jina_reranker,
)


def test_jina_model_detection():
    assert _is_jina_reranker_model('jinaai/jina-reranker-v2-base-multilingual')
    assert not _is_jina_reranker_model('BAAI/bge-reranker-v2-m3')


def test_trust_remote_code_auto_for_jina():
    assert _cross_encoder_trust_remote_code('jinaai/jina-reranker-v2-base-multilingual') is True
    with patch.dict(os.environ, {'COFIND_CROSS_ENCODER_TRUST_REMOTE_CODE': 'false'}):
        assert _cross_encoder_trust_remote_code('jinaai/jina-reranker-v2-base-multilingual') is False


def test_transformers_shim_adds_position_id_helper():
    _patch_transformers_for_jina_reranker()
    from transformers.models.xlm_roberta import modeling_xlm_roberta as mod

    assert hasattr(mod, 'create_position_ids_from_input_ids')

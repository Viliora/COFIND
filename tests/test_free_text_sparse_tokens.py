"""Free-text keyword → token sparse (selaras dengan korpus BM25)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault('COFIND_SEMANTIC_GATE', 'false')

from bm25_utils import score_shops_bm25_review_level
from hybrid_retrieval import sparse_tokens_from_keywords, tokenize_for_match


def test_sparse_tokens_from_keywords_normalizes_slang():
    assert sparse_tokens_from_keywords(['wfc']) == ['work', 'from', 'cafe']
    assert sparse_tokens_from_keywords(['colokan']) == ['stopkontak']
    assert sparse_tokens_from_keywords(['wifi kencang']) == ['wifi', 'kencang']


def test_bm25_free_text_keyword_matches_normalized_corpus():
    profiles = [
        {
            'place_id': 'hit',
            'reviews': [{'text': 'Enak buat work from cafe seharian, wifi ok.'}],
        },
        {
            'place_id': 'miss',
            'reviews': [{'text': 'Kopinya pahit, parkir susah.'}],
        },
        {
            'place_id': 'f1',
            'reviews': [{'text': 'Suasana tenang untuk baca buku.'}],
        },
        {
            'place_id': 'f2',
            'reviews': [{'text': 'Harga standar kafe biasa.'}],
        },
    ]
    raw_tokens = ['wfc']
    raw_scores, _ = score_shops_bm25_review_level(
        profiles, raw_tokens, tokenize_for_match,
    )
    norm_scores, _ = score_shops_bm25_review_level(
        profiles, sparse_tokens_from_keywords(raw_tokens), tokenize_for_match,
    )
    assert raw_scores['hit'] == 0.0
    assert norm_scores['hit'] > norm_scores['miss']

"""Unit test pool CE vs retrieval."""

import os

from rerank_blend import effective_rerank_pool, rerank_candidate_pool


def test_effective_rerank_pool_caps_by_candidates(monkeypatch):
    monkeypatch.setenv('COFIND_CE_RERANK_CANDIDATES', '20')
    assert effective_rerank_pool(candidate_count=5) == 5
    assert effective_rerank_pool(candidate_count=0) == 0


def test_effective_rerank_pool_caps_by_env(monkeypatch):
    monkeypatch.setenv('COFIND_CE_RERANK_CANDIDATES', '7')
    assert effective_rerank_pool(candidate_count=30) == 7


def test_rerank_candidate_pool_default(monkeypatch):
    monkeypatch.delenv('COFIND_CE_RERANK_CANDIDATES', raising=False)
    assert rerank_candidate_pool() == 7

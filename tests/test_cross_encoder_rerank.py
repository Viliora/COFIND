"""Unit test CE rerank (mock score_pairs)."""

import os

os.environ['COFIND_CE_RERANK'] = 'true'
os.environ['COFIND_CROSS_ENCODER'] = 'true'

from cross_encoder_rerank import _normalize_scores, _short_reason, ce_rerank_candidates


def test_normalize_scores():
    assert _normalize_scores([0.0, 1.0]) == [0.0, 10.0]
    assert len(_normalize_scores([2.0, 2.0])) == 2


def test_short_reason():
    text = ' '.join(['kata'] * 25)
    reason = _short_reason(text, max_words=18)
    assert len(reason.split()) <= 19


def test_ce_rerank_candidates_mock(monkeypatch):
    monkeypatch.setattr('cross_encoder_rerank.score_pairs', lambda q, texts: [0.5 + 0.1 * i for i in range(len(texts))])
    monkeypatch.setattr('cross_encoder.cross_encoder_enabled', lambda: True)
    monkeypatch.setattr('cross_encoder_rerank.ce_rerank_enabled', lambda: True)

    candidates = [{
        'place_id': 'p1',
        'name': 'Test Cafe',
        'score': 0.42,
        'profile': {'reviews': [{'text': 'tempat enak buat nugas wifi kencang', 'rating': 5}]},
        'evidence': {
            'review_quotes': [{'quote': 'tempat enak buat nugas wifi kencang', 'rating': 5}],
        },
        'score_detail': {},
    }]
    result = ce_rerank_candidates(
        candidates,
        ['nugas'],
        pill_labels={'nugas': 'Nugas'},
        activity_pills=['nugas'],
        activity_tokens=['nugas'],
        activity_matcher={'pills': ['nugas'], 'phrases': ['nugas'], 'bm25_tokens': ['nugas']},
        activity_query_text='nugas skripsi',
    )
    assert result is not None
    assert result.get('ranked')
    tel = result.get('telemetry') or {}
    assert tel.get('backend') == 'cross_encoder'

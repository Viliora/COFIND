"""Query expansion (sinonim/slang via LLM) + document expansion (doc2query) untuk BM25."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest

os.environ.setdefault('COFIND_SEMANTIC_GATE', 'false')

from bm25_utils import build_bm25_review_index, score_shops_bm25_review_level
from hybrid_retrieval import score_bm25_for_hybrid_retrieval, tokenize_for_match


def _profile(pid: str, reviews: list[tuple[int, str]]) -> dict:
    return {
        'place_id': pid,
        'reviews': [{'id': rid, 'text': text} for rid, text in reviews],
    }


def _filler_profiles() -> list[dict]:
    # BM25Okapi: korpus 2 dokumen memberi IDF 0; filler menjaga IDF positif.
    texts = ['kopinya pahit sekali', 'parkiran sempit', 'harga murah meriah', 'pelayan ramah']
    return [_profile(f'filler-{i}', [(900 + i, t)]) for i, t in enumerate(texts)]


# --------------------------------------------------------------- query expansion


@pytest.fixture
def expansion_file(tmp_path, monkeypatch):
    path = tmp_path / 'query_expansion.json'
    path.write_text(json.dumps({
        'schema_version': 1,
        'global': {'stop_terms': ['tempat', 'enak']},
        'pills': {
            'kerja': {'expansions': ['remote', 'wfa', 'kerja', 'tempat', 'nugas kantor']},
        },
    }), encoding='utf-8')
    monkeypatch.setenv('COFIND_QUERY_EXPANSION_PATH', str(path))
    monkeypatch.setenv('COFIND_QUERY_EXPANSION', 'true')
    from query_expansion import reload_query_expansion_cache

    reload_query_expansion_cache()
    yield path
    reload_query_expansion_cache()


def test_sanitize_drops_stop_terms_duplicates_and_original_tokens(expansion_file):
    from query_expansion import sanitize_expansion_terms

    out = sanitize_expansion_terms(
        ['Remote', 'wfc', 'tempat', 'remote', 'ok', 'kerja remote', 'wfa'],
        original_tokens=['wfc', 'kerja'],
    )
    assert out == ['remote', 'wfa']


def test_sanitize_caps_term_count(expansion_file, monkeypatch):
    from query_expansion import sanitize_expansion_terms

    monkeypatch.setenv('COFIND_QUERY_EXPANSION_MAX_TERMS', '2')
    out = sanitize_expansion_terms(['alpha', 'bravo', 'charlie'], original_tokens=[])
    assert out == ['alpha', 'bravo']


def test_pill_expansion_tokens_read_json_and_exclude_original(expansion_file):
    from query_expansion import pill_query_expansion_tokens

    out = pill_query_expansion_tokens(['kerja'], original_tokens=['kerja'])
    assert out == ['remote', 'wfa', 'nugas', 'kantor']


def test_pill_expansion_disabled_returns_empty(expansion_file, monkeypatch):
    from query_expansion import pill_query_expansion_tokens

    monkeypatch.setenv('COFIND_QUERY_EXPANSION', 'false')
    assert pill_query_expansion_tokens(['kerja'], original_tokens=[]) == []


def test_free_text_expansion_tokens_from_intent(expansion_file):
    from query_expansion import free_text_expansion_tokens

    intent = {'keywords': ['colokan'], 'keyword_expansions': ['stopkontak', 'charger', 'colokan']}
    out = free_text_expansion_tokens(intent, original_tokens=['colokan'])
    # 'colokan' dinormalisasi slang menjadi 'stopkontak' -> sama dengan token asli.
    assert 'charger' in out
    assert 'colokan' not in out


def test_intent_parses_keyword_expansions():
    os.environ['COFIND_FREE_TEXT_INTENT'] = 'true'
    from free_text_intent import extract_search_intent

    def fake_chat(**_kwargs):
        return json.dumps({
            'keywords': ['wfc'],
            'dense_query': 'tempat kerja remote',
            'keyword_expansions': ['remote', 'wfa', ''],
        })

    result = extract_search_intent(
        'wfc', pill_labels={}, pill_mapping={}, chat_fn=fake_chat,
    )
    assert result['keyword_expansions'] == ['remote', 'wfa']


def test_intent_fallback_has_empty_expansions():
    from free_text_intent import extract_search_intent

    def exploding(**_kwargs):
        raise RuntimeError('down')

    result = extract_search_intent('wfc', pill_labels={}, pill_mapping={}, chat_fn=exploding)
    assert result['keyword_expansions'] == []


def test_bm25_expansion_rescues_shop_with_only_synonym():
    profiles = [
        _profile('exact', [(1, 'enak buat nugas seharian')]),
        _profile('synonym', [(2, 'enak buat skripsi seharian')]),
        _profile('none', [(3, 'kopinya pahit')]),
    ] + _filler_profiles()
    without, _ = score_shops_bm25_review_level(profiles, ['nugas'], tokenize_for_match)
    assert without['synonym'] == 0.0

    scores, meta = score_shops_bm25_review_level(
        profiles, ['nugas'], tokenize_for_match,
        expansion_tokens=['skripsi'], expansion_weight=0.5,
    )
    assert scores['synonym'] > 0.0
    assert scores['exact'] > scores['synonym']
    assert scores['none'] == 0.0
    assert meta['query_expansion_terms'] == 1


# ------------------------------------------------------------ document expansion


def test_review_index_appends_document_expansion_terms():
    profiles = [_profile('a', [(10, 'kopinya enak dan murah')])]
    _, _, corpus = build_bm25_review_index(
        profiles, tokenize_for_match, expansion_by_review_id={10: 'wfc nugas'},
    )
    # Expansion ikut normalisasi slang yang sama dengan teks ulasan (wfc -> work from cafe).
    assert 'work' in corpus[0]
    assert 'nugas' in corpus[0]


def test_bm25_doc_expansion_matches_predicted_query():
    profiles = [
        _profile('expanded', [(1, 'bisa duduk lama sambil buka laptop')]),
        _profile('plain', [(2, 'kopinya pahit sekali')]),
    ] + _filler_profiles()
    scores, meta = score_shops_bm25_review_level(
        profiles, ['nugas'], tokenize_for_match,
        expansion_by_review_id={1: 'nugas skripsi'},
    )
    assert scores['expanded'] > scores['plain']
    assert meta['doc_expansion_docs'] == 1


def test_parse_doc_expansion_response_validates_ids_and_terms():
    from review_expansion_store import parse_doc_expansion_response

    raw = json.dumps({'items': [
        {'id': 5, 'terms': ['wfc', ' kerja remote ', '', 'wfc']},
        {'id': 'bogus', 'terms': ['x']},
        {'id': 99, 'terms': ['tidak diminta']},
    ]})
    out = parse_doc_expansion_response(raw, allowed_ids={5, 6})
    assert out == {5: ['wfc', 'kerja remote']}


def test_load_doc_expansions_skips_stale_hash(monkeypatch):
    import review_expansion_store as store

    fresh_text = 'enak buat laptopan'
    rows = {
        1: (['wfc'], store.review_text_hash(fresh_text)),
        2: (['mabar'], store.review_text_hash('teks lama')),
    }
    monkeypatch.setattr(store, '_load_all_expansion_rows', lambda: rows)
    store.invalidate_cache()
    profiles = [_profile('a', [(1, fresh_text), (2, 'teks baru sudah diedit')])]
    out = store.doc_expansions_for_profiles(profiles)
    assert out == {1: 'wfc'}


def test_hybrid_bm25_uses_doc_expansion_when_enabled(monkeypatch):
    monkeypatch.setenv('COFIND_DOC_EXPANSION', 'true')
    monkeypatch.setenv('COFIND_BM25_UNIT', 'review')
    monkeypatch.setenv('COFIND_BM25_BACKEND', 'memory')
    profiles = [
        _profile('expanded', [(1, 'bisa duduk lama sambil buka laptop')]),
        _profile('plain', [(2, 'kopinya pahit sekali')]),
    ] + _filler_profiles()
    with patch(
        'review_expansion_store.doc_expansions_for_profiles',
        return_value={1: 'nugas'},
    ):
        scores, meta = score_bm25_for_hybrid_retrieval(profiles, ['nugas'])
    assert scores['expanded'] > scores['plain']
    assert meta['bm25_review']['doc_expansion_docs'] == 1


def test_hybrid_bm25_passes_query_expansion(monkeypatch):
    monkeypatch.setenv('COFIND_DOC_EXPANSION', 'false')
    monkeypatch.setenv('COFIND_BM25_UNIT', 'review')
    monkeypatch.setenv('COFIND_BM25_BACKEND', 'memory')
    profiles = [
        _profile('synonym', [(1, 'enak buat kerja remote')]),
        _profile('plain', [(2, 'kopinya pahit sekali')]),
    ] + _filler_profiles()
    scores, _ = score_bm25_for_hybrid_retrieval(
        profiles, ['nugas'], expansion_tokens=['remote'],
    )
    assert scores['synonym'] > scores['plain']

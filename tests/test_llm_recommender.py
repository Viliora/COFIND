"""Uji guardrail llm_recommender dengan LLM palsu (tanpa panggilan API)."""
import json
import os

os.environ.setdefault('COFIND_LLM_RERANK', 'true')
os.environ.setdefault('COFIND_LLM_RERANK_WEIGHT', '0.6')

import llm_recommender as lr

PILL_LABELS = {'kerja': 'Kerja', 'bersantai': 'Bersantai'}


def test_grounding():
    corpus = 'Tempatnya nyaman buat kerja, wifi kencang dan stopkontak banyak.'
    assert lr.text_is_grounded('wifi kencang dan stopkontak banyak', corpus)
    assert lr.text_is_grounded('Tempatnya nyaman buat kerja...stopkontak banyak', corpus)
    assert not lr.text_is_grounded('ada kolom renang dan bioskop pribadi', corpus)
    summary = 'Kesimpulan: cocok kerja. Kelebihannya, "wifi kencang dan stopkontak banyak".'
    assert lr.ungrounded_quotes(summary, corpus) == []
    halu = 'Kelebihannya, "tersedia ruang meeting privat berkapasitas 50 orang".'
    assert lr.ungrounded_quotes(halu, corpus)


def test_format_activity_context_block():
    mapping = {
        'kerja': {
            'label': 'Kerja',
            'definition': 'Cocok untuk WFC dan fokus.',
            'negative_scope': 'Bukan untuk karaoke.',
        },
    }
    block = lr.format_activity_context_block(['kerja'], pill_mapping=mapping, pill_labels=PILL_LABELS)
    assert 'Kebutuhan Aktivitas Pengguna' in block
    assert 'WFC' in block
    assert 'karaoke' in block.lower()
    assert lr.format_activity_context_block([], pill_mapping=mapping) == ''


def _candidate(place_id, name, score, quote):
    return {
        'place_id': place_id,
        'name': name,
        'score': score,
        'profile': {'reviews': [{'text': quote, 'rating': 5}]},
        'evidence': {
            'review_count': 12,
            'avg_user_rating': 4.5,
            'category_ratings': {'suasana': 4.6},
            'pill_stats': [{'pill': 'kerja', 'pill_label': 'Kerja', 'keyword_review_hits': 5}],
            'review_quotes': [{'quote': quote, 'rating': 5}],
        },
    }


def test_rerank_promotes_llm_choice_and_drops_hallucination():
    candidates = [
        _candidate('A', 'Kopi A', 0.80, 'Wifi lumayan tapi agak ramai kalau sore.'),
        _candidate('B', 'Kopi B', 0.60, 'Stopkontak di setiap meja dan wifi kencang buat kerja.'),
    ]

    def fake_chat(*, messages, max_tokens, temperature, **kwargs):
        return json.dumps([
            {
                'id': 2,
                'selected': True,
                'fit_score': 9.5,
                'reason': 'Stopkontak tiap meja dan wifi kencang mendukung kerja.',
                'supporting_index': 1,
                'caveat_index': 0,
                'matched_pills': ['kerja'],
            },
            {
                'place_id': 'A',
                'selected': False,
                'fit_score': 6.0,
                'reason': 'Wifi memadai namun ramai pada sore hari.',
                'supporting_index': 9,
                'evidence_quote': 'Ada ruang kerja privat ber-AC dengan 30 kursi.',
                'matched_pills': ['kerja'],
            },
            {'id': 99, 'fit_score': 10, 'reason': 'kandidat karangan'},
        ])

    result = lr.llm_rerank_candidates(
        candidates,
        ['kerja'],
        pill_labels=PILL_LABELS,
        chat_fn=fake_chat,
        keyword_line='kerja, wifi',
    )
    assert result is not None
    ranked = result['ranked']
    telemetry = result['telemetry']
    assert ranked is not None
    assert [r['place_id'] for r in ranked] == ['B', 'A'], ranked
    assert telemetry['unknown_place_ids'] == 1, telemetry
    assert telemetry['ungrounded_quotes'] == 1, telemetry
    assert ranked[0]['llm_fit']['evidence_grounded'] is True
    assert ranked[1]['llm_fit']['evidence_grounded'] is False
    assert ranked[1]['llm_fit']['evidence_quote'] == ''
    assert ranked[0]['llm_fit']['evidence_quote'].startswith('Stopkontak di setiap meja')
    assert telemetry['order_changed'] is True


def test_rerank_accepts_grounded_verbatim_quote():
    quote = 'Stopkontak di setiap meja dan wifi kencang buat kerja.'
    candidates = [_candidate('B', 'Kopi B', 0.60, quote)]

    def fake_chat(*, messages, max_tokens, temperature, **kwargs):
        return json.dumps([
            {
                'id': 1,
                'selected': True,
                'fit_score': 8,
                'reason': 'Stopkontak tiap meja dan wifi kencang.',
                'supporting_index': 1,
                'caveat_index': 0,
            },
        ])

    result = lr.llm_rerank_candidates(
        candidates, ['kerja'], pill_labels=PILL_LABELS, chat_fn=fake_chat,
    )
    assert result and result['ranked']
    fit = result['ranked'][0]['llm_fit']
    assert fit['evidence_quote'] == quote, fit
    assert fit['evidence_grounded'] is True
    assert result['telemetry']['ungrounded_quotes'] == 0


def test_generic_reason_is_dropped():
    quote = 'Colokan di tiap meja dan wifi kencang buat kerja lama.'

    def fake_chat(*, messages, max_tokens, temperature, **kwargs):
        return json.dumps([
            {
                'id': 1,
                'selected': True,
                'fit_score': 9,
                'reason': 'Banyak review menyebut tempat ini cocok untuk kerja.',
                'supporting_index': 1,
            },
        ])

    result = lr.llm_rerank_candidates(
        [_candidate('A', 'Kopi A', 0.7, quote)],
        ['kerja'], pill_labels=PILL_LABELS, chat_fn=fake_chat,
    )
    assert result and result['ranked']
    fit = result['ranked'][0]['llm_fit']
    assert fit['reason'] == '', fit
    assert result['telemetry']['dropped_reasons'] == 1


def test_rerank_falls_back_on_bad_output():
    def broken_chat(*, messages, max_tokens, temperature, **kwargs):
        return 'maaf saya tidak bisa membantu'

    result = lr.llm_rerank_candidates(
        [_candidate('A', 'Kopi A', 0.8, 'wifi kencang')],
        ['kerja'],
        pill_labels=PILL_LABELS,
        chat_fn=broken_chat,
    )
    assert result['ranked'] is None, result
    assert result['telemetry']['backend'] == 'llm_invalid'


def test_rerank_disabled_returns_none():
    prev = os.environ.get('COFIND_LLM_RERANK')
    os.environ['COFIND_LLM_RERANK'] = 'false'
    try:
        assert lr.rerank_enabled() is False
        result = lr.llm_rerank_candidates(
            [_candidate('A', 'Kopi A', 0.8, 'wifi kencang')],
            ['kerja'],
            pill_labels=PILL_LABELS,
            chat_fn=lambda **kw: '[]',
        )
        assert result is None
    finally:
        if prev is None:
            os.environ.pop('COFIND_LLM_RERANK', None)
        else:
            os.environ['COFIND_LLM_RERANK'] = prev

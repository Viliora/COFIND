"""Uji guardrail llm_recommender dengan LLM palsu (tanpa panggilan API)."""

import llm_recommender as lr

PILL_LABELS = {'kerja': 'Kerja', 'bersantai': 'Bersantai'}


def test_grounding():
    corpus = 'Tempatnya nyaman buat kerja, wifi kencang dan stopkontak banyak.'
    assert lr.text_is_grounded('wifi kencang dan stopkontak banyak', corpus)
    assert lr.text_is_grounded('Tempatnya nyaman buat kerja...stopkontak banyak', corpus)
    assert not lr.text_is_grounded('ada kolam renang dan bioskop pribadi', corpus)
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

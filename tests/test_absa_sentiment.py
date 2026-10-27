"""Unit test ABSA mapping (mock inferensi)."""

import os

os.environ.setdefault('COFIND_ABSA_ENABLED', 'true')

from absa_sentiment import _map_label, aspects_from_preference_line, classify_clause_for_aspects


def test_map_label():
    assert _map_label('positive') == 'positif'
    assert _map_label('NEGATIVE') == 'negatif'
    assert _map_label('neutral') == 'netral'


def test_aspects_from_preference_line():
    assert aspects_from_preference_line('Nugas, Wifi kencang') == ['Nugas', 'Wifi kencang']
    assert aspects_from_preference_line('') == ['preferensi umum']


def test_classify_clause_for_aspects_mock(monkeypatch):
    monkeypatch.setattr(
        'absa_sentiment.predict_pairs',
        lambda pairs: [('negatif', 0.9)],
    )
    out = classify_clause_for_aspects('wifinya lemot banget', ['Wifi kencang'])
    assert out['sentiment'] == 'negatif'
    assert out['relevant'] is True

"""Kutipan modal: klausa snippet + batas panjang."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from recommendation.quote_snippet import (  # noqa: E402
    MODAL_QUOTE_CHAR_LIMIT,
    snippet_for_modal_quote,
    truncate_modal_quote,
)


def test_snippet_picks_activity_clause_not_full_review():
    text = (
        'Suasana tenang dan nyaman untuk nongkrong. '
        'Tapi wifi lambat dan colokan sedikit. '
        'Cocok buat WFC karena meja luas dan internet stabil di lantai dua.'
    )
    snippet = snippet_for_modal_quote(text, preference_keywords=['wfc', 'wifi'])
    assert 'WFC' in snippet or 'wfc' in snippet.lower() or 'internet' in snippet.lower()
    assert len(snippet) <= MODAL_QUOTE_CHAR_LIMIT
    assert snippet != text


def test_truncate_modal_quote_adds_ellipsis():
    long_text = 'a' * (MODAL_QUOTE_CHAR_LIMIT + 50)
    out = truncate_modal_quote(long_text)
    assert out.endswith('...')
    assert len(out) <= MODAL_QUOTE_CHAR_LIMIT
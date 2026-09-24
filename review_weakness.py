"""
Deteksi keluhan dekat kata kunci preferensi (jendela token).

Lapis generik ini mencegah patch frasa per kasus: jika ulasan menyebut aspek
(wifi, parkir, toilet, …) dan ada sinyal lemah dalam jendela, dianggap negatif
terhadap klaim/badge aspek tersebut.
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence

from metadata_prior import _NEGATION_PREFIXES
from slang_normalize import normalize_text_with_slang

PREFERENCE_WEAKNESS_TOKEN_WINDOW = 6

_NEGATIVE_KEYWORD_FRAGMENTS = frozenset({
    'buruk', 'jelek', 'kotor', 'jorok', 'berisik', 'bising', 'mahal',
    'pelit', 'lambat', 'lemot', 'kecewa', 'zonk', 'parah', 'sampah',
    'ga enak', 'nggak enak', 'tidak enak', 'gak enak', 'bau', 'sumpek',
})

REVIEW_WEAKNESS_FRAGMENTS = _NEGATIVE_KEYWORD_FRAGMENTS | frozenset({
    'kurang', 'ramai', 'penuh', 'sempit', 'panas', 'gelap', 'lama',
    'antri', 'antre', 'noise', 'ribut', 'crowded', 'overpriced',
    'wifi lelet', 'wifi lemot', 'colokan kurang', 'parkir susah',
    'susah', 'sulit', 'ribet', 'minim', 'kekurangan',
    'kurang disarankan', 'kurang cocok', 'kurang direkomendasikan',
    'tidak disarankan', 'tidak cocok', 'tidak direkomendasikan',
    'ga cocok', 'gak cocok', 'nggak cocok', 'enggak cocok',
    'tidak recommended', 'kurang recommended',
})

_REVIEW_WEAKNESS_FRAGMENTS_SORTED = tuple(
    sorted(REVIEW_WEAKNESS_FRAGMENTS, key=len, reverse=True),
)

_ID_AFFIX_SUFFIXES = ('nya', 'lah', 'kah', 'pun', 'ku', 'mu', 'kan', 'an', 'i')
_ID_AFFIX_PREFIXES = ('ber', 'me', 'di', 'ter', 'se', 'pe', 'per', 'ke', 'nge', 'ng')


def normalize_keyword_phrase(value) -> str:
    return normalize_text_with_slang(value)


def _strip_match_token(token: str) -> str:
    return re.sub(r'^[^\w]+|[^\w]+$', '', str(token or '').lower(), flags=re.UNICODE)


def _token_matches_keyword_token(token: str, keyword: str) -> bool:
    tok = _strip_match_token(token)
    kw = str(keyword or '').strip().lower()
    if not tok or not kw:
        return False
    if '-' in tok:
        return any(_token_matches_keyword_token(part, kw) for part in tok.split('-') if part)
    if tok == kw:
        return True
    if len(kw) <= 3:
        return False
    for suf in _ID_AFFIX_SUFFIXES:
        if tok == kw + suf:
            return True
    for pre in _ID_AFFIX_PREFIXES:
        if tok == pre + kw:
            return True
        for suf in _ID_AFFIX_SUFFIXES:
            if tok == pre + kw + suf:
                return True
    return False


def find_keyword_token_spans(tokens: Sequence[str], keyword_variant: str):
    found = set()
    kw_tokens = [t for t in str(keyword_variant or '').split() if t]
    if not tokens or not kw_tokens:
        return found
    n = len(kw_tokens)
    for i in range(0, len(tokens) - n + 1):
        if all(_token_matches_keyword_token(tokens[i + j], kw_tokens[j]) for j in range(n)):
            found.add((i, i + n - 1))
    return found


def text_matches_keyword_phrase(text: str, keyword: str) -> bool:
    normalized_text = normalize_keyword_phrase(text)
    variant = normalize_keyword_phrase(keyword)
    if not normalized_text or not variant:
        return False
    return bool(find_keyword_token_spans(normalized_text.split(), variant))


def text_matches_any_keyword(text: str, keywords: Iterable[str]) -> bool:
    for kw in keywords or []:
        if text_matches_keyword_phrase(text, kw):
            return True
    return False


def _split_tokens_with_spans(line: str):
    if not line:
        return [], []
    tokens = []
    spans = []
    offset = 0
    for chunk in line.split(' '):
        if not chunk:
            continue
        idx = line.find(chunk, offset)
        if idx < 0:
            idx = line.index(chunk)
        tokens.append(chunk)
        spans.append((idx, idx + len(chunk)))
        offset = idx + len(chunk) + 1
    return tokens, spans


def _collect_preference_anchor_spans(tokens, spans, line, preference_keywords):
    found = set()
    if not line or not tokens or not preference_keywords:
        return found
    for kw in preference_keywords:
        variant = normalize_keyword_phrase(kw)
        if variant:
            found.update(find_keyword_token_spans(tokens, variant))
    return found


def _collect_weakness_token_spans(tokens, spans, line):
    found = set()
    if not line or not tokens:
        return found
    for frag in _REVIEW_WEAKNESS_FRAGMENTS_SORTED:
        for span in find_keyword_token_spans(tokens, frag):
            start = span[0]
            prev = tokens[start - 1] if start > 0 else ''
            if prev in _NEGATION_PREFIXES:
                continue
            found.add(span)
    return found


def _weakness_overlaps_anchor_window(weak_span, anchor_span, n_tokens, window):
    if n_tokens <= 0:
        return False
    a0, a1 = anchor_span
    w0, w1 = weak_span
    zone_lo = max(0, a0 - window)
    zone_hi = min(n_tokens - 1, a1 + window)
    return not (w1 < zone_lo or w0 > zone_hi)


def line_has_weakness_near_anchors(tokens, spans, line, preference_keywords, window):
    if not preference_keywords:
        return False
    anchors = _collect_preference_anchor_spans(tokens, spans, line, preference_keywords)
    weak = _collect_weakness_token_spans(tokens, spans, line)
    n = len(tokens)
    for anchor in anchors:
        for wsp in weak:
            if _weakness_overlaps_anchor_window(wsp, anchor, n, window):
                return True
    return False


def review_has_weakness_near_preference_keywords(
    text,
    preference_keywords,
    *,
    window: int | None = None,
) -> bool:
    if window is None:
        window = PREFERENCE_WEAKNESS_TOKEN_WINDOW
    if not preference_keywords:
        return False
    normalized_line = normalize_keyword_phrase(text)
    if not normalized_line:
        return False
    tokens, spans = _split_tokens_with_spans(normalized_line)
    return line_has_weakness_near_anchors(
        tokens, spans, normalized_line, preference_keywords, window,
    )

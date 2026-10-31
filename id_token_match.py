"""Token matching & affix variants (Bahasa Indonesia) — dipakai bersama helpers & review_weakness."""

from __future__ import annotations

import re
from typing import List, Tuple

ID_AFFIX_SUFFIXES = ('nya', 'lah', 'kah', 'pun', 'ku', 'mu', 'kan', 'an', 'i')
ID_AFFIX_PREFIXES = ('ber', 'me', 'di', 'ter', 'se', 'pe', 'per', 'ke', 'nge', 'ng')

BASE_NEGATIVE_KEYWORD_FRAGMENTS = frozenset({
    'buruk', 'jelek', 'kotor', 'jorok', 'berisik', 'bising', 'mahal',
    'pelit', 'lambat', 'lemot', 'kecewa', 'zonk', 'parah', 'sampah',
    'ga enak', 'nggak enak', 'tidak enak', 'gak enak', 'bau', 'sumpek',
})


def strip_match_token(token: str) -> str:
    return re.sub(r'^[^\w]+|[^\w]+$', '', str(token or '').lower(), flags=re.UNICODE)


def token_matches_keyword_token(token: str, keyword: str) -> bool:
    tok = strip_match_token(token)
    kw = str(keyword or '').strip().lower()
    if not tok or not kw:
        return False
    if '-' in tok:
        return any(token_matches_keyword_token(part, kw) for part in tok.split('-') if part)
    if tok == kw:
        return True
    if len(kw) <= 3:
        return False
    for suf in ID_AFFIX_SUFFIXES:
        if tok == kw + suf:
            return True
    for pre in ID_AFFIX_PREFIXES:
        if tok == pre + kw:
            return True
        for suf in ID_AFFIX_SUFFIXES:
            if tok == pre + kw + suf:
                return True
    return False


def split_tokens_with_spans(line: str) -> Tuple[List[str], List[Tuple[int, int]]]:
    if not line:
        return [], []
    tokens: List[str] = []
    spans: List[Tuple[int, int]] = []
    offset = 0
    for chunk in line.split(' '):
        if not chunk:
            offset += 1
            continue
        start = line.find(chunk, offset)
        if start < 0:
            start = offset
        end = start + len(chunk)
        tokens.append(chunk)
        spans.append((start, end))
        offset = end + 1
    return tokens, spans

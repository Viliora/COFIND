"""
Query expansion BM25: sinonim, slang, singkatan, dan ejaan informal hasil LLM.

Sumber expansion:
  - Pill: data/lexicon/query_expansion.json (`pills.<pill_id>.expansions`), dibangkitkan
    offline oleh scripts/build_pill_query_expansion.py lalu dikurasi manual. Sengaja
    terpisah dari `review_keywords` di pill_config.py (kebijakan kurasi ulasan nyata).
  - Free text: field `keyword_expansions` pada respons intent LLM (free_text_intent.py),
    jadi tidak ada panggilan LLM tambahan per request.

Expansion hanya masuk lane sparse (BM25) dengan bobot lebih rendah dari token asli;
dense tidak berubah.

Env:
  COFIND_QUERY_EXPANSION            aktifkan query expansion (default: false)
  COFIND_QUERY_EXPANSION_WEIGHT     bobot skor BM25 expansion vs query asli (default: 0.5)
  COFIND_QUERY_EXPANSION_MAX_TERMS  batas token expansion per query (default: 8)
  COFIND_QUERY_EXPANSION_PATH       path JSON (default: data/lexicon/query_expansion.json)
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Sequence

from logging_config import get_logger

logger = get_logger('recommend')

ROOT = Path(__file__).resolve().parent
DEFAULT_QUERY_EXPANSION_PATH = ROOT / 'data' / 'lexicon' / 'query_expansion.json'
_MIN_TOKEN_CHARS = 3


def _env_flag(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or '').strip().lower()
    if not raw:
        return default
    return raw in ('1', 'true', 'yes', 'on')


def query_expansion_enabled() -> bool:
    return _env_flag('COFIND_QUERY_EXPANSION', False)


def query_expansion_weight() -> float:
    raw = (os.getenv('COFIND_QUERY_EXPANSION_WEIGHT') or '').strip()
    try:
        value = float(raw) if raw else 0.5
    except ValueError:
        value = 0.5
    return max(0.0, min(1.0, value))


def query_expansion_max_terms() -> int:
    raw = (os.getenv('COFIND_QUERY_EXPANSION_MAX_TERMS') or '').strip()
    try:
        value = int(raw) if raw else 8
    except ValueError:
        value = 8
    return max(1, min(20, value))


def query_expansion_path() -> Path:
    raw = (os.getenv('COFIND_QUERY_EXPANSION_PATH') or '').strip()
    return Path(raw) if raw else DEFAULT_QUERY_EXPANSION_PATH


@lru_cache(maxsize=1)
def _load_query_expansion_file(path_str: str) -> Dict[str, Any]:
    path = Path(path_str)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception as err:
        logger.warning(f"query_expansion.json tidak valid ({path}): {str(err)[:160]}")
        return {}
    return data if isinstance(data, dict) else {}


def load_query_expansion() -> Dict[str, Any]:
    return _load_query_expansion_file(str(query_expansion_path()))


def reload_query_expansion_cache() -> None:
    _load_query_expansion_file.cache_clear()


def expansion_stop_terms() -> FrozenSet[str]:
    """Stop term JSON + stop generik leksikon aktivitas (token terlalu umum untuk BM25)."""
    from activity_lexicon import generic_activity_stop

    g = load_query_expansion().get('global') or {}
    own = frozenset(str(t).strip().lower() for t in (g.get('stop_terms') or []) if str(t or '').strip())
    try:
        generic = generic_activity_stop()
    except Exception:
        generic = frozenset()
    return own | generic


def _tokenize(text: str) -> List[str]:
    from hybrid_retrieval import tokenize_for_match

    return tokenize_for_match(text)


def sanitize_expansion_terms(
    terms: Iterable[object],
    *,
    original_tokens: Sequence[str],
) -> List[str]:
    """
    Frasa expansion LLM → token BM25 bersih: dinormalisasi slang yang sama dengan korpus,
    tanpa stop term, token pendek, duplikat, atau token yang sudah ada di query asli.
    """
    stops = expansion_stop_terms()
    original = set()
    for tok in original_tokens or []:
        original.update(_tokenize(str(tok or '')) or [str(tok or '').lower()])
    limit = query_expansion_max_terms()
    out: List[str] = []
    seen = set()
    for term in terms or []:
        for tok in _tokenize(str(term or '')):
            if len(tok) < _MIN_TOKEN_CHARS or tok in stops or tok in original or tok in seen:
                continue
            seen.add(tok)
            out.append(tok)
            if len(out) >= limit:
                return out
    return out


def pill_expansion_phrases(pill: str) -> List[str]:
    pills = load_query_expansion().get('pills') or {}
    spec = pills.get(pill) if isinstance(pills, dict) else None
    if not isinstance(spec, dict):
        return []
    return [str(t).strip() for t in (spec.get('expansions') or []) if str(t or '').strip()]


def pill_query_expansion_tokens(
    pills: Sequence[str],
    *,
    original_tokens: Sequence[str],
) -> List[str]:
    if not query_expansion_enabled():
        return []
    phrases: List[str] = []
    for pill in pills or []:
        phrases.extend(pill_expansion_phrases(str(pill or '')))
    return sanitize_expansion_terms(phrases, original_tokens=original_tokens)


def free_text_expansion_tokens(
    intent_result: Optional[dict],
    *,
    original_tokens: Sequence[str],
) -> List[str]:
    if not query_expansion_enabled():
        return []
    terms = (intent_result or {}).get('keyword_expansions') or []
    return sanitize_expansion_terms(terms, original_tokens=original_tokens)

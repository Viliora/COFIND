"""Muat leksikon aktivitas terpusat (data/lexicon/activity_lexicon.json)."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent
DEFAULT_LEXICON_PATH = ROOT / "data" / "lexicon" / "activity_lexicon.json"

ACTIVITY_PILL_KEYS = (
    "belajar",
    "kerja",
    "bermain game",
    "meeting_sosialisasi",
    "keluarga",
    "instagrammable",
    "nongkrong_hangout",
)

_GAME_WORD_RE = re.compile(
    r"^(?:nge)?game(?:nya|an)?$|^gaming$|^gamers?$",
    re.IGNORECASE,
)
_HIDDEN_GEM_TYPO_RE = re.compile(r"\bhidden\s+games?\b")


def lexicon_path() -> Path:
    import os

    raw = (os.getenv("COFIND_ACTIVITY_LEXICON_PATH") or "").strip()
    return Path(raw) if raw else DEFAULT_LEXICON_PATH


@lru_cache(maxsize=1)
def load_activity_lexicon() -> dict[str, Any]:
    path = lexicon_path()
    if not path.is_file():
        raise FileNotFoundError(f"Leksikon aktivitas tidak ditemukan: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("pills"), dict):
        raise ValueError("activity_lexicon.json: field 'pills' wajib berupa objek")
    return data


def reload_activity_lexicon_cache() -> None:
    load_activity_lexicon.cache_clear()


def _frozenset_from_list(items: Optional[Sequence[str]]) -> FrozenSet[str]:
    return frozenset(str(x).strip() for x in (items or []) if str(x or "").strip())


def generic_activity_stop() -> FrozenSet[str]:
    g = load_activity_lexicon().get("global") or {}
    return _frozenset_from_list(g.get("generic_activity_stop"))


def rejection_phrases() -> Tuple[str, ...]:
    g = load_activity_lexicon().get("global") or {}
    return tuple(str(x).strip() for x in (g.get("rejection_phrases") or []) if str(x).strip())


def acronym_context_tokens() -> FrozenSet[str]:
    g = load_activity_lexicon().get("global") or {}
    return _frozenset_from_list(g.get("acronym_context_tokens"))


def pill_lexicon(pill: str) -> dict[str, Any]:
    pills = load_activity_lexicon().get("pills") or {}
    spec = pills.get(pill)
    if not isinstance(spec, dict):
        return {}
    return spec


def activity_extra_phrases() -> Dict[str, Tuple[str, ...]]:
    out: Dict[str, Tuple[str, ...]] = {}
    pills = load_activity_lexicon().get("pills") or {}
    for pill, spec in pills.items():
        if isinstance(spec, dict):
            phrases = tuple(str(p).strip() for p in (spec.get("extra_phrases") or []) if str(p).strip())
            if phrases:
                out[str(pill)] = phrases
    return out


def activity_whole_words() -> Dict[str, FrozenSet[str]]:
    out: Dict[str, FrozenSet[str]] = {}
    pills = load_activity_lexicon().get("pills") or {}
    for pill, spec in pills.items():
        if isinstance(spec, dict):
            out[str(pill)] = _frozenset_from_list(spec.get("whole_words"))
    return out


def activity_short_acronyms() -> Dict[str, FrozenSet[str]]:
    out: Dict[str, FrozenSet[str]] = {}
    pills = load_activity_lexicon().get("pills") or {}
    for pill, spec in pills.items():
        if isinstance(spec, dict):
            ac = _frozenset_from_list(spec.get("short_acronyms"))
            if ac:
                out[str(pill)] = ac
    return out


def activity_stop_tokens_by_pill() -> Dict[str, FrozenSet[str]]:
    generic = generic_activity_stop()
    out: Dict[str, FrozenSet[str]] = {}
    pills = load_activity_lexicon().get("pills") or {}
    for pill, spec in pills.items():
        if not isinstance(spec, dict):
            continue
        extra = _frozenset_from_list(spec.get("stop_tokens"))
        out[str(pill)] = generic | extra
    return out


def review_keywords_for_activity_pill(pill: str) -> List[str]:
    spec = pill_lexicon(pill)
    return [str(k).strip() for k in (spec.get("review_keywords") or []) if str(k).strip()]


def apply_activity_lexicon_to_mapping(pill_mapping: dict) -> None:
    """Sinkronkan review_keywords pill aktivitas dari leksikon JSON."""
    for pill in ACTIVITY_PILL_KEYS:
        entry = pill_mapping.get(pill)
        if not isinstance(entry, dict):
            continue
        kws = review_keywords_for_activity_pill(pill)
        if kws:
            entry["review_keywords"] = kws


def game_word_re() -> re.Pattern[str]:
    return _GAME_WORD_RE


def hidden_gem_typo_re() -> re.Pattern[str]:
    return _HIDDEN_GEM_TYPO_RE

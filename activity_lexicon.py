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


def _dedupe_terms(items: Optional[Sequence[str]]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for raw in items or []:
        text = str(raw).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _legacy_terms_from_spec(spec: dict[str, Any]) -> List[str]:
    """Schema v1: gabung review_keywords, extra_phrases, whole_words."""
    merged: List[str] = []
    for key in ("review_keywords", "extra_phrases", "whole_words"):
        merged.extend(str(x).strip() for x in (spec.get(key) or []) if str(x or "").strip())
    return _dedupe_terms(merged)


def generic_activity_stop() -> FrozenSet[str]:
    g = load_activity_lexicon().get("global") or {}
    return _frozenset_from_list(g.get("generic_activity_stop"))


def rejection_phrases() -> Tuple[str, ...]:
    g = load_activity_lexicon().get("global") or {}
    return tuple(str(x).strip() for x in (g.get("rejection_phrases") or []) if str(x).strip())


def pill_lexicon(pill: str) -> dict[str, Any]:
    pills = load_activity_lexicon().get("pills") or {}
    spec = pills.get(pill)
    if not isinstance(spec, dict):
        return {}
    return spec


def activity_terms(pill: str) -> List[str]:
    """Jangkar leksikal tunggal: sparse BM25, matcher, activity_text_score."""
    spec = pill_lexicon(pill)
    if not spec:
        return []
    raw = spec.get("terms")
    if isinstance(raw, list) and raw:
        return _dedupe_terms(raw)
    return _legacy_terms_from_spec(spec)


def activity_terms_by_pill() -> Dict[str, Tuple[str, ...]]:
    out: Dict[str, Tuple[str, ...]] = {}
    pills = load_activity_lexicon().get("pills") or {}
    for pill in pills:
        terms = activity_terms(str(pill))
        if terms:
            out[str(pill)] = tuple(terms)
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
    """Alias: isi review_keywords di PILL_MAPPING dari terms."""
    return list(activity_terms(pill))


def apply_activity_lexicon_to_mapping(pill_mapping: dict) -> None:
    """Sinkronkan review_keywords pill aktivitas dari leksikon (semua terms)."""
    for pill in ACTIVITY_PILL_KEYS:
        entry = pill_mapping.get(pill)
        if not isinstance(entry, dict):
            continue
        terms = activity_terms(pill)
        if terms:
            entry["review_keywords"] = terms


def game_word_re() -> re.Pattern[str]:
    return _GAME_WORD_RE


def hidden_gem_typo_re() -> re.Pattern[str]:
    return _HIDDEN_GEM_TYPO_RE

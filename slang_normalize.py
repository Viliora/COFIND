"""
Normalisasi slang Indonesia untuk matching review / BM25.

Memuat data/indonesia_slang_map.json
dan menggabungkannya dengan canonical replacements domain coffee shop.
Domain replacements selalu menang atas kamus slang umum.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from functools import lru_cache
from typing import Dict

_ROOT = os.path.dirname(os.path.abspath(__file__))
_SLANG_JSON_PATH = os.path.join(_ROOT, 'data', 'indonesia_slang_map.json')

# Domain coffee shop / fasilitas — prioritas tertinggi.
DOMAIN_CANONICAL_REPLACEMENTS: Dict[str, str] = {
    'wi fi': 'wifi',
    'wi-fi': 'wifi',
    'wifi': 'wifi',
    'shalat': 'salat',
    'sholat': 'salat',
    'solat': 'salat',
    'mushola': 'musholla',
    'musola': 'musholla',
    'musolla': 'musholla',
    'colokan': 'stopkontak',
    'cas': 'charge',
    'ngecas': 'charge',
    'parkiran': 'parkir',
    # Domain slang yang sering muncul di review coffee shop
    'wfc': 'work from cafe',
    'nongki': 'nongkrong',
    'nongky': 'nongkrong',
    'mabar': 'main bareng',
    'ngegame': 'main game',
    'ngopi': 'minum kopi',
}


def _basic_clean(text: str) -> str:
    text = str(text or '').strip().lower()
    if not text:
        return ''
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace('-', ' ')
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


@lru_cache(maxsize=1)
def load_slang_map() -> Dict[str, str]:
    """Load slang map dari JSON; kosong jika file belum ada."""
    if not os.path.exists(_SLANG_JSON_PATH):
        print(f'[WARN] Slang map tidak ditemukan: {_SLANG_JSON_PATH}')
        return {}
    try:
        with open(_SLANG_JSON_PATH, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        raw = payload.get('map') if isinstance(payload, dict) else payload
        if not isinstance(raw, dict):
            return {}
        out: Dict[str, str] = {}
        for src, dest in raw.items():
            s = _basic_clean(src)
            d = _basic_clean(dest)
            if not s or not d or s == d or ' ' in s:
                continue
            out[s] = d
        return out
    except Exception as err:
        print(f'[WARN] Gagal load slang map: {err}')
        return {}


@lru_cache(maxsize=1)
def get_replacement_pairs() -> tuple:
    """
    Daftar (src, dest) untuk normalisasi, diurutkan panjang src menurun.
    Domain canonical menang; slang mengisi sisanya.
    """
    merged: Dict[str, str] = {}
    slang = load_slang_map()
    merged.update(slang)
    # Domain override terakhir
    for src, dest in DOMAIN_CANONICAL_REPLACEMENTS.items():
        merged[_basic_clean(src)] = _basic_clean(dest)

    pairs = [(s, d) for s, d in merged.items() if s and d and s != d]
    pairs.sort(key=lambda item: len(item[0]), reverse=True)
    return tuple(pairs)


@lru_cache(maxsize=1)
def _compiled_replacements() -> tuple:
    """
    Pisah aturan jadi dua bentuk agar normalisasi tidak perlu ribuan regex:
      - token_map: src satu kata -> lookup dict O(1) per token
      - multiword: src berisi spasi (jumlahnya sedikit) -> satu regex gabungan
    """
    token_map: Dict[str, str] = {}
    multiword = []
    for src, dest in get_replacement_pairs():
        if ' ' in src:
            multiword.append((src, dest))
        else:
            token_map[src] = dest

    multiword_re = None
    if multiword:
        # Urutan panjang menurun sudah dijamin get_replacement_pairs().
        pattern = '|'.join(re.escape(src) for src, _ in multiword)
        multiword_re = re.compile(rf'\b(?:{pattern})\b')
    return token_map, dict(multiword), multiword_re


# Ekspansi bisa memunculkan token baru (mis. "wfc" -> "work from cafe").
# Dua lintasan sudah cukup dan tetap jauh lebih murah daripada regex per aturan.
_MAX_TOKEN_PASSES = 2


def _apply_token_map(text: str, token_map: Dict[str, str]) -> str:
    for _ in range(_MAX_TOKEN_PASSES):
        tokens = text.split()
        if not tokens:
            return ''
        changed = False
        out = []
        for token in tokens:
            replacement = token_map.get(token)
            if replacement is None:
                out.append(token)
                continue
            out.append(replacement)
            changed = True
        text = ' '.join(out)
        if not changed:
            break
    return text


@lru_cache(maxsize=20000)
def _normalize_cached(value: str) -> str:
    text = _basic_clean(value)
    if not text:
        return ''
    token_map, multiword_map, multiword_re = _compiled_replacements()
    if multiword_re is not None:
        text = multiword_re.sub(lambda m: multiword_map[m.group(0)], text)
    text = _apply_token_map(text, token_map)
    return re.sub(r'\s+', ' ', text).strip()


def normalize_text_with_slang(value: str) -> str:
    """
    Normalisasi teks: lowercase, strip aksen, lalu canonical + slang map.
    Cocok untuk keyword match dan tokenisasi BM25.
    """
    if not isinstance(value, str):
        value = str(value or '')
    return _normalize_cached(value)


def tokenize_normalized(value: str) -> list:
    """Token alnum setelah normalisasi slang; buang token 1 karakter."""
    text = normalize_text_with_slang(value)
    if not text:
        return []
    return [t for t in text.split() if len(t) > 1]

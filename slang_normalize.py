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


def normalize_text_with_slang(value: str) -> str:
    """
    Normalisasi teks: lowercase, strip aksen, lalu canonical + slang map.
    Cocok untuk keyword match dan tokenisasi BM25.
    """
    text = _basic_clean(value)
    if not text:
        return ''
    for src, dest in get_replacement_pairs():
        if not src:
            continue
        text = re.sub(rf'\b{re.escape(src)}\b', dest, text)
    return re.sub(r'\s+', ' ', text).strip()


def tokenize_normalized(value: str) -> list:
    """Token alnum setelah normalisasi slang; buang token 1 karakter."""
    text = normalize_text_with_slang(value)
    if not text:
        return []
    return [t for t in text.split() if len(t) > 1]

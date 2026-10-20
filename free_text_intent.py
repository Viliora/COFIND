"""
Deteksi intent & ekstraksi keyword dari free text user (opsional, pelengkap pill).

Konteks: ShopList menyediakan kotak kata kunci bebas (maks 50 karakter,
divalidasi di app.py) sebagai alternatif saat preferensi user tidak ada di
pill yang disediakan. Pill dan free text saling eksklusif di satu request
(lihat _read_recommendation_preferences di app.py) — modul ini hanya aktif
saat user memilih jalur free text.

LLM mengekstrak `keywords` + `dense_query` untuk hybrid retrieval
(BM25 + dense/ANN → RRF). Field pill opsional (hint telemetri saja);
routing pipeline tidak lagi meng-upgrade request ke jalur pill.

Fallback (LLM nonaktif / gagal / output tidak valid): tokenisasi deterministik
atas teks mentah sebagai keyword, tanpa pill match. Pipeline tetap jalan
(degradasi, bukan error) — konsisten dengan filosofi modul lain di app.py
(llm_recommender, llm_clause_sentiment) yang selalu punya jalur fallback.

Env:
  COFIND_FREE_TEXT_INTENT   aktifkan deteksi intent via LLM (default: true)
"""

from __future__ import annotations

import os
import re
from typing import Callable, Dict, List, Optional

from logging_config import get_logger

logger = get_logger('recommend')

MAX_FREE_TEXT_CHARS = 50

_TOKEN_RE = re.compile(r'[a-z0-9]+', re.IGNORECASE)


def _env_flag(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or '').strip().lower()
    if not raw:
        return default
    return raw in ('1', 'true', 'yes', 'on')


def free_text_intent_enabled() -> bool:
    return _env_flag('COFIND_FREE_TEXT_INTENT', True)


def _fallback_keywords(text: str) -> List[str]:
    """Tokenisasi deterministik tanpa LLM — dipakai saat LLM off/gagal."""
    tokens = [t.lower() for t in _TOKEN_RE.findall(str(text or '')) if len(t) > 1]
    seen = set()
    out = []
    for tok in tokens:
        if tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
    return out


def _empty_result(raw: str, *, backend: str, error: Optional[str] = None) -> Dict[str, object]:
    telemetry = {'backend': backend, 'input_chars': len(raw)}
    if error:
        telemetry['error'] = error[:200]
    return {
        'matched_pill': None,
        'matched_attribute_pills': [],
        'keywords': _fallback_keywords(raw),
        'dense_query': raw,
        'telemetry': telemetry,
    }


def extract_search_intent(
    text: str,
    *,
    pill_labels: Dict[str, str],
    pill_mapping: Dict[str, dict],
    chat_fn: Callable[..., str],
    parse_json_fn: Optional[Callable] = None,
    max_tokens: int = 220,
    temperature: float = 0.0,
) -> Dict[str, object]:
    """
    Return:
      {
        'matched_pill': str|None,            # hint opsional (telemetri), tidak mengubah routing
        'matched_attribute_pills': [str],    # hint opsional fasilitas
        'keywords': [str],                   # untuk BM25 (RRF list sparse)
        'dense_query': str,                  # untuk embedding/ANN (RRF list dense)
        'telemetry': {...},
      }

    Tidak pernah raise — kegagalan apa pun berujung ke fallback keyword mentah
    supaya pipeline rekomendasi tidak pernah gagal total karena tahap ini.
    """
    raw = str(text or '').strip()[:MAX_FREE_TEXT_CHARS]
    if not raw:
        return _empty_result(raw, backend='empty')
    if not free_text_intent_enabled():
        return _empty_result(raw, backend='disabled')

    pill_lines = []
    for pill_id, label in (pill_labels or {}).items():
        spec = (pill_mapping or {}).get(pill_id) or {}
        definition = re.sub(r'\s+', ' ', str(spec.get('definition') or '')).strip()
        line = f'- {pill_id}: {label}'
        if definition:
            line += f' — {definition[:120]}'
        pill_lines.append(line)
    pill_catalog = '\n'.join(pill_lines[:40])  # batasi panjang prompt

    prompt = (
        'Anda mendeteksi intent pencarian coffee shop dari kata kunci singkat yang '
        'diisi pengguna (bahasa Indonesia, maksimal 50 karakter, BUKAN kalimat panjang).\n\n'
        f'Kata kunci pengguna: "{raw}"\n\n'
        'Referensi pill sistem (opsional, hanya hint — routing TIDAK wajib cocok pill):\n'
        f'{pill_catalog}\n\n'
        'Balas HANYA JSON (tanpa markdown) dengan struktur:\n'
        '{"matched_pill": null, "matched_attribute_pills": [], '
        '"keywords": ["..."], "dense_query": "...", '
        '"query_class": "standard", "impossible_detail": null, '
        '"alternative_keywords": []}\n\n'
        'Aturan ketat:\n'
        '- keywords (WAJIB): 1-8 token/frasa pencarian bersih dari niat user; buang kata filler '
        '("cari", "coffee shop", "tempat", "untuk"). Pertahankan istilah fasilitas/aktivitas user '
        '(mis. wfc, musholla, colokan, wifi).\n'
        '- dense_query (WAJIB): satu kalimat pendek Bahasa Indonesia untuk semantic search '
        '(parafrase niat user, bukan salin mentah jika terlalu panjang).\n'
        '- matched_pill / matched_attribute_pills: opsional; isi null/[] kecuali user jelas '
        'meminta satu pill persis dari daftar; jangan paksa mapping pill.\n'
        '- query_class (WAJIB): salah satu dari '
        '"standard" | "negative_sentiment" | "false_presupposition" | "off_domain".\n'
        '  • negative_sentiment: niat valid tapi negatif/superlatif (mis. "paling jelek", '
        '"terburuk") — tetap ekstrak keywords, jangan tolak.\n'
        '  • false_presupposition: user mengasumsikan fitur/konsep yang tidak realistis '
        'untuk coffee shop di dataset (mis. dinosaurus, kolam renang olimpik) — isi '
        'impossible_detail singkat + alternative_keywords tematik terdekat (unik, estetik, '
        'game, keluarga, dll.) tanpa mengarang fitur impossible.\n'
        '  • off_domain: teks acak, spam, atau bukan pencarian coffee shop/wisata kafe — '
        'keywords boleh [] dan dense_query kosong.\n'
        '- impossible_detail: string singkat constraint yang tidak ada bukti, atau null.\n'
        '- alternative_keywords: 1-6 token alternatif pencarian (hanya untuk false_presupposition).\n'
        '- Jangan mengarang id pill di luar daftar.'
    )

    try:
        raw_response = chat_fn(
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
            usage_stage='free_text_intent',
        )
        if parse_json_fn is not None:
            parsed = parse_json_fn(
                raw_response, expected='object', usage_stage='free_text_intent_repair',
            )
        else:
            import json as _json
            parsed = _json.loads(raw_response)

        if not isinstance(parsed, dict):
            raise ValueError('respons intent LLM bukan objek JSON')

        matched_pill_raw = parsed.get('matched_pill')
        matched_pill = str(matched_pill_raw).strip() if matched_pill_raw else None
        if matched_pill and matched_pill not in (pill_mapping or {}):
            matched_pill = None

        matched_attrs = []
        for item in parsed.get('matched_attribute_pills') or []:
            candidate = str(item or '').strip()
            if candidate and candidate in (pill_mapping or {}) and candidate not in matched_attrs:
                matched_attrs.append(candidate)

        keywords = [str(k).strip() for k in (parsed.get('keywords') or []) if str(k or '').strip()]
        if not keywords:
            keywords = _fallback_keywords(raw)

        dense_query = str(parsed.get('dense_query') or '').strip() or raw
        query_class = str(parsed.get('query_class') or 'standard').strip().lower() or 'standard'
        impossible_detail = parsed.get('impossible_detail')
        if impossible_detail is not None:
            impossible_detail = str(impossible_detail).strip() or None
        alternative_keywords = [
            str(k).strip() for k in (parsed.get('alternative_keywords') or []) if str(k or '').strip()
        ]

        return {
            'matched_pill': matched_pill,
            'matched_attribute_pills': matched_attrs,
            'keywords': keywords,
            'dense_query': dense_query,
            'query_class': query_class,
            'impossible_detail': impossible_detail,
            'alternative_keywords': alternative_keywords,
            'telemetry': {'backend': 'llm', 'input_chars': len(raw)},
        }
    except Exception as err:
        logger.warning(
            f"extract_search_intent LLM gagal, fallback keyword mentah: {str(err)[:200]}"
        )
        return _empty_result(raw, backend='fallback', error=str(err))

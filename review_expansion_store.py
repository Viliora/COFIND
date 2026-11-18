"""
Document expansion (doc2query) per ulasan untuk BM25.

LLM memprediksi query/kata yang dijawab sebuah ulasan (sinonim, slang, singkatan).
Hasil disimpan di tabel Postgres `review_expansions` (satu baris per review_id),
dibangun offline oleh scripts/build_review_expansions.py, lalu ditempel ke token
ulasan saat indeks BM25 per-ulasan dibangun (bm25_utils.build_bm25_review_index).

`source_text_hash` menandai versi teks ulasan; bila ulasan diedit, expansion lama
diabaikan sampai skrip dijalankan ulang.

Env:
  COFIND_DOC_EXPANSION                aktifkan document expansion di BM25 (default: false)
  COFIND_DOC_EXPANSION_CACHE_SECONDS  umur cache proses tabel expansion (default: 300)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from logging_config import get_logger

logger = get_logger('recommend')

TABLE = 'review_expansions'
DOC_EXPANSION_PROMPT_VERSION = 'v1'
MAX_TERMS_PER_REVIEW = 10
MAX_TERM_CHARS = 40

_cache_lock = threading.Lock()
_cache_rows: Optional[Dict[int, Tuple[List[str], str]]] = None
_cache_loaded_at = 0.0


def doc_expansion_enabled() -> bool:
    raw = (os.getenv('COFIND_DOC_EXPANSION') or '').strip().lower()
    return raw in ('1', 'true', 'yes', 'on')


def _cache_seconds() -> int:
    raw = (os.getenv('COFIND_DOC_EXPANSION_CACHE_SECONDS') or '').strip()
    try:
        return max(0, int(raw)) if raw else 300
    except ValueError:
        return 300


def review_text_hash(text: str) -> str:
    canonical = re.sub(r'\s+', ' ', str(text or '')).strip()
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


_table_ready = False


def ensure_review_expansions_table() -> bool:
    """Idempotent; skema sama dengan scripts/migrations/004_review_expansions.sql."""
    global _table_ready
    if _table_ready:
        return True
    try:
        from db_backend import get_connection

        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {TABLE} (
                    review_id BIGINT PRIMARY KEY REFERENCES reviews(id) ON DELETE CASCADE,
                    place_id TEXT NOT NULL,
                    expansion_terms TEXT NOT NULL,
                    source_text_hash TEXT NOT NULL,
                    model_id TEXT,
                    prompt_version TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{TABLE}_place_id ON {TABLE}(place_id)"
            )
            conn.commit()
        finally:
            conn.close()
        _table_ready = True
        return True
    except Exception as err:
        logger.warning(f"ensure_review_expansions_table: {str(err)[:200]}")
        return False


def upsert_review_expansions(
    rows: Iterable[Tuple[int, str, Sequence[str], str]],
    *,
    model_id: str,
) -> int:
    """
    rows: (review_id, place_id, terms, source_text_hash). Return jumlah baris ditulis.
    terms kosong tetap disimpan sebagai penanda "sudah diproses" agar tidak di-LLM ulang.
    """
    payload = [
        (int(rid), str(pid), json.dumps(list(terms or []), ensure_ascii=False), str(h),
         model_id, DOC_EXPANSION_PROMPT_VERSION)
        for rid, pid, terms, h in rows
    ]
    if not payload:
        return 0
    from db_backend import get_connection

    conn = get_connection()
    try:
        conn.cursor().executemany(
            f"""
            INSERT INTO {TABLE}
                (review_id, place_id, expansion_terms, source_text_hash, model_id,
                 prompt_version, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, NOW())
            ON CONFLICT (review_id) DO UPDATE SET
                place_id = EXCLUDED.place_id,
                expansion_terms = EXCLUDED.expansion_terms,
                source_text_hash = EXCLUDED.source_text_hash,
                model_id = EXCLUDED.model_id,
                prompt_version = EXCLUDED.prompt_version,
                updated_at = NOW()
            """,
            payload,
        )
        conn.commit()
    finally:
        conn.close()
    invalidate_cache()
    return len(payload)


def _decode_terms(raw: object) -> List[str]:
    try:
        data = json.loads(str(raw or '[]'))
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [str(t).strip() for t in data if str(t or '').strip()]


def _load_all_expansion_rows() -> Dict[int, Tuple[List[str], str]]:
    """review_id -> (terms, source_text_hash) untuk prompt_version aktif."""
    if not ensure_review_expansions_table():
        return {}
    from db_backend import get_connection

    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT review_id, expansion_terms, source_text_hash FROM {TABLE} "
            "WHERE prompt_version = ?",
            (DOC_EXPANSION_PROMPT_VERSION,),
        ).fetchall()
    finally:
        conn.close()
    return {int(r[0]): (_decode_terms(r[1]), str(r[2] or '')) for r in rows if r and r[0] is not None}


def invalidate_cache() -> None:
    global _cache_rows, _cache_loaded_at
    with _cache_lock:
        _cache_rows = None
        _cache_loaded_at = 0.0


def _cached_rows() -> Dict[int, Tuple[List[str], str]]:
    global _cache_rows, _cache_loaded_at
    with _cache_lock:
        fresh = _cache_rows is not None and (time.time() - _cache_loaded_at) < _cache_seconds()
        if fresh:
            return _cache_rows or {}
    rows = _load_all_expansion_rows()
    with _cache_lock:
        _cache_rows = rows
        _cache_loaded_at = time.time()
    return rows


def doc_expansions_for_profiles(profiles: Sequence[dict]) -> Dict[int, str]:
    """review_id -> teks expansion, hanya untuk ulasan yang hash teksnya masih cocok."""
    from bm25_utils import review_row_text

    rows = _load_all_expansion_rows() if _cache_seconds() == 0 else _cached_rows()
    if not rows:
        return {}
    out: Dict[int, str] = {}
    for profile in profiles or []:
        for review in profile.get('reviews') or []:
            if not isinstance(review, dict) or review.get('id') is None:
                continue
            try:
                rid = int(review['id'])
            except (TypeError, ValueError):
                continue
            entry = rows.get(rid)
            if not entry:
                continue
            terms, stored_hash = entry
            if terms and stored_hash == review_text_hash(review_row_text(review)):
                out[rid] = ' '.join(terms)
    return out


def build_doc_expansion_prompt(items: Sequence[Tuple[int, str]], *, max_terms: int) -> str:
    lines = []
    for rid, text in items:
        body = re.sub(r'\s+', ' ', str(text or '')).strip()[:600]
        lines.append(f'[{rid}] {body}')
    return (
        'Anda membantu mesin pencari coffee shop di Indonesia (document expansion / doc2query).\n'
        'Untuk setiap ulasan, tulis kata atau frasa pendek yang mungkin diketik pengguna saat '
        'mencari tempat seperti yang dijelaskan ulasan itu.\n\n'
        'Aturan ketat:\n'
        f'- Maksimal {max_terms} istilah per ulasan, masing-masing 1-3 kata, huruf kecil.\n'
        '- Utamakan sinonim, slang, singkatan, dan ejaan informal dari hal yang BENAR-BENAR '
        'disebut ulasan (mis. "colokan" -> "stopkontak", "charger"; "kerja" -> "wfc", "remote").\n'
        '- Jangan mengarang fasilitas/aktivitas yang tidak disebut ulasan.\n'
        '- Jangan memakai kata umum (tempat, kafe, coffee shop, enak, bagus, mantap).\n'
        '- Jika ulasan negatif soal sesuatu (mis. "wifi lemot"), jangan tulis istilah yang '
        'menyiratkan hal itu bagus.\n'
        '- Ulasan tanpa informasi berguna: terms = [].\n\n'
        'Ulasan:\n'
        + '\n'.join(lines)
        + '\n\nBalas HANYA JSON tanpa markdown: '
        '{"items": [{"id": <id ulasan>, "terms": ["..."]}]}'
    )


def parse_doc_expansion_response(raw: object, *, allowed_ids: Iterable[int]) -> Dict[int, List[str]]:
    """Validasi JSON LLM: hanya id yang diminta, term non-kosong, unik, panjang wajar."""
    allowed = {int(i) for i in allowed_ids}
    if isinstance(raw, dict):
        data = raw
    else:
        text = str(raw or '').strip()
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if not match:
            return {}
        try:
            data = json.loads(match.group(0))
        except ValueError:
            return {}
    items = data.get('items') if isinstance(data, dict) else None
    out: Dict[int, List[str]] = {}
    for item in items or []:
        if not isinstance(item, dict):
            continue
        try:
            rid = int(item.get('id'))
        except (TypeError, ValueError):
            continue
        if rid not in allowed:
            continue
        terms: List[str] = []
        for term in item.get('terms') or []:
            clean = re.sub(r'\s+', ' ', str(term or '')).strip().lower()
            if not clean or len(clean) > MAX_TERM_CHARS or clean in terms:
                continue
            terms.append(clean)
            if len(terms) >= MAX_TERMS_PER_REVIEW:
                break
        out[rid] = terms
    return out

"""
Pra-hitung vektor embedding seluruh review (batch, offline).

Dijalankan di luar jam sibuk atau setelah banyak review baru masuk, sehingga
request rekomendasi hanya membaca cache dan tidak perlu meng-encode apa pun.

Pemakaian:
    python warm_semantic_cache.py                # semua review
    python warm_semantic_cache.py --limit 500    # batasi jumlah review
    python warm_semantic_cache.py --place-id ChIJ...   # satu toko saja
    python warm_semantic_cache.py --stats        # hanya tampilkan statistik cache
"""

from __future__ import annotations

import argparse
import time

from dotenv import load_dotenv

load_dotenv()

from semantic_match import (  # noqa: E402  (butuh env termuat lebih dulu)
    cache_stats,
    embed_texts,
    flush_cache,
    gate_config,
    model_available,
    split_clauses,
)


def fetch_reviews(place_id: str | None = None, limit: int | None = None):
    """Ambil teks review dari database (urut terbaru)."""
    from db_backend import get_connection

    sql = 'SELECT place_id, review_text FROM reviews'
    params: list = []
    if place_id:
        sql += ' WHERE place_id = ?'
        params.append(place_id)
    sql += ' ORDER BY created_at DESC'
    if limit:
        sql += ' LIMIT ?'
        params.append(int(limit))

    conn = get_connection()
    try:
        rows = conn.cursor().execute(sql, tuple(params)).fetchall()
    finally:
        conn.close()

    out = []
    for row in rows or []:
        values = list(row)
        text = str(values[1] or '').strip() if len(values) > 1 else ''
        if text:
            out.append(text)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description='Warm-up cache embedding review Cofind.')
    parser.add_argument('--place-id', dest='place_id', default=None, help='batasi ke satu coffee shop')
    parser.add_argument('--limit', type=int, default=None, help='batas jumlah review')
    parser.add_argument('--batch', type=int, default=256, help='klausa per batch encode')
    parser.add_argument('--stats', action='store_true', help='hanya cetak statistik cache')
    args = parser.parse_args()

    print(f"[WARM] Konfigurasi gerbang makna: {gate_config()}")
    if args.stats:
        print(f"[WARM] Statistik cache: {cache_stats()}")
        return 0

    if not model_available():
        print('[WARM] Model embedding tidak tersedia. Jalankan: pip install sentence-transformers')
        return 1

    reviews = fetch_reviews(place_id=args.place_id, limit=args.limit)
    print(f"[WARM] Review dimuat: {len(reviews)}")
    if not reviews:
        return 0

    clauses: list[str] = []
    seen = set()
    for text in reviews:
        for clause in split_clauses(text):
            marker = clause.lower()
            if marker in seen:
                continue
            seen.add(marker)
            clauses.append(clause)
    print(f"[WARM] Klausa unik: {len(clauses)}")

    started = time.perf_counter()
    batch = max(1, int(args.batch))
    for offset in range(0, len(clauses), batch):
        chunk = clauses[offset:offset + batch]
        embed_texts(chunk)
        done = min(offset + batch, len(clauses))
        elapsed = time.perf_counter() - started
        print(f"[WARM] {done}/{len(clauses)} klausa ({elapsed:.1f}s)", flush=True)
        # Simpan berkala supaya proses yang terhenti tidak kehilangan semua progres.
        flush_cache()

    flush_cache()
    print(f"[WARM] Selesai dalam {time.perf_counter() - started:.1f}s. Cache: {cache_stats()}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

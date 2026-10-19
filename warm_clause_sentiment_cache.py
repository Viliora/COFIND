"""
Pra-hitung verdict sentimen klausa LLM (cache `clause_sentiment`).

Jalankan setelah banyak review baru atau sebelum demo/sidang agar Fase 2b
sering memakai cache (`from_cache`) alih-alih panggilan LLM live.

Pemakaian:
    python warm_clause_sentiment_cache.py
    python warm_clause_sentiment_cache.py --limit 800 --dry-run
    python warm_clause_sentiment_cache.py --stats
"""

from __future__ import annotations

import argparse
import time

from dotenv import load_dotenv

load_dotenv()

from llm_clause_sentiment import (  # noqa: E402
    cache_stats,
    classify_clauses_batch,
    clause_sentiment_enabled,
    flush_cache,
    sentiment_config,
)
from llm_backend import llm_is_available
from semantic_match import split_clauses


def fetch_review_texts(limit: int | None = None):
    from db_backend import get_connection

    sql = 'SELECT review_text FROM reviews ORDER BY created_at DESC'
    params: tuple = ()
    if limit:
        sql += ' LIMIT ?'
        params = (int(limit),)
    conn = get_connection()
    try:
        rows = conn.cursor().execute(sql, params).fetchall()
    finally:
        conn.close()
    out = []
    for row in rows or []:
        text = str(row[0] or '').strip()
        if text:
            out.append(text)
    return out


def preference_lines_from_app():
    from app import PILL_LABELS, PILL_MAPPING

    lines = {'preferensi umum'}
    for key in PILL_MAPPING or {}:
        label = str(PILL_LABELS.get(key) or key).strip()
        if label:
            lines.add(label)
    return sorted(lines)


def collect_unique_clauses(reviews, *, max_clauses: int):
    seen = set()
    clauses = []
    for review in reviews:
        for clause in split_clauses(review):
            marker = clause.strip().lower()
            if len(marker) < 3 or marker in seen:
                continue
            seen.add(marker)
            clauses.append(clause.strip())
            if max_clauses and len(clauses) >= max_clauses:
                return clauses
    return clauses


def main() -> int:
    parser = argparse.ArgumentParser(description='Warm cache sentimen klausa Cofind.')
    parser.add_argument('--limit', type=int, default=None, help='batas jumlah review yang discan')
    parser.add_argument('--max-clauses', type=int, default=4000, help='batas klausa unik total')
    parser.add_argument('--dry-run', action='store_true', help='hanya hitung klausa, tanpa LLM')
    parser.add_argument('--stats', action='store_true', help='cetak statistik cache lalu keluar')
    args = parser.parse_args()

    print(f'[WARM-CLAUSE] Konfigurasi: {sentiment_config()}')
    if args.stats:
        print(f'[WARM-CLAUSE] Statistik cache: {cache_stats()}')
        return 0

    if not clause_sentiment_enabled():
        print('[WARM-CLAUSE] COFIND_LLM_CLAUSE_SENTIMENT=false — tidak ada yang di-warm.')
        return 0
    if not llm_is_available() and not args.dry_run:
        print('[WARM-CLAUSE] LLM tidak tersedia (HF_API_TOKEN?).')
        return 1

    reviews = fetch_review_texts(limit=args.limit)
    clauses = collect_unique_clauses(reviews, max_clauses=args.max_clauses)
    pref_lines = preference_lines_from_app()
    print(f'[WARM-CLAUSE] Review={len(reviews)} klausa_unik={len(clauses)} preferensi={len(pref_lines)}')

    if args.dry_run:
        return 0

    from app import _llm_chat_for_pipeline, _parse_llm_json_with_repair

    total_llm = 0
    t0 = time.perf_counter()
    for pref in pref_lines:
        verdicts, telemetry = classify_clauses_batch(
            clauses,
            preference_line=pref,
            chat_fn=_llm_chat_for_pipeline,
            parse_json_fn=_parse_llm_json_with_repair,
        )
        total_llm += int(telemetry.get('llm_calls') or 0)
        print(
            f'[WARM-CLAUSE] {pref[:48]}… '
            f'verdicts={len(verdicts)} llm_calls={telemetry.get("llm_calls")} '
            f'cache={telemetry.get("from_cache")}'
        )
    flush_cache()
    elapsed = round(time.perf_counter() - t0, 1)
    print(f'[WARM-CLAUSE] Selesai dalam {elapsed}s, total_llm_calls≈{total_llm}')
    print(f'[WARM-CLAUSE] Statistik cache: {cache_stats()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

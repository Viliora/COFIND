# pgvector review embeddings

## Overview

Dense vectors for hybrid retrieval are stored in **`review_embeddings`** (Supabase pgvector, 384 dims, cosine).

- **Write:** `review_utils` CRUD calls `schedule_review_embedding_after_write` when `COFIND_EMBEDDING_STORE=pgvector` (sync or Celery if `COFIND_EMBEDDING_ASYNC=true`).
- **Read (per-id):** `semantic_match.score_reviews_by_id` loads vectors from Postgres; encodes the query only (+ backfill missing rows).
- **Read (Fase 2 ANN):** `hybrid_retrieval.score_shops_dense` uses `ann_search_reviews` when `COFIND_DENSE_USE_ANN` is on (default on for pgvector): top-K reviews scoped to `place_id` from Fase 1, then max-pool per shop.
- **Rollback:** set `COFIND_EMBEDDING_STORE=cache` (legacy Redis/file via `vector_cache.py`); ANN auto-off in cache mode.

See also [cache-and-persistence.md](cache-and-persistence.md).

## Setup

1. Apply migrations: `python scripts/run_pgvector_migration.py` (001 + optional 002 `reviews.place_id` index).
2. Backfill: `set COFIND_EMBEDDING_STORE=pgvector` then `python scripts/backfill_review_embeddings.py`
3. Enable in production (Railway): `COFIND_EMBEDDING_STORE=pgvector`, `COFIND_DENSE_USE_ANN=true` (default when pgvector).
4. Verify: `python scripts/verify_embedding_parity.py`, `python scripts/smoke_ann_search.py`
5. Admin dashboard: coverage % on `/api/admin/dashboard` → `charts.embedding_stats`.

## ANN (scoped)

- SQL: join `review_embeddings` ⋈ `reviews`, filter `place_id IN (...)`, `ORDER BY embedding <=> query`, `LIMIT COFIND_ANN_TOP_K` (default 300).
- Index: HNSW on `review_embeddings.embedding`; optional `idx_reviews_place_id` on `reviews`.
- Fallback: if ANN error or zero rows → legacy max-pool (`COFIND_DENSE_MAX_REVIEWS` per shop).
- Telemetry: `dense.pool` = `ann` | `max` in recommendation logs and `recommendation_pipeline_runs.snapshot_json`.

## Coverage SQL

```sql
SELECT COUNT(*) AS embedded FROM review_embeddings;
SELECT COUNT(*) AS reviews FROM reviews WHERE review_text IS NOT NULL;
```

Compare with Admin **Coverage embedding** or `GET /api/admin/embedding-stats`.

## Model change

If `COFIND_EMBEDDING_MODEL` changes, re-run backfill (`model_id` + `source_text_hash` invalidate stale rows).

## Production (Railway)

1. Set `COFIND_EMBEDDING_STORE=pgvector` on web (+ worker if async embed).
2. Redeploy (sentence-transformers on image).
3. Backfill: `python scripts/backfill_review_embeddings.py` with production `DATABASE_URL`.
4. Optional: `COFIND_EMBEDDING_ASYNC=true` + Celery worker consuming `cofind.embed_review_task`.
5. Monitor: hybrid ms, `ann_usage_rate`, embedding coverage in Admin.

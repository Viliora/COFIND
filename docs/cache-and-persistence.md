# Cache vs database persistence

## Decision table

| Data | Storage | Notes |
|------|---------|--------|
| Review dense vectors | Postgres `review_embeddings` (pgvector) | One row per review; CRUD sync or Celery |
| Shop dense score (Fase 2) | Computed at request time | **ANN** top-K scoped to Fase 1 `place_id`, max-pool per shop; not stored |
| Query / clause embeddings | Redis → file (`vector_cache`, namespace `semantic_embeddings`) | Ephemeral; TTL |
| Clause sentiment LLM verdicts | Redis → file (`clause_sentiment`) | Dedup expensive LLM calls |
| LLM rerank | Separate cache (expiry in admin settings) | Not review entities |
| Recommendation summary (`explanation`) | No cache | Regenerated per pill combo |
| `facilities.json` (frontend) | Static file | Not DB unless product needs admin edit |

## Redis role

`REDIS_URL` (Upstash): shared cache for embeddings/verdicts **and** Celery broker. It does **not** replace pgvector for review vectors.

Health: `GET /api/admin/cache-health` (admin).

## Rollback

- `COFIND_EMBEDDING_STORE=cache` → dense uses in-memory/Redis encode path; ANN disabled.
- Existing `review_embeddings` rows remain in DB for re-enable.

## Related env

- `COFIND_EMBEDDING_STORE`, `COFIND_DENSE_USE_ANN`, `COFIND_ANN_TOP_K`
- `COFIND_EMBEDDING_ASYNC`, `COFIND_VECTOR_CACHE_*`

Details: [pgvector-embeddings.md](pgvector-embeddings.md).

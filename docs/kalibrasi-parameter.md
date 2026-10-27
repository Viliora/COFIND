# Kalibrasi Parameter Ranking — Cofind

**Legenda deployment:** kecuali disebutkan, nilai deployment = **Tidak Diketahui**. Contoh di repo: **`.env.example`** (bukan bukti production).

---

## A. Parameter inti ranking (Fase 2 RRF)

| Nama Parameter | Lokasi (file:baris) | Nilai Default Kode | Env Var | Efek ke Ranking | Rentang Aman Disarankan | Cara Validasi |
|----------------|---------------------|--------------------|---------|-----------------|-------------------------|---------------|
| RRF constant `k` | `hybrid_retrieval.py:1008-1032` | 60 | `COFIND_RRF_K` | Semakin besar `k`, semakin datar kontribusi rank | 40–80 (literatur umum); uji 30–120 | Log `telemetry.rrf_k`; bandingkan MRR@7 pada query golden |
| RRF pool size | `hybrid_retrieval.py:1012-1045` | 50 | `COFIND_RRF_POOL_SIZE` | Lebar union kandidat per saluran | 30–100 | `rrf_candidates` vs recall kandidat relevan |
| Blend RRF norm : quality | `hybrid_retrieval.py:1186` | **0.9 : 0.1** (hardcoded) | — | Quality menggeser urutan within RRF pool | Quality 0.05–0.15 jika tetap secondary | Ablation: set quality=0 vs nyata pada profil sama |
| Normalisasi RRF | `hybrid_retrieval.py:1163-1171` | bagi `max_rrf` | — | Skala RRF ke [0,1] per request | — | Inspect `score_detail.rrf_norm` vs `rrf_score` |
| Top-K retrieval | `hybrid_retrieval.py:206` | 7 | `COFIND_RETRIEVAL_TOP_K` | Ukuran pool ke Fase 3 | 5–10 | Latency vs coverage LLM rerank |
| BM25 weight (legacy) | `hybrid_retrieval.py:194` | 0.45 | `COFIND_HYBRID_BM25_WEIGHT` | **[Tidak memengaruhi RRF hidup]** | — | Grep pemanggil `_blend_weights` |
| Dense weight (legacy) | `hybrid_retrieval.py:198` | 0.45 | `COFIND_HYBRID_DENSE_WEIGHT` | **[Tidak memengaruhi RRF hidup]** | — | Idem |
| Quality weight (legacy) | `hybrid_retrieval.py:202` | 0.10 | `COFIND_HYBRID_QUALITY_WEIGHT` | **[Tidak memengaruhi RRF hidup]** | — | Idem; blend aktual 0.1 di `1186` |
| Quality score profil | `app.py:2332-2342` | 0.5 experience + 0.5 rating | — | Input `quality_s` ke blend 0.1 | — | Sample profil tanpa `community_signals` |
| Dense max reviews (fallback) | `hybrid_retrieval.py:210` | 20 | `COFIND_DENSE_MAX_REVIEWS` | Max-pool cosine per toko | 15–40 | Bandingkan ANN vs max-pool telemetry |
| ANN top-K rows | `hybrid_retrieval.py:244` | 300 | `COFIND_ANN_TOP_K` | Recall dense global | 200–500 | `dense.ann_reviews`, fallback rate `851-855` |
| Dense use ANN | `hybrid_retrieval.py:232-240` | on jika pgvector store | `COFIND_DENSE_USE_ANN` | Jalur dense vs fallback | — | `dense.pool` ann vs maxpool |
| Activity dense min | `hybrid_retrieval.py:221-222` | 0.55 | `COFIND_ACTIVITY_DENSE_MIN` | **Hanya telemetry saat ini** | 0.45–0.65 jika di-wire | Setelah implementasi: hitung `activity_pass_dense_only` |
| Lex/dense review rank (non-RRF) | `hybrid_retrieval.py:57-58` | 0.3 / 0.7 | — | Urutan kutipan/evidence | — | Uji kutipan modal |
| Rank reviews weights (pill) | `hybrid_retrieval.py:641-648` | 0.45/0.30/0.15/0.10 + bonus | — | Evidence ke LLM, indirect ranking Fase 3 | — | Quote relevance manual |

**`.env.example`:** `COFIND_HYBRID_*`, `COFIND_RETRIEVAL_TOP_K`, `COFIND_ACTIVITY_DENSE_MIN` (`.env.example:33-50`); **tanpa** `COFIND_RRF_K` / `COFIND_RRF_POOL_SIZE`.

---

## B. Metadata prior

| Nama Parameter | Lokasi | Default | Env | Efek | Rentang | Validasi |
|----------------|--------|---------|-----|------|---------|----------|
| Gate on/off | `metadata_prior.py:53-54` | true | `COFIND_METADATA_GATE` | Nonaktif = skip fusi | — | `metadata_gate.enabled` per kandidat |
| Prior weight | `metadata_prior.py:57-58` | 0.08 (max env 0.2) | `COFIND_METADATA_PRIOR_WEIGHT` | Boost additive × prior × signal | 0.04–0.12 | A/B attribute-only queries |
| Penalty weight | `metadata_prior.py:61-62` | 0.18 (max 0.5) | `COFIND_METADATA_PENALTY_WEIGHT` | Potong skor kontradiksi | 0.10–0.25 | Kasus parkir/wifi kontradiksi |
| Contradiction scale | `metadata_prior.py:260-267` | 0.6 / 1.0 | — | Keras kontradiksi | — | Unit quotes count |
| Review signal untuk prior | `metadata_prior.py:302-304` | `rrf_norm` | — | Prior nol tanpa sinyal ulasan | — | `metadata_prior_boost` vs `rrf_norm` |

**`.env.example`:** `38-40`.

---

## C. Fase 3 LLM rerank

| Nama Parameter | Lokasi | Default | Env | Efek | Rentang | Validasi |
|----------------|--------|---------|-----|------|---------|----------|
| Rerank enabled | `llm_recommender.py:78` | true | `COFIND_LLM_RERANK` | LLM vs urutan hybrid | — | `rerank_backend` |
| Rerank weight | `llm_recommender.py:94`, `1110` | 0.6 | `COFIND_LLM_RERANK_WEIGHT` | Campuran fit vs hybrid | 0.4–0.7 | Swap 0.5/0.6 pada set eval |
| Rerank candidates | `llm_recommender.py:90` | 7 | `COFIND_LLM_RERANK_CANDIDATES` | Berapa toko dinilai LLM | 5–10 | `scored_by_llm` |
| Min fit (corpus floor) | `hybrid_retrieval.py:247-248`, `llm_recommender.py:1034-1040` | 5.0 | `COFIND_LLM_MIN_FIT` | Floor fit jika aktivitas supported | 4.0–6.0 | Log `fit_score` vs selected |
| Grounding | `llm_recommender.py:86` | true | `COFIND_LLM_GROUNDING_CHECK` | Kutipan tidak grounding → penalti | — | `ungrounded_quotes` |
| Personalization | `llm_recommender.py:82` | true | `COFIND_LLM_PERSONALIZATION` | Prompt rerank | — | Cache key per user |
| Rerank cache | `app.py:6299` | true (via env) | `COFIND_LLM_RERANK_CACHE` | Stabilitas/latency | — | Invalidate saat review baru |

**`.env.example`:** `52-68`.

---

## D. Semantic / embedding (dense & side paths)

| Nama Parameter | Lokasi | Default | Env | Efek ke Ranking | Rentang | Validasi |
|----------------|--------|---------|-----|-----------------|---------|----------|
| Semantic gate | `semantic_match.py:101` | true | `COFIND_SEMANTIC_GATE` | Mati = dense skip | — | `dense.skipped` |
| Threshold | `semantic_match.py:114` | 0.55 | `COFIND_SEMANTIC_THRESHOLD` | Utilitas lama, bukan gerbang RRF (`.env.example:87-88`) | 0.45–0.65 | Smoke semantic_match |
| Score cap | `semantic_match.py:126` | 0.6 | `COFIND_SEMANTIC_SCORE_CAP` | Cap kontribusi semantik legacy | — | — |
| Encode budget | `semantic_match.py:131` | 1500 | `COFIND_SEMANTIC_ENCODE_BUDGET` | Batas encode/request | 1000–3000 | Budget telemetry |
| Embedding model | `semantic_match.py:105` | MiniLM-L12-v2 | `COFIND_EMBEDDING_MODEL` | Geometri cosine | — | Benchmark query set |
| PG vector dim | `review_embedding_store.py:21` | 384 | `COFIND_PGVECTOR_DIM` | ANN compatibility | 384 (model) | Dim mismatch check |
| Embedding store | `review_embedding_store.py:25` | cache | `COFIND_EMBEDDING_STORE` | ANN vs file-only | pgvector prod | `dense.store` |

**`.env.example`:** `85-96`, `115-119`.

---

## E. Fase 1, free text, sentimen, legacy coverage

| Nama Parameter | Lokasi | Default | Env | Efek | Rentang | Validasi |
|----------------|--------|---------|-----|------|---------|----------|
| Min reviews | `app.py:1123`, `1231` | 1 | — | Hard filter Fase 1 | 1–3 | Count shops dropped |
| Free text intent | `free_text_intent.py:45-46` | true | `COFIND_FREE_TEXT_INTENT` | Keywords untuk RRF | — | Intent telemetry |
| Max free text chars | `free_text_intent.py:33` | 50 | — | Panjang query | — | API validation [TIDAK TERVERIFIKASI di app.py baris spesifik] |
| ABSA kutipan (Fase 2) | `absa_sentiment.py` | true | `COFIND_ABSA_ENABLED` | Verdict caveat/support | — | `clause_sentiment_ms` |
| CE rerank (Fase 3) | `cross_encoder_rerank.py` | true | `COFIND_CE_RERANK` + `COFIND_CROSS_ENCODER` | Urutan final vs hybrid | 0.4–0.7 | `rerank_backend` |
| Batch/max/pool/concurrency | `llm_clause_sentiment.py:90-102` | 16/96/6/3 | `COFIND_CLAUSE_*` | Latency & coverage verdict | — | Telemetry quotes |
| Dedup min cosine | `llm_clause_sentiment.py:79` | 0.92 | `COFIND_CLAUSE_SENTIMENT_DEDUP_MIN` | Dedup klausa | 0.88–0.95 | — |
| Coverage bonus (legacy) | `app.py:2812` | 0.25 | `COFIND_COVERAGE_BONUS` | Scorer lama, bukan RRF (`.env.example:107-110`) | — | Grep pemanggil di jalur recommend |
| Activity coverage share | `app.py:2846` | 0.6 | `COFIND_ACTIVITY_COVERAGE_SHARE` | Legacy | — | Idem |
| Coverage semantic min | `app.py:2829` | 0.65 | `COFIND_COVERAGE_SEMANTIC_MIN` | Legacy | — | Idem |

---

## F. Prompt / scan (indirect)

| Parameter | Lokasi | Default | Env | Efek |
|-----------|--------|---------|-----|------|
| Prompt review scan | `hybrid_retrieval.py:214` | 60 | `COFIND_PROMPT_REVIEW_SCAN` | Ulasan di-scan untuk kutipan |
| Prompt review limit | `hybrid_retrieval.py:218` | 8 | `COFIND_PROMPT_REVIEW_LIMIT` | Kutipan disimpan |

---

## G. Ringkasan env `COFIND_*` non-ranking (operasional / summary)

Tidak mengubah urutan hybrid langsung: `COFIND_DEV_LLM_STRICT`, `COFIND_SUMMARY_*`, `COFIND_MODAL_QUOTE_LLM`, `COFIND_RECOMMEND_VERBOSE`, `COFIND_VECTOR_CACHE*`, `COFIND_LOG_LEVEL*`, `COFIND_JOB_*`, `COFIND_DB_BACKEND`, `COFIND_LLM_PROBE_*`, `COFIND_SEMANTIC_PRELOAD` — definisi di `app.py`, `vector_cache.py`, `celery_app.py`, `.env.example`.

---

## H. Triase klausa, FTS, dan migrasi embedding

| Parameter | Default | Efek |
|-----------|---------|------|
| `COFIND_CLAUSE_TRIAGE` | true | Bi-encoder triase sebelum LLM clause sentiment |
| `COFIND_CROSS_ENCODER` | false | Cross-encoder pada pita ambigu (`cross_encoder.py`) |
| `COFIND_CROSS_ENCODER_MODEL` | jina-reranker-v2-base-multilingual | Model pasangan query–klausa; alternatif `BAAI/bge-reranker-v2-m3`. Jina butuh `einops` + shim transformers 5.x di `cross_encoder.py` |
| `COFIND_TAU_LOW` / `COFIND_TAU_HIGH` | 0.35 / 0.72 | Ambang accept/reject vs needs_llm (`semantic_triage.py`). Skor Jina cross-encoder bisa lebih rendah dari BGE pada teks pendek — pantau `triaged_reject` / `triaged_llm` setelah ganti model; sesuaikan jika perlu |
| `COFIND_BM25_BACKEND` | memory | `postgres` memakai `coffee_shops.review_tsv` |
| `COFIND_EMBEDDING_MODEL` + `COFIND_PGVECTOR_DIM` | MiniLM / 384 | Set `BAAI/bge-m3` + 1024 lalu backfill + `tests/smoke/smoke_threshold.py` |

Baseline golden: `python scripts/eval/run_golden_baseline.py` → `data/eval/baseline.json`.

---

## Asumsi & item tidak terverifikasi

1. **Nilai env di production/staging** — tidak ada bukti di repo selain `.env.example`.
2. **`COFIND_ACTIVITY_DENSE_MIN`** — dokumentasi `.env.example:47-50` vs kode: hanya `activity_dense_min()` di telemetry (`hybrid_retrieval.py:1296`); gerbang `shop_has_activity_signal` (`900-927`) **tanpa** ambang cosine.
3. **`activity_pass_dense_only`** — diinisialisasi 0 (`hybrid_retrieval.py:1294`); **tidak ditemukan** increment di codebase.
4. **`COFIND_LLM_MIN_FIT`** — tidak memfilter `_select_top_shops`; hanya `corpus_floor` di `llm_recommender.py:1034-1041`.
5. **Validasi panjang free text 50 char di `app.py`** — disebut di `free_text_intent.py:4-5`; baris potongan exact di `app.py` belum disitasi di dokumen ini.
6. **Pemanggilan `_coverage_*` / legacy scorer** pada jalur `_recommendation_pipeline_events` — per `.env.example:107-110` legacy; perlu audit grep terpisah jika harus klaim “tidak dipakai”.
7. **Audit DB gaming / typo “hidden game”** — temuan percakapan; perbaikan di `slang_normalize`/`hybrid_retrieval` **tidak** diverifikasi ulang baris-per-baris di dokumen ini.

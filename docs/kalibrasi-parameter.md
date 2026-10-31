# Kalibrasi Parameter Ranking — Cofind

**Legenda:** nilai **default kode** vs **nilai skripsi (dev)** setelah tuning pada [`data/eval/relevance_judgments.json`](../data/eval/relevance_judgments.json). Deployment production tidak diverifikasi dari repo.

**Dihapus dari jalur ranking (legacy):** `COFIND_HYBRID_*`, `COFIND_METADATA_*`, `COFIND_LLM_RERANK*`, LLM rerank, fusi metadata di hybrid.

---

## A. Parameter inti ranking (Fase 2 RRF)

| Nama Parameter | Lokasi | Default kode | Env Var | Efek | Rentang / literatur | Validasi |
|----------------|--------|--------------|---------|------|---------------------|----------|
| RRF constant `k` | `hybrid_retrieval.py` | 60 | `COFIND_RRF_K` | Kontribusi rank tail | 40–80 (Cormack et al. 2009) | `scripts/eval/relevance_metrics.py` |
| RRF pool size | `hybrid_retrieval.py` | 50 | `COFIND_RRF_POOL_SIZE` | Lebar union kandidat | 30–100 | Snapshot golden |
| Blend RRF norm : quality | `hybrid_retrieval.py` | **0.9 : 0.1** | — | Geser urutan dalam pool | 0.05–0.15 quality | Ablation manual |
| Top-K retrieval | `hybrid_retrieval.py` | 7 | `COFIND_RETRIEVAL_TOP_K` | Pool ke Fase 3 | 5–10 | Latency vs recall |
| Activity dense min | `hybrid_retrieval.py` | 0.55 | `COFIND_ACTIVITY_DENSE_MIN` | Gate/telemetry aktivitas | 0.45–0.65 | Grid `threshold_tuning.py` |
| Dense max reviews | `hybrid_retrieval.py` | 20 | `COFIND_DENSE_MAX_REVIEWS` | Max-pool cosine | 15–40 | Telemetry dense |
| ANN top-K | `hybrid_retrieval.py` | 300 | `COFIND_ANN_TOP_K` | Recall dense | 200–500 | `dense.ann_reviews` |

**Sumber nilai skripsi (dev):** isi kolom setelah menjalankan `python scripts/eval/threshold_tuning.py --judgments data/eval/relevance_judgments.json`.

---

## B. Fase 3 — Cross-encoder rerank

| Nama Parameter | Lokasi | Default | Env | Efek | Rentang | Validasi |
|----------------|--------|---------|-----|------|---------|----------|
| CE enabled | `cross_encoder_rerank.py` | true | `COFIND_CE_RERANK`, `COFIND_CROSS_ENCODER` | Urutan vs hybrid | on/off | `rerank_backend=cross_encoder` |
| Rerank weight | `cross_encoder_rerank.py` / `rerank_blend.py` | 0.6 | `COFIND_CE_RERANK_WEIGHT` | Blend fit CE vs hybrid | 0.4–0.7 | Grid tuning |
| Rerank candidates | `cross_encoder_rerank.py` | 7 | `COFIND_CE_RERANK_CANDIDATES` | Toko dinilai CE | 5–10 | Telemetry |
| Rerank cache | `app.py` | true | `COFIND_CE_RERANK_CACHE` | Latency | — | Invalidate saat review baru |
| Min fit floor | `hybrid_retrieval.py` | 5.0 | `COFIND_LLM_MIN_FIT` | Floor skor corpus | 4.0–6.0 | Log fit |
| Grounding | `llm_recommender.py` | true | `COFIND_LLM_GROUNDING_CHECK` | Kutipan harus di review | — | Ungrounded count |

---

## C. Semantic / embedding (dense)

| Nama Parameter | Lokasi | Default | Env | Validasi |
|----------------|--------|---------|-----|----------|
| Semantic gate | `semantic_match.py` | true | `COFIND_SEMANTIC_GATE` | `dense.skipped` |
| Embedding model | `semantic_match.py` | e5-small | `COFIND_EMBEDDING_MODEL` | Cosine geometry |
| PG vector dim | `review_embedding_store.py` | 384 | `COFIND_PGVECTOR_DIM` | Dim match model |
| BM25 backend | `postgres_fts.py` | memory | `COFIND_BM25_BACKEND` | FTS postgres vs memory |

---

## D. ABSA & triase (Fase 2b)

| Nama Parameter | Lokasi | Default | Env | Validasi |
|----------------|--------|---------|-----|----------|
| ABSA on | `absa_sentiment.py` | true | `COFIND_ABSA_ENABLED` | `from_absa` telemetry |
| Model | `absa_sentiment.py` | indobert-absa | `COFIND_ABSA_MODEL` | Smoke clause |
| Tau low / high | `semantic_triage.py` | 0.35 / 0.72 | `COFIND_TAU_LOW`, `COFIND_TAU_HIGH` | Grid tuning |
| Clause max / pool | `llm_clause_sentiment.py` | 96 / 6 | `COFIND_CLAUSE_SENTIMENT_*` | Latency |

Caveat kutipan: frasa unsuitability + verdict ABSA (bukan heuristik `review_weakness` di ranking pill).

---

## E. Free text & operasional

| Parameter | Default | Env | Catatan |
|-----------|---------|-----|---------|
| Free text intent | true | `COFIND_FREE_TEXT_INTENT` | Keywords untuk RRF |
| Legacy coverage env | — | `COFIND_COVERAGE_*` | **Tidak dibaca** jalur RAG; tetap di `.env.example` sebagai dokumentasi |

Summary LLM, cache vektor, logging: lihat `.env.example` § operasional.

---

## F. Metrik evaluasi

```bash
python scripts/eval/relevance_metrics.py --judgments data/eval/relevance_judgments.json --run-retrieval
python scripts/eval/threshold_tuning.py --judgments data/eval/relevance_judgments.json
python scripts/eval/run_golden_baseline.py
python scripts/eval/golden_retrieval_snapshot.py --out data/eval/retrieval_snapshot.json
```

Baseline struktural: [`data/eval/baseline.json`](../data/eval/baseline.json) (tanpa expect metadata gate).

---

## Metadata prior (offline / admin saja)

Modul [`metadata_prior.py`](../metadata_prior.py) dipakai badge fasilitas admin (`facility_badge_checks.py`), **bukan** hybrid retrieval atau pipeline rekomendasi.

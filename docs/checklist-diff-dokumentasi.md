# Checklist diff: dokumentasi vs kode (Cofind)

Daftar periksa untuk menyelaraskan README, `docs/`, materi sidang, dan `.env.example` dengan implementasi **per Maret 2026** (sumber kebenaran: `recommendation/pipeline.py`, `api/recommendation_routes.py`, `hybrid_retrieval.py`, `.env.example`).

**Cara pakai:** centang kolom **Selesai** setelah teks/diagram di dokumen sumber sudah diperbaiki. Prioritas **P1** = salah arah arsitektur / sidang; **P2** = membingungkan tapi sebagian benar; **P3** = kosmetik / sitasi usang.

---

## Ringkasan kebenaran kode (referensi cepat)

| Topik | Keadaan kode sekarang |
|--------|------------------------|
| Orkestrasi pipeline | `recommendation/pipeline.py` → `recommendation_pipeline_events` |
| HTTP API | `api/recommendation_routes.py` (JSON + SSE stream + feedback) |
| Parse body | `recommendation/request_prefs.py` → `read_recommendation_preferences` (alias `_read_…` di `app.py` untuk compat) |
| Fase 1 | Min **1 ulasan pipeline** (Cofind **+** Google Places), `get_reviews_for_recommendation_batch` |
| Fase 2 | BM25 + dense/ANN → **RRF**; pill: activity gate + **metadata prior** (mengubah skor) |
| Fase 3 (produksi default) | **`ce_rerank_candidates`** (Jina CE lokal) jika `COFIND_CE_RERANK=true` |
| LLM rerank | `llm_rerank_candidates` **ada** di `llm_recommender.py` tetapi **tidak dipanggil** dari `recommendation/pipeline.py` |
| Output ke user | Pool retrieval ~**7** (`COFIND_RETRIEVAL_TOP_K`); dikirim **≤3** (`MAX_REC=3`) |
| LLM di pipeline | Intent (free text), ABSA/triase klausa (campuran), **Step 5 summary** |
| Fasilitas runtime | **`coffee_shops.facilities` (JSONB)** via `facilities_store.py`; `data/facilities.json` hanya impor opsional sync |
| Env default deploy | `.env.example`: `COFIND_LLM_RERANK=false`, `COFIND_CE_RERANK=true` |

---

## README.md

| # | Prioritas | Lokasi / klaim dokumen | Kode / fakta sekarang | Tindakan disarankan | Selesai |
|---|-----------|-------------------------|------------------------|---------------------|---------|
| R1 | P1 | Paragraf pembuka: “rerank **LLM**” | Fase 3 default = **cross-encoder**; LLM rerank off di `.env.example` | Tulis: CE rerank + LLM untuk intent/summary; sebut LLM rerank sebagai opsional legacy | [ ] |
| R2 | P1 | Fitur: metadata “**bukan bobot skor ranking**” | `metadata_prior.fuse_metadata_score` mengubah skor Fase 2 (pill) | Perjelas: prior/penalti lemah di ranking; di modal tetap bukti ulasan utama | [ ] |
| R3 | P2 | Struktur repo: pipeline di `app.py` | Inti di `recommendation/` + blueprint `api/recommendation_routes.py` | Tambah baris `recommendation/`, `api/recommendation_routes.py` | [ ] |
| R4 | P2 | Stack: “LLM … untuk intent, **rerank**, ringkasan” | Rerank produksi = CE; LLM rerank tidak wired di pipeline | Pisah bullet: CE rerank vs LLM (intent, summary, opsional rerank) | [ ] |
| R5 | P3 | Tabel dokumen | — | Tambah link ke dokumen ini (`checklist-diff-dokumentasi.md`) | [ ] |

---

## docs/recommendation-pipeline.md

| # | Prioritas | Lokasi / klaim dokumen | Kode / fakta sekarang | Tindakan disarankan | Selesai |
|---|-----------|-------------------------|------------------------|---------------------|---------|
| P1 | P1 | Modul: orkestrasi `app.py` → `_recommendation_pipeline_events` | `recommendation/pipeline.py`; routes di `api/recommendation_routes.py` | Ganti tabel modul + diagram §2 | [ ] |
| P2 | P1 | Modul rerank: hanya `llm_recommender.py` | Fase 3 aktif: `cross_encoder_rerank.py` (+ helper blend dari `llm_recommender`) | Tambah baris CE; LLM rerank = opsional / tidak dipakai pipeline | [ ] |
| P3 | P1 | Diagram Fase 1: “review **Cofind**”, toko tanpa review Cofind | Corpus **unified** Cofind + Google; filter `review_count >= 1` pipeline | Ganti label diagram §3 F1 | [ ] |
| P4 | P1 | Subgraph F3: “**LLM rerank**”, `llm_rerank_candidates` | Hanya `ce_rerank_candidates` di pipeline | Redraw F3 sebagai CE rerank; catatan LLM rerank legacy | [ ] |
| P5 | P2 | Sequence: participant `app.py`, Fase 3 LLM | Stream/route via blueprint; Fase 3 CE | Update sequence §5 | [ ] |
| P6 | P2 | Backend `_read_recommendation_preferences` di `app.py` | Definisi di `recommendation/request_prefs.py` | Sitasi file yang benar | [ ] |
| P7 | P3 | Tes: `tests/test_llm_recommender.py` | Masih valid untuk modul LLM; bukan bukti Fase 3 produksi | Tambah catatan: CE → `tests/test_cross_encoder_rerank.py` | [ ] |

---

## docs/arsitektur-rekomendasi.md

| # | Prioritas | Lokasi / klaim dokumen | Kode / fakta sekarang | Tindakan disarankan | Selesai |
|---|-----------|-------------------------|------------------------|---------------------|---------|
| A1 | P2 | Sitasi `app.py:6032–6074`, `5469–5482`, dll. | `app.py` ~686 baris; endpoint di `api/recommendation_routes.py` | Ganti sitasi ke `recommendation_routes.py` + `pipeline.py` (tanpa nomor baris stale) | [ ] |
| A2 | P2 | Tabel tahap: Step 5 / respons → `app.py:5866+` | Logika di `recommendation/pipeline.py` + helpers | Perbarui kolom “Bukti” | [ ] |
| A3 | P3 | Diagram Mermaid Fase 3 CE | Sudah selaras | Pertahankan; jadikan referensi utama sidang | [ ] |
| A4 | P2 | Bagian rerank: rumus `COFIND_LLM_RERANK_WEIGHT` | Berlaku jika LLM rerank dipanggil; produksi pakai `COFIND_CE_RERANK_WEIGHT` | Tambah subbagian “Fase 3 produksi (CE)” vs “LLM rerank (opsional, tidak wired)” | [ ] |

---

## docs/kalibrasi-parameter.md

| # | Prioritas | Lokasi / klaim dokumen | Kode / fakta sekarang | Tindakan disarankan | Selesai |
|---|-----------|-------------------------|------------------------|---------------------|---------|
| K1 | P1 | §C judul “Fase 3 **LLM rerank**” sebagai bagian utama | Pipeline memanggil CE, bukan `llm_rerank_candidates` | Promosikan CE ke §C; pindahkan LLM rerank ke “Legacy / opsional” | [ ] |
| K2 | P2 | Default `COFIND_LLM_RERANK` = true (kode `rerank_enabled`) | `.env.example` = **false**; tanpa env, kode default true tapi pipeline tidak memanggil | Jelaskan: default kode vs default repo vs jalur aktif | [ ] |
| K3 | P2 | `COFIND_CROSS_ENCODER` false di tabel E | CE rerank butuh `COFIND_CE_RERANK` + `cross_encoder_enabled()` (`COFIND_CROSS_ENCODER` di `cross_encoder.py`) | Selaraskan dengan `.env.example` (`COFIND_CROSS_ENCODER=true`) | [ ] |
| K4 | P3 | Legacy hybrid weights | Sudah ditandai tidak dipakai RRF | OK; referensikan dari README | [ ] |

---

## .env.example

| # | Prioritas | Lokasi / klaim dokumen | Kode / fakta sekarang | Tindakan disarankan | Selesai |
|---|-----------|-------------------------|------------------------|---------------------|---------|
| E1 | P2 | Komentar baris ~37: “Fase 3 … **LLM rerank**” | Fase 3 default = CE (baris 65–70 sudah benar) | Ubah komentar blok pipeline: “CE rerank (default); LLM rerank opsional (tidak dipanggil pipeline saat ini)” | [ ] |
| E2 | P3 | `COFIND_ACTIVITY_DENSE_MIN` vs gerbang | Doc arsitektur: telemetry dulu | Tambah satu baris “belum wired ke gerbang” atau implementasi (pilih salah satu) | [ ] |

---

## docs/cache-and-persistence.md

| # | Prioritas | Lokasi / klaim dokumen | Kode / fakta sekarang | Tindakan disarankan | Selesai |
|---|-----------|-------------------------|------------------------|---------------------|---------|
| C1 | P2 | `facilities.json` (frontend) static | Runtime baca DB; file opsional di `data/` untuk sync | Ganti baris: JSONB `coffee_shops.facilities`; file impor opsional | [ ] |
| C2 | P2 | Cache “LLM rerank” | Pipeline CE masih pakai `_get_cached_rerank_fits` / store rerank (shared keying) | Perjelas: cache fit rerank dipakai CE **dan** LLM rerank bila aktif | [ ] |

---

## docs/pgvector-embeddings.md & docs/runbook-operasional.md

| # | Prioritas | Lokasi / klaim dokumen | Kode / fakta sekarang | Tindakan disarankan | Selesai |
|---|-----------|-------------------------|------------------------|---------------------|---------|
| V1 | — | pgvector / ANN / backfill | Selaras dengan `hybrid_retrieval` + scripts | Tidak wajib ubah | [ ] |
| O1 | — | `facilities.json` impor sync | Masih benar untuk **ingest** | Tambah kalimat: setelah impor, runtime baca JSONB | [ ] |

---

## MATERI_SIDANG_COFIND.md

| # | Prioritas | Lokasi / klaim dokumen | Kode / fakta sekarang | Tindakan disarankan | Selesai |
|---|-----------|-------------------------|------------------------|---------------------|---------|
| S1 | P1 | Fase 3 = **LLM rerank 60%** | CE + blend `COFIND_CE_RERANK_WEIGHT`; LLM rerank tidak di pipeline | Revisi seluruh bagian Fase 3 & diagram stack | [ ] |
| S2 | P1 | `facilities.json` / frontend path fasilitas | DB JSONB + admin editor | Update tabel data & Q&A metadata | [ ] |
| S3 | P1 | Metode sidang: “LLM rerank + grounding” sebagai inti Fase 3 | Grounding kutipan lebih ke evidence/LLM summary; CE rerank urutan | Narasi sidang: RRF → CE → summary LLM | [ ] |
| S4 | P2 | Referensi rujukan LLM rerank (Hou, RankGPT) | Tetap valid sebagai **literatur opsional** | Tambah catatan: implementasi produksi memakai cross-encoder lokal | [ ] |
| S5 | P3 | `pontianak_normalization_map.json` | Sudah benar “tidak ada” | — | [ ] |

---

## DOKUMENTASI_ACTIVITY_DIAGRAM_PLANTUML.md

| # | Prioritas | Lokasi / klaim dokumen | Kode / fakta sekarang | Tindakan disarankan | Selesai |
|---|-----------|-------------------------|------------------------|---------------------|---------|
| D1 | P1 | Isi pipeline di **`app.py`** `_recommendation_pipeline_events` | `recommendation/pipeline.py` | Ganti referensi file + nama fungsi | [ ] |
| D2 | P1 | Langkah 10: **`COFIND_LLM_RERANK`** Fase 3 | `ce_rerank_enabled()` + `ce_rerank_candidates` | Redraw cabang Fase 3 | [ ] |
| D3 | P2 | Data: `facilities.json` | JSONB DB | Update kotak data | [ ] |
| D4 | P2 | `rerank_backend`: `llm` / hybrid / cache | Telemetry pipeline: `cross_encoder` / `hybrid` (lihat `pipeline.py`) | Selaraskan legenda telemetri | [ ] |

---

## Komentar / docstring di kode (bukan markdown publik)

| # | Prioritas | Lokasi | Klaim | Fakta | Tindakan | Selesai |
|---|-----------|--------|-------|-------|----------|---------|
| X1 | P2 | `app.py` ~518 | “Weighted Multi-Signal Scoring + LLM Reasoning” | RRF + CE + summary LLM | Perbarui header komentar | [ ] |
| X2 | P2 | `free_text_intent.py` | `_read_recommendation_preferences di app.py` | `recommendation/request_prefs.py` | Perbarui komentar modul | [ ] |
| X3 | P3 | `recommendation/pipeline.py` komentar feedback | “LLM rerank memilih lagi” | CE rerank memilih | Ganti wording komentar | [ ] |
| X4 | P3 | `llm_recommender.py` header | Default rerank true | Pipeline tidak memanggil | Tambah catatan “not used by recommendation/pipeline unless wired” | [ ] |

---

## Diagram arsitektur sidang (gambar lama Anda)

| # | Prioritas | Elemen diagram lama | Ganti dengan | Selesai |
|---|-----------|---------------------|--------------|---------|
| G1 | P1 | Satu jalur pill saja | Pill **xor** free text (+ intent LLM) | [ ] |
| G2 | P1 | Normalisasi → hybrid scoring → activity gate → top 7 | Fase 1 filter → **RRF** → gate/metadata (pill) → evidence + ABSA → pool ~7 | [ ] |
| G3 | P1 | Proses LLM: re-rank top 7 → grounding → evidence & summary | **CE rerank** top ~7 → filter kontradiksi → **≤3 toko** → **summary LLM** (evidence di Fase 2) | [ ] |
| G4 | P2 | Google Places + facilities.json → DB (panah langsung ke runtime) | Sync **offline** → Supabase; request baca DB saja | [ ] |
| G5 | P2 | Feedback loop ke “build profile” | Feedback → DB analitik; **tidak** exclude retrieval | [ ] |
| G6 | P2 | GET top 7 = output user | Top 7 = pool rerank; **output max 3** | [ ] |

---

## Urutan kerja disarankan

1. **P1 README + recommendation-pipeline + materi sidang + diagram sidang (G1–G3)** — agar narasi sidang tidak salah.
2. **P1 arsitektur-rekomendasi sitasi** — doc audit tetap dipakai, hapus nomor baris `app.py` lama.
3. **P2 kalibrasi-parameter §C** — env dan tuning CE vs LLM.
4. **P3 komentar kode + cache doc** — konsistensi jangka panjang.

Setelah semua P1 centang, jalankan smoke: `python -m pytest tests/test_recommendation_wiring.py tests/test_cross_encoder_rerank.py -q` dan satu request manual ke `/api/recommend-by-preferences/stream` untuk memverifikasi `llm_pipeline.rerank.backend` = `cross_encoder` bila CE aktif.

---

*Terakhir diselaraskan dengan struktur repo saat penulisan checklist ini. Perbarui baris “Ringkasan kebenaran kode” jika pipeline di-wire ulang ke `llm_rerank_candidates`.*

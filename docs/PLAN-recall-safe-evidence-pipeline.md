# Plan: Recall-Safe Evidence Pipeline untuk Recommendation Modal

Dokumen ini adalah spesifikasi kerja untuk agent. Tujuannya mengubah cara CoFind
memilih kutipan ulasan yang tampil di recommendation modal, dari **pemangkasan
top-k buta** menjadi **cascade dua kecepatan**: lapisan murah menilai 100% korpus
secara offline, LLM hanya menangani zona ambigu dan wakil klaster.

Baca dokumen ini sampai selesai sebelum mengubah kode. Kerjakan per fase, satu
commit per fase, dan jangan lanjut ke fase berikutnya sebelum acceptance
criteria fase sebelumnya terpenuhi.

---

## 1. Konteks sistem saat ini

Stack: Flask + gunicorn, Supabase PostgreSQL (`db_backend.py`), Redis + Celery,
`rank_bm25`, sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`),
LLM Llama 3.1 8B Instruct via Hugging Face Router (`llm_backend.py`).

Pipeline rekomendasi aktif ada di `_recommendation_pipeline_events`
(`app.py` ~4237–4524) dengan alur:

```
get_reviews_for_recommendation_batch (review_utils.py:235)
  -> _build_profiles_for_recommendation (app.py:1060)
  -> retrieve_top_k (hybrid_retrieval.py:484)          # BM25 + dense + gerbang aktivitas
  -> _build_retrieval_evidence (app.py:4105)
  -> llm_rerank_candidates (llm_recommender.py:868)    # LLM pilih index kutipan
  -> _apply_llm_extracted_quotes (app.py:4154)
  -> _build_summary_output_entry (app.py:3476)
  -> JSON recommendations[].supporting_evidence
  -> frontend-cofind/src/components/RecommendationModal.jsx
```

### 1.1 Masalah yang harus diselesaikan

Pemangkasan terjadi **sebelum** sistem tahu sebuah ulasan relevan atau tidak,
sehingga ulasan yang berpotensi menjadi supporting evidence bisa hilang diam-diam.
Titik kehilangan yang wajib ditangani:

| # | Titik drop | Lokasi | Sifat masalah |
|---|---|---|---|
| D1 | Hanya 20 ulasan per toko yang di-embed (`COFIND_DENSE_MAX_REVIEWS`) | `hybrid_retrieval.py:171` `_select_reviews_for_embedding` | Kuota buta |
| D2 | `break` saat overlap leksikal nol | `hybrid_retrieval.py:199-200` | Ulasan bersinonim tidak pernah sampai ke embedding |
| D3 | Scan 60 ulasan (`COFIND_PROMPT_REVIEW_SCAN`) | `hybrid_retrieval.py:229` | Kuota buta |
| D4 | Ambil 8 ulasan (`COFIND_PROMPT_REVIEW_LIMIT`) | `hybrid_retrieval.py:273` | Hard cutoff |
| D5 | Teks < 15 char dibuang (`_MIN_REVIEW_CHARS`) | `hybrid_retrieval.py:161` | "wifi kenceng" justru evidence bagus |
| D6 | Dedup kunci `text.lower()[:160]` | `hybrid_retrieval.py:163` | Dua ulasan beda yang berawal sama saling menghapus |
| D7 | Maks 6 kutipan per kandidat ke prompt LLM | `llm_recommender.py:668` | Hard cutoff sebelum LLM menilai |
| D8 | Kutipan < 12 char dibuang | `llm_recommender.py:673` | Sama seperti D5 |
| D9 | Gerbang aktivitas leksikal bersifat AND | `hybrid_retrieval.py:406`, dipanggil di `:583` | Toko gugur total sebelum tahap kutipan |
| D10 | Threshold tunggal cosine 0.55 | `semantic_match.py:108` | Tidak terkalibrasi, membuang tanpa jejak |
| D11 | Toko tanpa `modal_display_quotes` di-drop | `app.py:3491` | Konsekuensi dari D1–D9 |

Penyebab struktural: embedding disimpan sebagai base64 float16 di JSON/Redis
dengan kunci hash teks (`vector_cache.py:77`), sehingga **hanya bisa lookup
exact, tidak bisa ANN search**. Karena korpus tidak bisa dicari, kode terpaksa
memuat subset kecil ke memori. Menghapus kuota tanpa memperbaiki penyimpanan
akan meledakkan latensi.

`llm_clause_sentiment.classify_quotes` sudah ditulis lengkap (batching, cache,
konkurensi) tetapi **`COFIND_LLM_CLAUSE_SENTIMENT` default `false` dan fungsinya
tidak pernah dipanggil** dari pipeline aktif.

---

## 2. Sasaran dan batasan

### 2.1 Sasaran

1. Setiap ulasan disentuh minimal satu kali oleh model murah, tanpa kecuali.
2. Tidak ada ulasan yang gugur karena posisi urutan atau kuota; yang gugur hanya
   yang skornya di bawah ambang terkalibrasi, dan itu tercatat di telemetri.
3. Ulasan yang tidak dikirim ke LLM tetap punya label, karena diwakili anggota
   klaster near-duplicate.
4. Biaya LLM per request turun, bukan naik, meski cakupan korpus menjadi 100%.
5. Ada angka miss-rate yang bisa dipertanggungjawabkan, bukan asumsi.

### 2.2 Non-sasaran

- Mengubah tampilan atau UX `RecommendationModal.jsx` (selain menghapus filter
  duplikat di sisi klien pada Fase 6).
- Mengganti provider LLM atau model chat.
- Fine-tuning LLM.
- Menambah vector database terpisah (Qdrant/Weaviate/Pinecone) — gunakan pgvector.
- Mengadopsi LangChain/LlamaIndex.

### 2.3 Aturan kerja

- **Semua fitur baru di belakang feature flag env var, default `false`.** Pipeline
  lama harus tetap jalan persis seperti sekarang saat flag mati.
- Konvensi DDL repo ini: fungsi idempoten `ensure_<nama>_table()` yang memanggil
  `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS`. Lihat contoh di
  `recommendation_feedback_utils.py:55` dan `preference_suggestion_utils.py:44`.
  Tidak ada framework migrasi; ikuti pola itu, jangan memperkenalkan Alembic.
- SQL ditulis bergaya SQLite dengan placeholder `?`; `AdaptingCursor` di
  `db_backend.py:97` yang menerjemahkan ke Postgres. Untuk SQL khusus Postgres
  (pgvector, tsvector) yang tidak bisa diadaptasi, tulis eksplisit dan pastikan
  melewati `_adapt_sql_postgres` dengan benar — verifikasi hasil adaptasinya.
- Semua env var baru diberi prefix `COFIND_`, didokumentasikan di `.env.example`,
  dan dibaca lewat helper bergaya `_env_flag` / `_env_int` yang sudah ada.
- Kode dan komentar dalam Bahasa Indonesia, mengikuti gaya modul yang ada
  (docstring modul menjelaskan alasan keberadaan modul, bukan sekadar apa).
- Jangan menghapus jalur legacy (`_score_shop_by_user_reviews`,
  `match_reviews`) dalam rangkaian fase ini; cukup biarkan tidak terpakai.

---

## 3. Arsitektur target

```
INGEST (offline, inkremental, per ulasan baru — Celery)
  Fase 1  pecah klausa -> normalisasi slang -> simpan ke review_clauses
  Fase 2  embedding lokal (ONNX) -> kolom vector(dim) + tsvector -> index HNSW & GIN
  Fase 5  skor terhadap katalog pill -> clause_pill_scores (precompute penuh)
  Fase 4  klaster near-duplicate -> cluster_id

REQUEST (online)
  Fase 3  gate recall-safe: UNION (leksikal OR dense OR trigram) via satu query SQL
  Fase 4  triase tiga pita:
            skor >= tau_high            -> terima langsung, tanpa LLM
            tau_low <= skor < tau_high  -> cross-encoder, lalu LLM bila masih ambigu
            skor <  tau_low             -> tolak, catat di telemetri
  Fase 4  hanya representatif klaster yang dikirim ke LLM; label diwariskan
  Fase 5  penghentian adaptif menggantikan hard cutoff
  Fase 6  rakit supporting_evidence -> modal
  Fase 7  telemetri recall + shadow run
```

---

## 4. Fase kerja

### Fase 0 — Baseline dan harness pengukuran

**Kenapa pertama:** tanpa angka pembanding, tidak ada cara membuktikan fase
berikutnya memperbaiki recall dan bukan sekadar mengubah keluaran.

Tugas:

1. Buat `scripts/eval_recall.py` yang: mengambil N toko dari database, menjalankan
   pipeline rekomendasi untuk sekumpulan kombinasi pill, dan mencatat himpunan
   `modal_display_quotes` yang dihasilkan ke file JSON bertanda versi.
2. Buat gold set manual di `data/eval/gold_evidence.jsonl`. Format per baris:
   `{"place_id": "...", "pills": ["..."], "review_id": 123, "clause": "...", "label": "supporting|caveat|irrelevant"}`.
   Minimal 150 klausa berlabel dari minimal 10 toko, mencakup kasus sulit:
   negasi ("ngga nyaman"), sinonim ("koneksinya ngebut" untuk aspek wifi),
   klausa campur ("kursinya bagus tapi ngga nyaman"), dan slang.
   Bila tidak ada label manusia, hasilkan label kandidat dengan LLM lalu tandai
   `"source": "llm-bootstrap"` — jangan mengklaim itu gold set manusia.
3. Hitung dan cetak metrik: **recall** (proporsi klausa berlabel `supporting`
   yang muncul di keluaran pipeline), **precision**, dan jumlah panggilan LLM
   per request.
4. Simpan hasil baseline ke `data/eval/baseline.json` dan commit.

Acceptance criteria:
- `python scripts/eval_recall.py --baseline` berjalan tanpa error dan
  menghasilkan angka recall/precision/biaya untuk pipeline saat ini.
- Angka baseline tercatat di `data/eval/baseline.json`.

---

### Fase 1 — Tabel klausa dan backfill

Tugas:

1. Buat modul baru `clause_store.py` dengan `ensure_clause_tables()` yang membuat:

```sql
CREATE TABLE IF NOT EXISTS review_clauses (
    id           SERIAL PRIMARY KEY,
    review_id    INTEGER NOT NULL,
    place_id     TEXT NOT NULL,
    clause_index INTEGER NOT NULL,
    clause_text  TEXT NOT NULL,
    normalized   TEXT NOT NULL,      -- hasil normalize_text_with_slang
    char_len     INTEGER NOT NULL,
    cluster_id   INTEGER,            -- diisi Fase 4
    content_hash TEXT NOT NULL,      -- sha1(normalized), untuk dedup lintas ulasan
    created_at   TIMESTAMP DEFAULT NOW(),
    UNIQUE (review_id, clause_index)
);
CREATE INDEX IF NOT EXISTS idx_review_clauses_place ON review_clauses (place_id);
CREATE INDEX IF NOT EXISTS idx_review_clauses_hash  ON review_clauses (content_hash);
```

2. Gunakan `semantic_match.split_clauses` untuk pemecahan, dan
   `slang_normalize.normalize_text_with_slang` untuk kolom `normalized`.
3. **Perbaiki D5:** batas minimum panjang klausa turun menjadi 3 karakter, bukan
   15. Klausa pendek seperti "wifi ok" harus masuk index. Batas ini jadi konstanta
   `_MIN_CLAUSE_CHARS = 3` di `clause_store.py`.
4. Tambahkan Celery task `cofind.index_review_clauses` di `tasks.py` yang
   meng-index satu `review_id`, dan panggil task itu dari jalur pembuatan review
   di `api/review_routes.py` (fire-and-forget; kegagalan index tidak boleh
   menggagalkan penyimpanan review).
5. Buat `scripts/backfill_clauses.py` untuk meng-index seluruh ulasan yang sudah
   ada, dengan progress log, batasan batch, dan sifat resumable (lewati
   `review_id` yang sudah ada barisnya).

Acceptance criteria:
- Setelah backfill, `SELECT COUNT(DISTINCT review_id) FROM review_clauses` sama
  dengan jumlah ulasan yang punya teks non-kosong di tabel `reviews`. **Nol
  ulasan boleh hilang** — bila ada selisih, cetak daftar `review_id` yang gagal
  beserta alasannya.
- Menjalankan ulang backfill bersifat idempoten (tidak menduplikasi baris).

---

### Fase 2 — pgvector, full-text search, dan embedding ONNX

Tugas:

1. Aktifkan extension di Supabase: `CREATE EXTENSION IF NOT EXISTS vector;` dan
   `CREATE EXTENSION IF NOT EXISTS pg_trgm;` di dalam `ensure_clause_tables()`,
   dibungkus try/except karena butuh privilese dan bisa gagal di lingkungan lokal.
2. Tambahkan kolom dan indeks:

```sql
ALTER TABLE review_clauses ADD COLUMN IF NOT EXISTS embedding vector(768);
ALTER TABLE review_clauses ADD COLUMN IF NOT EXISTS tsv tsvector;
CREATE INDEX IF NOT EXISTS idx_review_clauses_hnsw
    ON review_clauses USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_review_clauses_tsv
    ON review_clauses USING gin (tsv);
CREATE INDEX IF NOT EXISTS idx_review_clauses_trgm
    ON review_clauses USING gin (normalized gin_trgm_ops);
```

   Dimensi vektor harus mengikuti model yang dipilih di poin 4 — jangan
   hardcode 768 bila modelnya 384. Simpan dimensinya sebagai konstanta modul dan
   validasi saat startup.

3. Isi `tsv` dengan `to_tsvector('simple', normalized)`. **Jangan pakai
   konfigurasi `'indonesian'`** — Postgres tidak menyediakannya. Stemming
   dilakukan di sisi Python dengan Sastrawi saat mengisi kolom `normalized`.
4. Ganti backend embedding: tambahkan `onnx_embedder.py` yang memuat model lewat
   `onnxruntime` (via `optimum` atau `fastembed`), dengan kuantisasi int8.
   Model yang direkomendasikan: `intfloat/multilingual-e5-base` atau
   `BAAI/bge-m3`; keduanya jauh lebih kuat untuk Bahasa Indonesia daripada
   `paraphrase-multilingual-MiniLM-L12-v2` yang dipakai sekarang.
   - `semantic_match.load_model` harus tetap berfungsi sebagai fallback bila
     ONNX tidak tersedia, agar deploy tidak pernah mati total.
   - Env baru: `COFIND_EMBEDDING_BACKEND` (`onnx` | `sentence_transformers`,
     default `sentence_transformers` pada tahap ini).
   - Catat di `requirements.txt` bahwa torch menjadi opsional bila backend ONNX
     dipakai; jangan hapus `sentence-transformers` dari requirements pada fase ini.
5. Perluas `scripts/backfill_clauses.py` agar mengisi `embedding` dan `tsv`,
   dengan batching dan checkpoint.

Acceptance criteria:
- Query `SELECT clause_text FROM review_clauses ORDER BY embedding <=> $1 LIMIT 20`
  mengembalikan hasil masuk akal untuk vektor query "wifi kencang untuk kerja".
- Tidak ada baris `review_clauses` dengan `embedding IS NULL` setelah backfill.
- Latensi query ANN pada korpus penuh di bawah 100 ms.
- Benchmark tercatat: waktu embedding per 1000 klausa untuk backend ONNX vs
  sentence-transformers, ditulis di deskripsi PR.

---

### Fase 3 — Gate recall-safe menggantikan kuota

Ini fase yang menghapus D1, D2, D3, D4, D6, dan D9.

Tugas:

1. Buat `clause_retrieval.py` dengan fungsi
   `gather_candidates(place_ids, aspect_terms, *, tau_low) -> List[ClauseCandidate]`
   yang menjalankan **satu query SQL** berisi **UNION** dari tiga kanal:
   - leksikal: `tsv @@ plainto_tsquery('simple', :q)` dengan skor `ts_rank`;
   - dense: `1 - (embedding <=> :qvec) >= :tau_low`;
   - trigram: `similarity(normalized, :q) > 0.3` untuk menangkap salah ketik.
   Gabungkan peringkat ketiga kanal dengan **Reciprocal Rank Fusion**, bukan
   penjumlahan skor mentah berbobot (skala ketiganya tidak sebanding).
2. **Kanal harus UNION, bukan INTERSECT.** Gerbang aktivitas sekarang
   (`shop_has_activity_signal`, `hybrid_retrieval.py:406`) bersifat AND terhadap
   sinyal dense dan menggugurkan toko secara keseluruhan; di jalur baru, sinyal
   aktivitas menjadi salah satu kanal recall, bukan syarat wajib.
3. **Hapus semua batas kuota di jalur baru.** Tidak ada `LIMIT` pada tahap
   kandidat selain ambang `tau_low`. Kalau jumlah kandidat besar, itu ditangani
   Fase 4 (klaster) dan Fase 5 (penghentian adaptif), bukan dengan memotong.
4. **Perbaiki D6:** dedup memakai `content_hash` dari teks penuh, bukan 160
   karakter pertama.
5. Feature flag: `COFIND_CLAUSE_RETRIEVAL` (default `false`). Saat `true`,
   `_build_retrieval_evidence` (`app.py:4105`) memakai jalur baru; saat `false`,
   memakai `rank_reviews_for_query` yang lama.

Acceptance criteria:
- Dengan flag menyala, `scripts/eval_recall.py` menunjukkan recall **naik**
  dibanding baseline Fase 0, tanpa penurunan precision lebih dari 5 poin.
- Untuk setiap entri gold set berlabel `supporting`, klausa tersebut **ada di
  himpunan kandidat** (bukan harus tampil di modal, tapi harus lolos gate).
  Tulis pengujian ini sebagai assertion otomatis; kegagalan satu pun entri
  berarti fase ini belum selesai.

---

### Fase 4 — Triase tiga pita, cross-encoder, dan klaster

Tugas:

1. **Kalibrasi ambang.** Buat `scripts/calibrate_thresholds.py` yang mencari
   `tau_low` terbesar yang masih memberi **recall 100%** pada gold set, lalu
   `tau_high` terkecil yang memberi precision >= 0.95. Tulis hasilnya ke
   `data/eval/thresholds.json` dan baca dari sana saat runtime, dengan env
   `COFIND_TAU_LOW` / `COFIND_TAU_HIGH` sebagai override manual.
   Angka 0.55 di `semantic_match.py:108` adalah tebakan; jangan diwariskan.
2. **Klaster near-duplicate.** Tambahkan job yang mengelompokkan klausa dengan
   cosine >= 0.92 ke `cluster_id` yang sama (pakai ANN pgvector, bukan
   perbandingan O(n^2)). Satu representatif per klaster yang dikirim ke penilai;
   **label hasilnya diwariskan ke seluruh anggota klaster** sehingga anggota lain
   tetap layak dipilih sebagai kutipan tampil. Ini penghemat biaya, bukan
   pemotong recall — pastikan implementasinya benar-benar mewariskan label dan
   tidak membuang anggota klaster.
3. **Cross-encoder untuk band ambigu.** Tambahkan `cross_encoder.py` memakai
   `BAAI/bge-reranker-v2-m3` (akurat) atau `mmarco-mMiniLMv2-L12-H384-v1`
   (ringan), dijalankan lewat ONNX Runtime di CPU. Perannya menilai pasangan
   (aspek, klausa) di band `tau_low..tau_high` sebelum LLM dipanggil.
   Env: `COFIND_CROSS_ENCODER` (default `false`), `COFIND_CROSS_ENCODER_MODEL`.
4. **Aktifkan clause sentiment LLM.** Sambungkan
   `llm_clause_sentiment.classify_quotes` ke pipeline untuk klausa yang masih
   ambigu setelah cross-encoder. Modulnya sudah siap; yang perlu dilakukan:
   - ubah default `COFIND_LLM_CLAUSE_SENTIMENT` menjadi `true` **hanya setelah**
     jalur ini terbukti di staging;
   - turunkan `_MIN_CLAUSE_CHARS` di `llm_clause_sentiment.py:39` dari 8 ke 3
     agar konsisten dengan Fase 1;
   - hapus batas `COFIND_CLAUSE_SENTIMENT_MAX` sebagai pemotong keras; ganti
     menjadi batas anggaran yang, bila tercapai, **mencatat sisa kandidat di
     telemetri dan menjadwalkan penilaiannya secara asinkron**, bukan
     membuangnya diam-diam.
5. **Structured output.** Ganti parsing regex + `json-repair` di
   `_parse_batch_response` (`llm_clause_sentiment.py:124`) dengan
   `response_format` JSON Schema bila provider mendukung. Pertahankan parser
   lama sebagai fallback. Tujuannya menghilangkan `failed_batches` yang saat ini
   menyebabkan klausa kehilangan verdict secara diam-diam.

Acceptance criteria:
- Recall pada gold set tetap 100% untuk label `supporting`.
- Jumlah panggilan LLM per request **turun** dibanding baseline Fase 0 meski
  cakupan korpus menjadi 100%. Sertakan angkanya di deskripsi PR.
- Setiap klausa yang tidak dikirim ke LLM punya alasan terekam: `above_tau_high`,
  `below_tau_low`, `cluster_member`, atau `cache_hit`.

---

### Fase 5 — Penghentian adaptif menggantikan hard cutoff

Tugas:

1. Hapus `[:take]` di `rank_reviews_for_query` (`hybrid_retrieval.py:273`) dan
   batas 6 kutipan di `_quote_candidates_for_prompt` (`llm_recommender.py:668`)
   **pada jalur baru**. Gantikan dengan aturan berhenti:
   ambil kandidat berurutan sampai kuota tampilan modal terpenuhi **dan** skor
   kandidat berikutnya berada di bawah skor kandidat terakhir yang diterima
   dikurangi margin. Bila masih ada kandidat di atas ambang, jalankan batch
   tambahan alih-alih memotong.
2. Precompute skor (klausa x pill) di background. Katalog pill bersifat terbatas
   (`PILL_MAPPING` di `app.py`), jadi seluruh matriks bisa dihitung penuh oleh
   Celery task. Tabel:

```sql
CREATE TABLE IF NOT EXISTS clause_pill_scores (
    clause_id  INTEGER NOT NULL,
    pill       TEXT NOT NULL,
    score      REAL NOT NULL,
    label      TEXT,               -- supporting | caveat | irrelevant
    label_src  TEXT,               -- dense | cross_encoder | llm | cluster | setfit
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (clause_id, pill)
);
```

3. Task refresh dijalankan saat: pill baru ditambahkan, ulasan baru masuk, atau
   model embedding berganti. Tambahkan kolom versi model agar entri basi bisa
   diidentifikasi dan dihitung ulang.

Acceptance criteria:
- Untuk toko dengan lebih dari 100 ulasan, tidak ada kandidat di atas `tau_high`
  yang gagal dipertimbangkan hanya karena urutan.
- Latensi p95 endpoint rekomendasi tidak lebih buruk dari baseline.

---

### Fase 6 — Perakitan evidence dan modal

Tugas:

1. `_apply_llm_extracted_quotes` (`app.py:4154`) dan
   `_build_summary_output_entry` (`app.py:3476`) membaca label dari
   `clause_pill_scores`, bukan hanya dari hasil rerank LLM.
2. **Tangani D11:** toko tidak lagi di-drop hanya karena `modal_display_quotes`
   kosong bila sebenarnya ada kandidat berlabel `supporting` di database. Bila
   memang benar-benar tidak ada evidence, drop-nya sah tapi harus tercatat di
   telemetri dengan alasan.
3. Di `RecommendationModal.jsx`, filter duplikat di sisi klien
   (`quoteLooksUnsuitable` sekitar baris 57, dipakai di 94/208/226) menjadi tidak
   perlu karena penyaringan sudah dilakukan di backend dengan label eksplisit.
   Hapus filter heuristik itu, tetapi **pertahankan** batas jumlah tampilan
   (3 supporting, 2 caveat) karena itu keputusan UI, bukan recall.
4. Struktur `supporting_evidence` tetap kompatibel: field `modal_display_quotes`,
   `modal_caveat_quotes`, `review_quotes` tidak berubah namanya. Tambahkan field
   baru `evidence_provenance` berisi `{clause_id, label_src, score}` per kutipan
   untuk keperluan debugging dan audit.

Acceptance criteria:
- Kontrak JSON lama tidak rusak; frontend versi lama tetap bisa merender.
- Setiap kutipan yang tampil bisa ditelusuri sampai `clause_id` dan sumber
  labelnya.

---

### Fase 7 — Observability dan pembuktian recall

Tugas:

1. Tambahkan telemetri per request: `candidates_gated`, `candidates_by_band`,
   `clusters_represented`, `llm_calls`, `cache_hit_rate`, `dropped_with_reason`.
2. Integrasikan **Langfuse** (self-host) atau OpenTelemetry untuk melacak setiap
   panggilan LLM berikut biaya, latensi, dan prompt. Env:
   `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`. Bila kunci
   kosong, tracing mati total tanpa error.
3. Tambahkan **shadow run** terjadwal: satu sampel toko diproses tanpa gate sama
   sekali (semua klausa dinilai LLM), lalu hasilnya dibandingkan dengan pipeline
   bergate. Selisihnya adalah **miss-rate**, dan angka itulah yang menjadi bukti
   klaim "tidak ada evidence yang terlewat". Simpan hasil ke
   `data/eval/shadow_runs/` dan gagalkan CI bila miss-rate melebihi ambang yang
   disepakati.
4. Pertimbangkan **Ragas** untuk metrik `context_recall` dan `faithfulness`
   sebagai pelengkap `scripts/eval_recall.py`.

Acceptance criteria:
- Ada dashboard atau laporan yang menampilkan miss-rate per periode.
- Shadow run berjalan otomatis dan hasilnya tersimpan berversi.

---

### Fase 8 — Distilasi ke classifier lokal (opsional, setelah data terkumpul)

Setelah `clause_sentiment` mengumpulkan cukup label LLM (target minimal 2000
pasangan aspek-klausa), latih classifier kecil untuk mengeluarkan LLM dari jalur
panas sepenuhnya.

Tugas:

1. Ekspor label dari cache dan `clause_pill_scores` menjadi dataset latih.
2. Latih **SetFit** (dibangun di atas sentence-transformers yang sudah ada, cukup
   ratusan contoh per kelas) atau, bila ingin lebih sederhana, regresi logistik
   scikit-learn di atas embedding klausa.
3. Evaluasi terhadap gold set. **Adopsi hanya bila recall tidak turun** dibanding
   jalur LLM. Bila turun, tetap pakai LLM untuk band ambigu.
4. Setelah diadopsi, LLM berperan sebagai pelabel data untuk kasus baru saja.

Acceptance criteria:
- Perbandingan metrik classifier vs LLM terdokumentasi.
- Keputusan adopsi didasarkan pada angka, bukan asumsi penghematan.

---

## 5. Ringkasan env var baru

| Env | Default | Fase | Fungsi |
|---|---|---|---|
| `COFIND_CLAUSE_INDEX` | `false` | 1 | Aktifkan indexing klausa saat review masuk |
| `COFIND_EMBEDDING_BACKEND` | `sentence_transformers` | 2 | `onnx` atau `sentence_transformers` |
| `COFIND_EMBEDDING_MODEL` | (ada) | 2 | Ganti ke e5-base atau bge-m3 |
| `COFIND_CLAUSE_RETRIEVAL` | `false` | 3 | Pakai gate SQL menggantikan kuota |
| `COFIND_TAU_LOW` | dari kalibrasi | 4 | Ambang bawah gate |
| `COFIND_TAU_HIGH` | dari kalibrasi | 4 | Ambang auto-accept |
| `COFIND_CROSS_ENCODER` | `false` | 4 | Aktifkan reranker |
| `COFIND_CROSS_ENCODER_MODEL` | `BAAI/bge-reranker-v2-m3` | 4 | Model reranker |
| `COFIND_CLUSTER_THRESHOLD` | `0.92` | 4 | Ambang klaster near-duplicate |
| `COFIND_LLM_CLAUSE_SENTIMENT` | `false` -> `true` | 4 | Sudah ada, diaktifkan setelah terbukti |
| `COFIND_SHADOW_RUN` | `false` | 7 | Jalankan pembanding tanpa gate |
| `LANGFUSE_*` | kosong | 7 | Tracing LLM |

Semua wajib didokumentasikan di `.env.example`.

---

## 6. Teknologi yang diadopsi dan yang ditolak

Diadopsi: **pgvector** (ANN di Supabase, tanpa infra baru), **Postgres FTS +
pg_trgm** (menggantikan `rank_bm25` in-memory yang dibangun ulang tiap request),
**cross-encoder reranker** (akurasi mendekati LLM dengan biaya CPU),
**ONNX Runtime / fastembed** (buang torch, image kecil, cold start cepat),
**SetFit / scikit-learn** (distilasi), **structured output** (hilangkan kegagalan
parsing diam-diam), **Langfuse + Ragas** (pembuktian recall).

Ditolak beserta alasannya: vector database terpisah (pgvector cukup sampai
jutaan klausa dan menghindari sinkronisasi dua sistem), LangChain/LlamaIndex
(abstraksinya menyembunyikan titik pemangkasan yang justru perlu dikendalikan),
Elasticsearch (sepadan hanya pada korpus jauh lebih besar), fine-tuning LLM
sendiri (distilasi memberi manfaat setara dengan risiko jauh lebih rendah),
Alembic (repo ini memakai pola `ensure_*_table()` idempoten).

---

## 7. Risiko dan mitigasi

| Risiko | Mitigasi |
|---|---|
| Menghapus kuota meledakkan latensi | Jangan hapus kuota sebelum Fase 2 selesai; ANN + precompute yang membuatnya aman |
| pgvector tidak aktif di plan Supabase | Verifikasi di awal Fase 2; bila gagal, hentikan dan laporkan, jangan lanjut ke Fase 3 |
| Model embedding baru mengubah semua skor | Kolom versi model di `clause_pill_scores` + hitung ulang penuh saat berganti |
| Backfill berat pada korpus besar | Batching, resumable, dijalankan di worker Celery, bukan di web dyno |
| Gold set terlalu kecil sehingga kalibrasi bias | Minimal 150 klausa dari 10+ toko; catat keterbatasannya dengan jujur di laporan |
| Regresi diam-diam saat flag dinyalakan | Semua flag default `false`; bandingkan dengan baseline sebelum menyalakan |

---

## 8. Definisi selesai

Pekerjaan dianggap selesai bila:

1. Setiap ulasan berteks di database punya minimal satu baris di `review_clauses`
   dengan `embedding` terisi.
2. Recall pada gold set untuk label `supporting` mencapai 100%, dibuktikan oleh
   assertion otomatis di `scripts/eval_recall.py`.
3. Jumlah panggilan LLM per request lebih rendah daripada baseline Fase 0.
4. Setiap klausa yang tidak dinilai LLM punya alasan terekam.
5. Shadow run berjalan dan miss-rate-nya terdokumentasi.
6. Semua fitur baru bisa dimatikan lewat env var dan pipeline lama kembali utuh.

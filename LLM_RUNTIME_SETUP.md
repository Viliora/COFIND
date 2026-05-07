# LLM Runtime Setup (Inference Providers API + Async Summary)

## 1) Install dependencies backend

```bash
pip install -r requirements.txt
```

## 2) Konfigurasi Inference Providers

Pastikan `.env` mengandung:

```env
HF_LLM_BACKEND=inference
HF_INFERENCE_PROVIDER=featherless-ai
HF_API_TOKEN=your_token
HF_MODEL=meta-llama/Llama-3.2-1B-Instruct
HF_KEYWORD_MODEL=meta-llama/Llama-3.2-1B-Instruct
HF_LLM_MAX_RETRIES=2
HF_LLM_BACKOFF_FACTOR=0.8
```

## 3) Jalankan Redis untuk Celery

Contoh lokal:

```bash
redis-server
```

## 4) Jalankan Flask API

```bash
python app.py
```

## 5) Jalankan worker async summary

```bash
celery -A tasks worker --loglevel=info
```

## 6) Polling job async summary

- Submit: `POST /api/llm/summarize-review`
- Jika async aktif (`COFIND_SUMMARY_ASYNC=true`), response `202` berisi `job_id`.
- Poll status: `GET /api/jobs/<job_id>`.

## 7) Feature flags penting

```env
COFIND_RERANK_BACKEND=llm
COFIND_SUMMARY_ASYNC=true
```

- `COFIND_RERANK_BACKEND=cross_encoder` jika ingin pakai reranker cross-encoder lagi.
- `COFIND_SUMMARY_ASYNC=false` untuk rollback ke summary sinkron.

## 8) Troubleshooting cepat

- Cek health runtime:
  - `GET /health`
- Jika worker macet:
  - stop worker lama, lalu jalankan ulang
  - `celery -A tasks worker --loglevel=info --concurrency=1`
- Jika Redis membengkak:
  - pastikan `COFIND_JOB_RESULT_TTL_SECONDS` terpasang (default 1 jam).
- Jika provider inference flaky:
  - cek token + model id + provider
  - tuning retry env:
    - `HF_LLM_MAX_RETRIES`
    - `HF_LLM_BACKOFF_FACTOR`
- Jika ingin switch backend cepat:
  - tetap gunakan `HF_LLM_BACKEND=inference` (backend lain sudah dinonaktifkan), ubah `HF_INFERENCE_PROVIDER` dan restart backend.

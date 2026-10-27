# Evaluasi RAGAS (dev)

Evaluasi offline kualitas RAG/rekomendasi dengan [RAGAS](https://docs.ragas.io/) **0.4.3**. Judge LLM: **Gemini** (`GEMINI_API_KEY`, `GEMINI_MODEL` atau `COFIND_RAGAS_GEMINI_MODEL`).

Dependensi hanya di [`requirements-dev.txt`](../../requirements-dev.txt) — **tidak** memengaruhi deploy production (`requirements.txt`).

Pin penting: `ragas==0.4.3`, `langchain-community>=0.3,<0.4` (import RAGAS), `instructor[google-genai]` + `jsonref` (structured output Gemini judge).

## Prasyarat

```powershell
pip install -r requirements-dev.txt
```

`.env` harus berisi `GEMINI_API_KEY`. Untuk export pipeline (HF quota habis), skrip export mengosongkan `HF_API_TOKEN` setelah `load_dotenv` agar probe memakai Gemini.

Smoke import:

```powershell
python -c "import ragas; print(ragas.__version__)"
```

## Urutan

### 1. Smoke dataset sintetis

```powershell
python scripts/eval/ragas_eval.py --dataset scripts/eval/ragas_smoke_dataset.json --use-ragas
```

Metrik default: `faithfulness`, `answer_relevancy`, `context_precision`, `context_recall`.

Opsional context relevancy (NVidia):

```powershell
python scripts/eval/ragas_eval.py --dataset scripts/eval/ragas_smoke_dataset.json --use-ragas --context-relevance
```

Laporan: [`ragas_report.json`](ragas_report.json).

### 2. Export dari golden queries (DB + pipeline)

```powershell
python scripts/eval/export_ragas_dataset.py --dry-run
python scripts/eval/export_ragas_dataset.py --limit 18
```

Output: [`data/eval/ragas_cases.jsonl`](../../data/eval/ragas_cases.jsonl).

### 3. Eval pada export

```powershell
python scripts/eval/ragas_eval.py --dataset data/eval/ragas_cases.jsonl --use-ragas
```

Filter baris yang `export_error` / `response` kosong sebelum interpretasi penelitian.

## Kolom dataset

| Field | RAGAS | Keterangan |
|-------|-------|------------|
| `user_input` / `question` | ya | Intent user |
| `contexts` / `retrieved_contexts` | ya | Chunk ulasan/kutipan retrieval |
| `response` / `answer` | ya | Output user-facing (toko + alasan + bukti) |
| `ground_truth` / `reference` | context P/R | Referensi naratif anotator |

## vs grounding deterministik Cofind

Tahap D di [`llm_recommender.py`](../../llm_recommender.py) (`text_is_grounded`, `ungrounded_quotes`) auditable dan dipakai produksi. Skor RAGAS Faithfulness adalah **LLM-as-judge** — bandingkan korelasi, jangan anggap definisi identik.

## Env opsional

| Variabel | Default |
|----------|---------|
| `COFIND_RAGAS_GEMINI_MODEL` | `GEMINI_MODEL` |
| `COFIND_RAGAS_EMBEDDING_MODEL` | `gemini-embedding-001` |

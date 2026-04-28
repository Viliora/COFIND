#!/usr/bin/env python3
"""
Estimasi token untuk alur /api/recommend-by-preferences (LLM summary + opsional rerank).
Membangun string prompt dengan struktur sama seperti app.py (tanpa import app).

Tokenizer: coba model di HF_MODEL / Meta Llama 3 family; fallback ke perkiraan karakter.
"""
from __future__ import annotations

import os
import sys

# Samakan default dengan app.py
HF_MODEL = os.getenv("HF_MODEL", "meta-llama/Meta-Llama-3-8B").strip()

CUSTOM_QUERY = (
    "saya ingin coffee shop yang enak buat nugas dan ada tempat solat atau musholla"
)


def truncate_evidence_text(text: str, limit: int = 160) -> str:
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + "..."


def build_intent_line(pills: list[str], custom_query: str) -> str:
    intent_parts = list(pills)
    if custom_query:
        intent_parts.append(f'kebutuhan tambahan: "{custom_query[:200]}"')
    return " | ".join(intent_parts) if intent_parts else "preferensi umum"


def build_rerank_prompt(custom_query: str, num_candidates: int = 10, reviews_per_shop: int = 5) -> str:
    intent_line = build_intent_line([], custom_query)
    shop_blocks = []
    for idx in range(1, num_candidates + 1):
        review_lines = []
        for r in range(reviews_per_shop):
            body = (
                f"Review contoh {idx}-{r}: tempat nyaman buat kerja, wifi lumayan, "
                f"ada musholla kecil di belakang, kopi enak. " * 3
            )
            review_lines.append(
                f'  - "{truncate_evidence_text(body, 160)}" (rating: {4 + (r % 2)})'
            )
        shop_blocks.append(
            f"{idx}. Coffee Shop {idx} (place_id: PLACE_{idx}) - "
            f"total review: 42, avg rating user: 4.2\n" + "\n".join(review_lines)
        )

    role = (
        "ROLE / PERSONA:\n"
        "Kamu adalah sistem pemeringkat internal Cofind untuk rekomendasi coffee shop. "
        "Tugasmu hanya mengurutkan kandidat berdasarkan bukti review user, bukan menulis promosi."
    )
    style = (
        "STYLE INSTRUCTION:\n"
        "- Berpikir objektif dan ringkas.\n"
        "- Nilai kecocokan dari review yang eksplisit menyebut kebutuhan user.\n"
        "- Dahulukan bukti review yang konkret, spesifik, dan relevan."
    )
    context = (
        "CONTEXT:\n"
        f"Kebutuhan user: {intent_line}\n\n"
        "Kandidat coffee shop dan review user:\n"
        + "\n\n".join(shop_blocks)
    )
    guardrail = (
        "GUARDRAIL:\n"
        "- Ranking HARUS berdasarkan isi review user di atas saja, bukan nama toko atau asumsi.\n"
        "- Jika dua kandidat sama relevannya, dahulukan yang bukti reviewnya paling konkret.\n"
        "- Jangan mengarang place_id; place_id harus PERSIS sama seperti data di atas.\n"
        "- Output HANYA JSON array 3 teratas, contoh:\n"
        '[{"place_id":"xxx","rank":1,"reason":"alasan singkat"}]\n\nJSON:'
    )
    return "\n\n".join([role, style, context, guardrail])


def build_summary_prompt(custom_query: str, quote_chars: int) -> str:
    """quote_chars: panjang kasar tiap kutipan review (3 kutipan per toko, 3 toko)."""
    intent_line = build_intent_line([], custom_query)
    is_manual_mode = bool(custom_query)

    def make_quote(n: int) -> str:
        base = (
            "Tempatnya enak buat nugas, colokan cukup, suasana tenang. "
            "Ada musholla kecil untuk sholat. Kopinya recommended. "
        )
        q = (base * ((quote_chars // 80) + 1))[:quote_chars]
        return q

    shop_blocks = []
    for idx in range(1, 4):
        stats_lines = [
            "  - Nyaman & produktif: 3 review menyebut kata terkait, rata-rata rating_suasana=4.1",
            "  - Ruang ibadah: 2 review menyebut kata terkait",
        ]
        quote_lines = []
        for qn in range(3):
            quote_lines.append(
                f'  - "{make_quote(quote_chars)}" (untuk preferensi, rating: {4.5 - qn * 0.2})'
            )
        cat_info = "makanan: 4.0, layanan: 4.2, suasana: 4.3"
        shop_blocks.append(
            f"{idx}. Toko Rekomendasi {idx} (place_id: PID_{idx})\n"
            f"  Total review user: 28, avg rating user: 4.3\n"
            f"  Rating kategori: {cat_info}\n"
            f"  Statistik pill:\n" + "\n".join(stats_lines) + "\n"
            f"  Kutipan review:\n" + "\n".join(quote_lines)
        )

    role = (
        "ROLE / PERSONA:\n"
        "Kamu adalah Cofind Assistant, teman ngopi digital yang membantu user memilih coffee shop "
        "berdasarkan review pengguna nyata. Kamu berbicara hangat, jujur, dan tidak melebih-lebihkan."
    )
    style = (
        "STYLE INSTRUCTION:\n"
        "- Tulis dalam Bahasa Indonesia yang natural, ringan, dan personal.\n"
        "- Tulis 1 sampai 2 kalimat pendek per coffee shop.\n"
        "- Awali dari kebutuhan user, misalnya 'Kalau Anda mencari...' atau 'Tempat ini terasa cocok...'.\n"
        "- Hindari gaya iklan, kalimat kaku seperti 'Cocok untuk X:', daftar poin, nomor urut, dan emoji.\n"
        "- Jangan gunakan istilah teknis seperti place_id, evidence, skor, JSON, [fasilitas], atau [review]."
    )
    context = (
        "CONTEXT:\n"
        f"User ingin coffee shop yang: {intent_line}\n"
        f"Mode input: {'manual bebas' if is_manual_mode else 'pilihan preferensi'}\n\n"
        "Berikut 3 kandidat beserta DATA DARI REVIEW USER "
        "(tidak ada data fasilitas, tidak ada rating Google):\n\n"
        + "\n\n".join(shop_blocks)
    )
    guardrail = (
        "GUARDRAIL:\n"
        "- WAJIB merujuk atau mengutip data review user di atas, misalnya jumlah review yang menandai, "
        "isi komentar, atau rata-rata rating kategori.\n"
        "- JANGAN mengarang fakta di luar data yang diberikan.\n"
        "- Jika bukti review untuk preferensi user tipis, tulis secara hati-hati dan jangan memaksakan klaim.\n"
        "- place_id di output HARUS persis sama seperti data.\n"
        "- Output HANYA JSON array, contoh:\n"
        '[{"place_id":"xxx","name":"Nama","summary":"Kalimat..."}]\n\nJSON:'
    )
    return "\n\n".join([role, style, context, guardrail])


def count_tokens_hf(text: str, model_id: str) -> int | None:
    try:
        from transformers import AutoTokenizer
    except ImportError:
        return None
    try:
        tok = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        return len(tok.encode(text, add_special_tokens=True))
    except Exception as e:
        print(f"[INFO] Tokenizer '{model_id}' gagal: {e}", file=sys.stderr)
        return None


def rough_chars_to_tokens(text: str) -> float:
    """Perkiraan kasar untuk Bahasa Indonesia + JSON: ~3.5–4 char/token."""
    return len(text) / 3.7


def main() -> None:
    print("=== Konfigurasi LLM (app.py, alur rekomendasi) ===")
    print(f"HF_MODEL: {HF_MODEL}")
    print("Panggilan 1 (opsional) _llm_semantic_rerank: max_new_tokens = 400")
    print("Panggilan 2 _generate_llm_review_summary: max_new_tokens = 600")
    print("(Rerank hanya jika ada custom_query/pill DAN jumlah kandidat di atas ambang > 3.)")
    print()
    print("Catatan: Batas konteks model (mis. 8k token) ada di kartu model HF;")
    print("max_new_tokens hanya membatasi panjang OUTPUT generasi per request.\n")

    summary_short = build_summary_prompt(CUSTOM_QUERY, quote_chars=120)
    summary_mid = build_summary_prompt(CUSTOM_QUERY, quote_chars=280)
    summary_long = build_summary_prompt(CUSTOM_QUERY, quote_chars=600)

    rerank_prompt = build_rerank_prompt(CUSTOM_QUERY, num_candidates=10, reviews_per_shop=5)

    example_output_summary = (
        '[{"place_id":"PID_1","name":"Toko Rekomendasi 1","summary":"Kalau Anda mencari tempat untuk nugas '
        "dan sholat, ulasan menyebut musholla dan suasana tenang. Beberapa review juga menonjolkan kopi. "
        '"},'
        '{"place_id":"PID_2","name":"Toko Rekomendasi 2","summary":"..."},'
        '{"place_id":"PID_3","name":"Toko Rekomendasi 3","summary":"..."}]'
    )
    example_output_rerank = (
        '[{"place_id":"PLACE_2","rank":1,"reason":"Review menyebut musholla dan cocok kerja laptop"},'
        '{"place_id":"PLACE_1","rank":2,"reason":"..."},'
        '{"place_id":"PLACE_3","rank":3,"reason":"..."}]'
    )

    tokenizer_ids = [
        HF_MODEL,
        "meta-llama/Llama-3.2-1B-Instruct",
        "meta-llama/Meta-Llama-3-8B-Instruct",
        # Publik, arsitektur Llama: perkiraan token mendekati Llama 3 untuk teks Latin/Indonesia
        "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    ]

    tok_model = None
    for mid in tokenizer_ids:
        n = count_tokens_hf("test", mid)
        if n is not None:
            tok_model = mid
            print(f"Menggunakan tokenizer: {tok_model}\n")
            break

    def show_block(label: str, text: str) -> None:
        if tok_model:
            inp = count_tokens_hf(text, tok_model)
            print(f"{label}")
            print(f"  Perkiraan input tokens (tokenizer): {inp}")
        else:
            print(f"{label}")
            print(f"  Perkiraan input tokens (approx len/3.7): {rough_chars_to_tokens(text):.0f}")
        print(f"  Panjang karakter prompt: {len(text)}")

    show_block('Prompt SUMMARY (kutipan pendek ~120 char x 9):', summary_short)
    show_block('Prompt SUMMARY (kutipan sedang ~280 char x 9):', summary_mid)
    show_block('Prompt SUMMARY (kutipan panjang ~600 char x 9):', summary_long)
    show_block('Prompt RERANK (10 toko x 5 review x 160 char):', rerank_prompt)

    print("\n=== Perkiraan OUTPUT (bukan dari API nyata) ===")
    if tok_model:
        ot_sum = count_tokens_hf(example_output_summary, tok_model)
        ot_rer = count_tokens_hf(example_output_rerank, tok_model)
        print(f"Contoh JSON summary 3 toko: ~{ot_sum} tokens")
        print(f"Contoh JSON rerank top 3:   ~{ot_rer} tokens")
    else:
        print(f"Contoh JSON summary: ~{rough_chars_to_tokens(example_output_summary):.0f} tokens")
        print(f"Contoh JSON rerank:  ~{rough_chars_to_tokens(example_output_rerank):.0f} tokens")

    print("\n=== Ringkasan untuk satu proses preferensi manual ===")
    print("- Output LLM dibatasi maksimal 600 token (summary) + 400 token (rerank) jika rerank jalan.")
    print("- Token INPUT nyata bergantung panjang kutipan review di database (summary tidak memotong quote).")
    print("- Angka di atas memakai contoh sintetis; jalankan ulang setelah pip install transformers jika perlu.")


if __name__ == "__main__":
    main()

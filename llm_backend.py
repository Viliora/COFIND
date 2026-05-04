"""
Backend LLM terpadu: Hugging Face InferenceClient (API) atau Transformers lokal.

Lingkungan:
  HF_LLM_BACKEND=inference|transformers
    - inference: pakai InferenceClient (perlu HF_API_TOKEN), perilaku lama.
    - transformers: muat model lokal dengan library transformers (perlu torch).
    - default: inference jika HF_API_TOKEN ada, selain itu transformers.

  HF_MODEL              — id model (default: meta-llama/Llama-3.1-8B-Instruct, gated: huggingface-cli login)
  HF_KEYWORD_MODEL      — opsional model terpisah untuk keyword (bisa berat jika beda id)
  HF_API_TOKEN          — token HF (wajib untuk model gated saat from_pretrained)
  HF_TRANSFORMERS_DEVICE — cuda | cpu | auto (default: auto)
  HF_TRANSFORMERS_MAX_INPUT_TOKENS — anggaran panjang konteks efektif (prompt + cadangan
    untuk generasi), default 131072 agar selaras jendela panjang Llama 3.1; dipotong otomatis
    ke max_position_embeddings model jika lebih kecil.
  HF_TRANSFORMERS_GENERATION_RESERVE — cadangan token di luar prompt (default: 512).
"""
from __future__ import annotations

import os
import threading
from typing import Any, Dict, List, Optional

try:
    import torch
except ImportError:
    torch = None  # type: ignore

HF_API_TOKEN = os.getenv("HF_API_TOKEN")
HF_MODEL = os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct").strip()
HF_KEYWORD_MODEL = os.getenv("HF_KEYWORD_MODEL", HF_MODEL).strip()

_backend = os.getenv("HF_LLM_BACKEND", "").strip().lower()
if _backend not in ("", "inference", "transformers"):
    print(f"[LLM] HF_LLM_BACKEND tidak dikenal '{_backend}', pakai auto.")
    _backend = ""

if _backend == "":
    _backend = "inference" if HF_API_TOKEN else "transformers"

LLM_BACKEND = _backend

hf_client = None
if _backend == "inference":
    if HF_API_TOKEN:
        try:
            from huggingface_hub import InferenceClient

            try:
                hf_client = InferenceClient(provider="featherless-ai", api_key=HF_API_TOKEN)
                print("[INFO] LLM: InferenceClient (Featherless AI)")
            except Exception as e:
                print(f"[WARNING] Featherless init gagal: {e}, fallback default HF")
                hf_client = InferenceClient(api_key=HF_API_TOKEN)
                print("[INFO] LLM: InferenceClient (default)")
        except Exception as e:
            print(f"[WARNING] InferenceClient gagal: {e}")
            hf_client = None
    else:
        print("[WARNING] HF_LLM_BACKEND=inference tetapi HF_API_TOKEN kosong.")
else:
    print("[INFO] LLM: mode Transformers lokal (HF_LLM_BACKEND=transformers atau tanpa token)")

_local_lock = threading.Lock()
_local_tokenizer = None
_local_model = None
_local_model_id: Optional[str] = None

# Default jendela konteks besar (Llama 3.1 / model long-context); turunkan via env jika VRAM terbatas.
_DEFAULT_CONTEXT_WINDOW = 131072


def _prompt_truncation_limit(model, max_new_tokens: int) -> int:
    """
    Jumlah token maksimum untuk prompt setelah tokenisasi (truncation=True).
    Tidak melebihi konfigurasi model dan menyisakan ruang untuk max_new_tokens + cadangan.
    """
    reserve = int(os.getenv("HF_TRANSFORMERS_GENERATION_RESERVE", "512"))
    reserve = max(reserve, max_new_tokens + 128)
    target = int(os.getenv("HF_TRANSFORMERS_MAX_INPUT_TOKENS", str(_DEFAULT_CONTEXT_WINDOW)))
    cfg = getattr(model, "config", None)
    if cfg is not None:
        hard = getattr(cfg, "max_position_embeddings", None)
        if hard is not None:
            target = min(target, int(hard))
    return max(256, target - reserve)


def _pick_device() -> str:
    pref = os.getenv("HF_TRANSFORMERS_DEVICE", "auto").strip().lower()
    cuda_ok = torch is not None and torch.cuda.is_available()
    if pref == "cuda":
        return "cuda" if cuda_ok else "cpu"
    if pref == "cpu":
        return "cpu"
    return "cuda" if cuda_ok else "cpu"


def _auth_token_optional():
    return HF_API_TOKEN if HF_API_TOKEN else None


def _ensure_local(model_id: str) -> None:
    global _local_tokenizer, _local_model, _local_model_id
    if torch is None:
        raise RuntimeError("Paket torch tidak terpasang. pip install torch")
    from transformers import AutoModelForCausalLM, AutoTokenizer

    with _local_lock:
        if _local_model is not None and _local_model_id == model_id:
            return
        if _local_model is not None:
            del _local_model
            _local_model = None
            _local_tokenizer = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        device = _pick_device()
        dtype = torch.bfloat16 if device == "cuda" else torch.float32
        tok_kw = {"token": _auth_token_optional()}
        print(f"[LLM] Memuat {model_id} (device={device}, dtype={dtype}) …")
        _local_tokenizer = AutoTokenizer.from_pretrained(model_id, **tok_kw)
        if _local_tokenizer.pad_token_id is None:
            _local_tokenizer.pad_token_id = _local_tokenizer.eos_token_id

        load_kw: Dict[str, Any] = {
            "token": _auth_token_optional(),
            "torch_dtype": dtype,
            "low_cpu_mem_usage": True,
        }
        if device == "cuda":
            load_kw["device_map"] = "auto"
        model = AutoModelForCausalLM.from_pretrained(model_id, **load_kw)
        if device == "cpu":
            model = model.to("cpu")
        model.eval()
        _local_model = model
        _local_model_id = model_id
        print("[LLM] Model Transformers siap.")
        if "instruct" not in model_id.lower():
            print(
                "[LLM] Catatan: id model tidak mengandung 'Instruct'. "
                "Untuk chat & ekstraksi keyword terstruktur, disarankan "
                "HF_MODEL=meta-llama/Llama-3.1-8B-Instruct (atau setara)."
            )


def llm_is_available() -> bool:
    if _backend == "inference":
        return hf_client is not None
    try:
        import transformers  # noqa: F401
    except ImportError:
        return False
    return torch is not None


def llm_text_generation(
    prompt: str,
    *,
    model: Optional[str] = None,
    max_new_tokens: int = 256,
    min_new_tokens: int = 0,
    temperature: float = 0.2,
    top_p: float = 1.0,
    return_full_text: bool = False,
) -> str:
    """Kompatibel dengan InferenceClient.text_generation (return_full_text=False → hanya teks baru)."""
    model_id = (model or HF_MODEL).strip()
    if _backend == "inference":
        if hf_client is None:
            raise RuntimeError("InferenceClient tidak terkonfigurasi (HF_API_TOKEN?)")
        return hf_client.text_generation(
            prompt,
            model=model_id,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            return_full_text=return_full_text,
        )

    import torch

    _ensure_local(model_id)
    assert _local_tokenizer is not None and _local_model is not None

    max_in = _prompt_truncation_limit(_local_model, max_new_tokens)

    enc = _local_tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=max_in,
    )
    dev = next(_local_model.parameters()).device
    enc = {k: v.to(dev) for k, v in enc.items()}

    gen_kw: Dict[str, Any] = {
        "max_new_tokens": max_new_tokens,
        "pad_token_id": _local_tokenizer.eos_token_id,
    }
    if min_new_tokens > 0:
        gen_kw["min_new_tokens"] = min_new_tokens
    if temperature and temperature > 0:
        gen_kw["do_sample"] = True
        gen_kw["temperature"] = float(temperature)
        if top_p and top_p < 1.0:
            gen_kw["top_p"] = float(top_p)
    else:
        gen_kw["do_sample"] = False

    with torch.inference_mode():
        out = _local_model.generate(**enc, **gen_kw)
    in_len = enc["input_ids"].shape[1]
    new_tokens = out[0][in_len:]
    text = _local_tokenizer.decode(new_tokens, skip_special_tokens=True)
    if return_full_text:
        return prompt + text
    return text


def llm_chat_completions_create(
    *,
    model: Optional[str] = None,
    messages: List[Dict[str, str]],
    max_tokens: int = 512,
    min_tokens: int = 0,
    temperature: float = 0.7,
    top_p: float = 0.9,
) -> str:
    """Mengembalikan isi assistant (satu string), setara response.choices[0].message.content."""
    model_id = (model or HF_MODEL).strip()
    if _backend == "inference":
        if hf_client is None:
            raise RuntimeError("InferenceClient tidak terkonfigurasi")
        resp = hf_client.chat.completions.create(
            model=model_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
        )
        return (resp.choices[0].message.content or "").strip()

    _ensure_local(model_id)
    assert _local_tokenizer is not None

    tok = _local_tokenizer
    if getattr(tok, "chat_template", None):
        prompt = tok.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
    else:
        lines = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            lines.append(f"{role.upper()}:\n{content}\n")
        lines.append("ASSISTANT:\n")
        prompt = "\n".join(lines)

    return llm_text_generation(
        prompt,
        model=model_id,
        max_new_tokens=max_tokens,
        min_new_tokens=min_tokens,
        temperature=temperature,
        top_p=top_p,
        return_full_text=False,
    ).strip()

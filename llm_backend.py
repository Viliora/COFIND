"""
Backend LLM via OpenAI-compatible Hugging Face Router.

Lingkungan:
  HF_MODEL — id model router (default: meta-llama/Llama-3.1-8B-Instruct:novita)
  HF_API_TOKEN / HF_TOKEN — token Hugging Face
  HF_LLM_TIMEOUT_SECONDS — timeout request HTTP ke router (default: 60)
  HF_LLM_MAX_NEW_TOKENS_CAP — batas output text generation (default: 384)
  HF_LLM_MAX_CHAT_TOKENS_CAP — batas output chat completion (default: 900)
  HF_LLM_DEFAULT_TEMPERATURE — default temperature (default: 0.2)
  HF_LLM_DEFAULT_TOP_P — default top_p (default: 0.9)
  HF_LLM_DEFAULT_REPETITION_PENALTY — default repetition penalty (default: 1.1)
  HF_LLM_MAX_RETRIES — retry maksimum per request (default: 1)
  HF_LLM_BACKOFF_FACTOR — backoff factor retry (default: 0.8)
"""
from __future__ import annotations

import os
import time
from typing import Dict, List, Optional

HF_API_TOKEN = (os.getenv("HF_API_TOKEN") or os.getenv("HF_TOKEN") or "").strip()
HF_MODEL = os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct:novita").strip()
LLM_BACKEND = "hf_router_openai"

_MAX_NEW_TOKENS_CAP = int(os.getenv("HF_LLM_MAX_NEW_TOKENS_CAP", "384"))
_MAX_CHAT_TOKENS_CAP = int(os.getenv("HF_LLM_MAX_CHAT_TOKENS_CAP", "900"))
_DEFAULT_TEMPERATURE = float(os.getenv("HF_LLM_DEFAULT_TEMPERATURE", "0.2"))
_DEFAULT_TOP_P = float(os.getenv("HF_LLM_DEFAULT_TOP_P", "0.9"))
_DEFAULT_REPETITION_PENALTY = float(os.getenv("HF_LLM_DEFAULT_REPETITION_PENALTY", "1.1"))
_MAX_RETRIES = max(0, int(os.getenv("HF_LLM_MAX_RETRIES", "1")))
_BACKOFF_FACTOR = float(os.getenv("HF_LLM_BACKOFF_FACTOR", "0.8"))
# Satu percobaan yang dibiarkan selesai lebih berguna daripada dua percobaan yang
# sama-sama dipotong di tengah: prompt ringkasan besar dan retry mengulang dari nol.
_TIMEOUT_SECONDS = float(os.getenv("HF_LLM_TIMEOUT_SECONDS", "60"))

hf_client = None
if HF_API_TOKEN:
    try:
        from openai import OpenAI
        hf_client = OpenAI(
            base_url="https://router.huggingface.co/v1",
            api_key=HF_API_TOKEN,
            timeout=_TIMEOUT_SECONDS,
        )
        print(f"[INFO] LLM: OpenAI-compatible HF Router (timeout={_TIMEOUT_SECONDS}s)")
    except Exception as e:
        print(f"[WARNING] OpenAI client init gagal: {e}")
        hf_client = None
else:
    print("[WARNING] HF_API_TOKEN/HF_TOKEN kosong. Backend HF Router tidak aktif.")


def _clamp_int(value: int, *, min_value: int, max_value: int) -> int:
    return max(min_value, min(max_value, int(value)))


def _normalize_temperature(value: float) -> float:
    return max(0.0, min(1.5, float(value)))


def _normalize_top_p(value: float) -> float:
    return max(0.1, min(1.0, float(value)))


def _normalize_repetition_penalty(value: float) -> float:
    return max(1.0, min(2.0, float(value)))


def _call_with_retry(func, *args, **kwargs):
    last_err = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return func(*args, **kwargs)
        except Exception as err:
            last_err = err
            if attempt >= _MAX_RETRIES:
                break
            sleep_s = max(0.0, _BACKOFF_FACTOR * (2 ** attempt))
            time.sleep(sleep_s)
    raise last_err  # type: ignore[misc]


def llm_is_available() -> bool:
    return hf_client is not None


def llm_text_generation(
    prompt: str,
    *,
    model: Optional[str] = None,
    max_new_tokens: int = 256,
    min_new_tokens: int = 0,
    temperature: float = _DEFAULT_TEMPERATURE,
    top_p: float = _DEFAULT_TOP_P,
    repetition_penalty: float = _DEFAULT_REPETITION_PENALTY,
    return_full_text: bool = False,
) -> str:
    if hf_client is None:
        raise RuntimeError("HF Router client tidak terkonfigurasi (HF_API_TOKEN/HF_TOKEN?)")
    model_id = (model or HF_MODEL).strip()
    max_new_tokens = _clamp_int(max_new_tokens, min_value=16, max_value=max(32, _MAX_NEW_TOKENS_CAP))
    _ = _clamp_int(min_new_tokens, min_value=0, max_value=max_new_tokens)
    temperature = _normalize_temperature(temperature)
    top_p = _normalize_top_p(top_p)
    _ = _normalize_repetition_penalty(repetition_penalty)
    resp = _call_with_retry(
        hf_client.chat.completions.create,
        model=model_id,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_new_tokens,
        temperature=temperature,
        top_p=top_p,
    )
    content = ((resp.choices or [{}])[0].message.content or "").strip()
    return (prompt + content) if return_full_text else content


def llm_chat_completions_create(
    *,
    model: Optional[str] = None,
    messages: List[Dict[str, str]],
    max_tokens: int = 512,
    min_tokens: int = 0,
    temperature: float = _DEFAULT_TEMPERATURE,
    top_p: float = _DEFAULT_TOP_P,
    repetition_penalty: float = _DEFAULT_REPETITION_PENALTY,
) -> str:
    if hf_client is None:
        raise RuntimeError("HF Router client tidak terkonfigurasi (HF_API_TOKEN/HF_TOKEN?)")
    model_id = (model or HF_MODEL).strip()
    max_tokens = _clamp_int(max_tokens, min_value=16, max_value=max(32, _MAX_CHAT_TOKENS_CAP))
    _ = _clamp_int(min_tokens, min_value=0, max_value=max_tokens)
    temperature = _normalize_temperature(temperature)
    top_p = _normalize_top_p(top_p)
    _ = _normalize_repetition_penalty(repetition_penalty)
    resp = _call_with_retry(
        hf_client.chat.completions.create,
        model=model_id,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
    )
    return ((resp.choices or [{}])[0].message.content or "").strip()

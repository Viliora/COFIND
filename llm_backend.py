"""
Backend LLM: Google AI Studio Gemini (utama) + Hugging Face Router / Llama (fallback).

Lingkungan Gemini (Google AI Studio):
  GEMINI_API_KEY — API key dari AI Studio
  GEMINI_MODEL — default gemini-3.8-flash
  GEMINI_PROJECT_ID — opsional (logging / dokumentasi)

Lingkungan HF (fallback Llama via Router):
  HF_MODEL, HF_API_TOKEN / HF_TOKEN, HF_LLM_* (retries, token caps)
  COFIND_LLM_GEMINI_FALLBACK — true/false, default true (aktifkan fallback ke HF bila Gemini gagal)

Alur chat: coba Gemini dulu; jika gagal (quota, 429, dll.) dan fallback aktif + HF token ada,
panggil HF Router (Llama). Jika keduanya gagal, exception ke pemanggil (fallback deterministik).
"""
from __future__ import annotations

import contextvars
import os
import re
import time
from dataclasses import asdict, dataclass
from time import time as monotonic_time
from typing import Dict, List, Literal, Optional, Tuple

from logging_config import get_logger

logger = get_logger('llm')

HF_API_TOKEN = (os.getenv("HF_API_TOKEN") or os.getenv("HF_TOKEN") or "").strip()
HF_MODEL = os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct:novita").strip()

GEMINI_API_KEY = (
    os.getenv("GEMINI_API_KEY")
    or os.getenv("GOOGLE_AI_STUDIO_API_KEY")
    or ""
).strip()
GEMINI_MODEL = (os.getenv("GEMINI_MODEL") or "gemini-3.8-flash").strip()
GEMINI_PROJECT_ID = (os.getenv("GEMINI_PROJECT_ID") or "").strip()
_GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"

_MAX_NEW_TOKENS_CAP = int(os.getenv("HF_LLM_MAX_NEW_TOKENS_CAP", "384"))
_MAX_CHAT_TOKENS_CAP = int(os.getenv("HF_LLM_MAX_CHAT_TOKENS_CAP", "900"))
_DEFAULT_TEMPERATURE = float(os.getenv("HF_LLM_DEFAULT_TEMPERATURE", "0.2"))
_DEFAULT_TOP_P = float(os.getenv("HF_LLM_DEFAULT_TOP_P", "0.9"))
_DEFAULT_REPETITION_PENALTY = float(os.getenv("HF_LLM_DEFAULT_REPETITION_PENALTY", "1.1"))
_MAX_RETRIES = max(0, int(os.getenv("HF_LLM_MAX_RETRIES", "1")))
_BACKOFF_FACTOR = float(os.getenv("HF_LLM_BACKOFF_FACTOR", "0.8"))
# Model Gemini "thinking" menghitung token penalaran ke max_tokens; 1024 sering habis
# sebelum JSON summary selesai (finish_reason=length, completion ~35 token).
GEMINI_SUMMARY_MAX_TOKENS = int(os.getenv("GEMINI_SUMMARY_MAX_TOKENS", "2048"))
# Berlaku untuk semua panggilan Gemini (intent, rerank, sentimen, summary): tanpa ini
# token penalaran menghabiskan max_tokens dan JSON terpotong. Kosongkan untuk mematikan.
GEMINI_REASONING_EFFORT = (
    os.getenv("GEMINI_REASONING_EFFORT", "low") or ""
).strip().lower()
_GEMINI_SUMMARY_STAGES = ("summary", "summary_retry", "summary_json_repair")
_gemini_reasoning_effort_unsupported = False

_last_llm_provider: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "last_llm_provider", default=None,
)
_last_llm_model: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "last_llm_model", default=None,
)
_last_finish_reason: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "last_finish_reason", default=None,
)


class LlmRunRouteOfflineError(RuntimeError):
    """LLM sengaja dimatikan untuk run rekomendasi ini (probe gagal)."""


@dataclass(frozen=True)
class LlmRunRoute:
    mode: Literal["hf", "gemini", "off"]
    reason: str
    probed_at: float
    hf_error_snippet: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


_llm_run_route: contextvars.ContextVar[Optional[LlmRunRoute]] = contextvars.ContextVar(
    "llm_run_route", default=None,
)
_llm_fallback_warned: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "llm_fallback_warned", default=False,
)


def _env_flag(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


COFIND_LLM_GEMINI_FALLBACK = _env_flag("COFIND_LLM_GEMINI_FALLBACK", True)
COFIND_LLM_PROBE_RECOMMEND = _env_flag("COFIND_LLM_PROBE_RECOMMEND", True)

hf_client = None
gemini_client = None

if HF_API_TOKEN:
    try:
        from openai import OpenAI

        hf_client = OpenAI(
            base_url="https://router.huggingface.co/v1",
            api_key=HF_API_TOKEN,
            timeout=None,
        )
        logger.info("LLM fallback HF Router (tanpa batas timeout klien)")
    except Exception as e:
        logger.warning(f"HF OpenAI client init gagal: {e}")
        hf_client = None
else:
    logger.warning("HF_API_TOKEN/HF_TOKEN kosong — HF Router tidak aktif.")

if GEMINI_API_KEY:
    try:
        from openai import OpenAI

        gemini_client = OpenAI(
            base_url=_GEMINI_OPENAI_BASE,
            api_key=GEMINI_API_KEY,
            timeout=None,
        )
        logger.info(
            f"LLM primary: Google AI Studio ({GEMINI_MODEL}"
            f"{', project=' + GEMINI_PROJECT_ID if GEMINI_PROJECT_ID else ''})"
        )
    except Exception as e:
        logger.warning(f"Gemini OpenAI client init gagal: {e}")
        gemini_client = None
elif COFIND_LLM_GEMINI_FALLBACK:
    logger.info("GEMINI_API_KEY kosong — primary Gemini nonaktif.")

if gemini_client and hf_client and COFIND_LLM_GEMINI_FALLBACK:
    LLM_BACKEND = "gemini_openai+hf_fallback"
elif gemini_client:
    LLM_BACKEND = "gemini_openai"
elif hf_client:
    LLM_BACKEND = "hf_router_openai"
else:
    LLM_BACKEND = "none"


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


def _error_code(err: Exception) -> Optional[int]:
    code = getattr(err, "status_code", None)
    if isinstance(code, int):
        return code
    code = getattr(err, "code", None)
    if isinstance(code, int):
        return code
    match = re.search(r"Error code:\s*(\d{3})", str(err))
    if match:
        return int(match.group(1))
    return None


def _retryable_provider_error(err: Exception) -> bool:
    code = _error_code(err)
    if code in (401, 402, 403, 429, 500, 502, 503, 504):
        return True
    text = str(err).lower()
    markers = (
        "credit",
        "quota",
        "billing",
        "rate limit",
        "insufficient",
        "exceeded",
        "unauthorized",
        "permission",
    )
    return any(m in text for m in markers)


def _should_try_hf_after_gemini_error(err: Exception) -> bool:
    if not COFIND_LLM_GEMINI_FALLBACK or hf_client is None:
        return False
    return _retryable_provider_error(err)


def _should_try_gemini_after_hf_error(err: Exception) -> bool:
    if not COFIND_LLM_GEMINI_FALLBACK or gemini_client is None:
        return False
    return _retryable_provider_error(err)


def llm_is_available() -> bool:
    return hf_client is not None or gemini_client is not None


def begin_llm_run_route() -> contextvars.Token:
    _llm_fallback_warned.set(False)
    return _llm_run_route.set(None)


def reset_llm_run_route(token: contextvars.Token) -> None:
    _llm_run_route.reset(token)


def get_llm_run_route() -> Optional[LlmRunRoute]:
    return _llm_run_route.get()


def set_llm_run_route(route: LlmRunRoute) -> None:
    _llm_run_route.set(route)


def _warn_llm_fallback_once(*, from_provider: str, to_provider: str, err: Exception) -> None:
    if _llm_fallback_warned.get():
        return
    _llm_fallback_warned.set(True)
    logger.warning(
        f"LLM {from_provider} gagal ({str(err)[:160]}), "
        f"mencoba fallback {to_provider}..."
    )


def _probe_provider_once(provider: str, model_id: str) -> Tuple[bool, Optional[str]]:
    """Satu chat minimal untuk cek kredit/akses provider."""
    messages = [{"role": "user", "content": "."}]
    try:
        _create_chat_completion(
            provider=provider,
            model_id=model_id,
            messages=messages,
            max_tokens=1,
            temperature=0.0,
            top_p=0.9,
            usage_stage="llm_probe",
        )
        return True, None
    except Exception as err:
        return False, str(err)[:200]


def probe_llm_for_recommendation_run() -> LlmRunRoute:
    """
    Probe sekali per run rekomendasi; set context route untuk anti-spam fallback.
    """
    now = monotonic_time()
    if not llm_is_available():
        route = LlmRunRoute(
            mode="off",
            reason="no_client_configured",
            probed_at=now,
        )
        set_llm_run_route(route)
        return route

    if not COFIND_LLM_PROBE_RECOMMEND:
        if gemini_client is not None:
            mode: Literal["hf", "gemini", "off"] = "gemini"
        elif hf_client is not None:
            mode = "hf"
        else:
            mode = "off"
        route = LlmRunRoute(
            mode=mode,
            reason="probe_disabled_config_only",
            probed_at=now,
        )
        set_llm_run_route(route)
        return route

    if gemini_client is not None:
        ok, gem_err = _probe_provider_once("gemini", GEMINI_MODEL)
        if ok:
            route = LlmRunRoute(mode="gemini", reason="gemini_probe_ok", probed_at=now)
            set_llm_run_route(route)
            return route
        gem_snippet = gem_err or "gemini_probe_failed"
        if (
            hf_client is not None
            and COFIND_LLM_GEMINI_FALLBACK
            and _should_try_hf_after_gemini_error(Exception(gem_snippet))
        ):
            ok_h, hf_err = _probe_provider_once("hf", HF_MODEL)
            if ok_h:
                route = LlmRunRoute(
                    mode="hf",
                    reason="gemini_probe_failed_use_hf",
                    probed_at=now,
                    hf_error_snippet=gem_snippet,
                )
                set_llm_run_route(route)
                return route
            route = LlmRunRoute(
                mode="off",
                reason="gemini_and_hf_probe_failed",
                probed_at=now,
                hf_error_snippet=gem_snippet or hf_err,
            )
            set_llm_run_route(route)
            return route
        route = LlmRunRoute(
            mode="off",
            reason="gemini_probe_failed_no_fallback",
            probed_at=now,
            hf_error_snippet=gem_snippet,
        )
        set_llm_run_route(route)
        return route

    if hf_client is not None:
        ok, hf_err = _probe_provider_once("hf", HF_MODEL)
        if ok:
            route = LlmRunRoute(mode="hf", reason="hf_probe_ok", probed_at=now)
            set_llm_run_route(route)
            return route
        route = LlmRunRoute(
            mode="off",
            reason="hf_probe_failed",
            probed_at=now,
            hf_error_snippet=hf_err,
        )
        set_llm_run_route(route)
        return route

    route = LlmRunRoute(mode="off", reason="no_client_configured", probed_at=now)
    set_llm_run_route(route)
    return route


def get_last_llm_provider() -> Tuple[Optional[str], Optional[str]]:
    """Provider dan model id dari panggilan chat terakhir di context request/thread ini."""
    return _last_llm_provider.get(), _last_llm_model.get()


def get_last_llm_finish_reason() -> Optional[str]:
    """finish_reason dari panggilan chat terakhir (stop, length, dll.)."""
    return _last_finish_reason.get()


def _record_last_llm_call(provider: str, model_id: str) -> None:
    _last_llm_provider.set(provider)
    _last_llm_model.set(model_id)


def _effective_max_tokens(
    max_tokens: int,
    *,
    provider: str,
    usage_stage: Optional[str],
) -> int:
    stage = str(usage_stage or "").strip().lower()
    if provider == "gemini" and stage in _GEMINI_SUMMARY_STAGES:
        return _clamp_int(
            GEMINI_SUMMARY_MAX_TOKENS,
            min_value=max_tokens,
            max_value=max(32, _MAX_CHAT_TOKENS_CAP),
        )
    return max_tokens


def llm_provider_summary() -> Dict[str, object]:
    return {
        "backend": LLM_BACKEND,
        "hf_configured": hf_client is not None,
        "gemini_configured": gemini_client is not None,
        "hf_fallback_enabled": COFIND_LLM_GEMINI_FALLBACK,
        "primary_provider": "gemini" if gemini_client else ("hf" if hf_client else None),
        "hf_model": HF_MODEL if hf_client else None,
        "gemini_model": GEMINI_MODEL if gemini_client else None,
        "gemini_project_id": GEMINI_PROJECT_ID or None,
        "recommend_probe_enabled": COFIND_LLM_PROBE_RECOMMEND,
        "recommend_probe_hint": (
            "Run route (hf|gemini|off) hanya di-set selama pipeline rekomendasi "
            "via probe_llm_for_recommendation_run(); GET status tidak mem-probe."
        ),
    }


def finish_reason_from_chat_response(resp: object) -> Optional[str]:
    choices = getattr(resp, "choices", None) or []
    if not choices:
        return None
    choice = choices[0]
    reason = getattr(choice, "finish_reason", None) or getattr(choice, "finishReason", None)
    return str(reason).strip() if reason else None


def usage_from_chat_response(resp: object) -> Optional[Dict[str, int]]:
    usage = getattr(resp, 'usage', None)
    if usage is None:
        return None
    prompt = int(getattr(usage, 'prompt_tokens', 0) or 0)
    completion = int(getattr(usage, 'completion_tokens', 0) or 0)
    total = int(getattr(usage, 'total_tokens', 0) or 0)
    if total <= 0:
        total = prompt + completion
    if prompt <= 0 and completion <= 0 and total <= 0:
        return None
    return {
        'prompt_tokens': prompt,
        'completion_tokens': completion,
        'total_tokens': total,
    }


def _create_chat_completion(
    *,
    provider: str,
    model_id: str,
    messages: List[Dict[str, str]],
    max_tokens: int,
    temperature: float,
    top_p: float,
    usage_stage: Optional[str] = None,
    response_format: Optional[Dict[str, object]] = None,
):
    client = hf_client if provider == "hf" else gemini_client
    if client is None:
        raise RuntimeError(f"Client {provider} tidak terkonfigurasi")
    global _gemini_reasoning_effort_unsupported
    max_tokens = _effective_max_tokens(
        max_tokens, provider=provider, usage_stage=usage_stage,
    )
    call_kwargs = {
        "model": model_id,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
    }
    if response_format is not None:
        call_kwargs["response_format"] = response_format
    if (
        provider == "gemini"
        and GEMINI_REASONING_EFFORT
        and not _gemini_reasoning_effort_unsupported
    ):
        try:
            return _call_with_retry(
                client.chat.completions.create,
                reasoning_effort=GEMINI_REASONING_EFFORT,
                **call_kwargs,
            )
        except Exception as err:
            if _error_code(err) != 400:
                raise
            _gemini_reasoning_effort_unsupported = True
            logger.warning(
                f"Gemini menolak reasoning_effort={GEMINI_REASONING_EFFORT!r} "
                f"({str(err)[:160]}); lanjut tanpa parameter itu."
            )
    return _call_with_retry(client.chat.completions.create, **call_kwargs)


def _ordered_chat_providers(
    *,
    prefer_provider: Optional[Literal["hf", "gemini"]],
) -> List[Literal["hf", "gemini"]]:
    route = get_llm_run_route()
    if route is not None and route.mode == "off":
        return []

    if prefer_provider == "gemini" and gemini_client is not None:
        return ["gemini"]
    if prefer_provider == "hf" and hf_client is not None:
        return ["hf"]

    if route is not None and route.mode == "gemini" and gemini_client is not None:
        order: List[Literal["hf", "gemini"]] = ["gemini"]
        if hf_client is not None and COFIND_LLM_GEMINI_FALLBACK:
            order.append("hf")
        return order
    if route is not None and route.mode == "hf" and hf_client is not None:
        return ["hf"]

    order = []
    if gemini_client is not None:
        order.append("gemini")
    if hf_client is not None and COFIND_LLM_GEMINI_FALLBACK:
        order.append("hf")
    elif hf_client is not None and not gemini_client:
        order = ["hf"]
    return order


def _should_fallback_after_error(
    failed_provider: Literal["hf", "gemini"],
    err: Exception,
) -> bool:
    if failed_provider == "gemini":
        return _should_try_hf_after_gemini_error(err)
    return _should_try_gemini_after_hf_error(err)


def _chat_with_fallback(
    *,
    hf_model: Optional[str],
    messages: List[Dict[str, str]],
    max_tokens: int,
    temperature: float,
    top_p: float,
    usage_stage: Optional[str],
    prefer_provider: Optional[Literal["hf", "gemini"]] = None,
    response_format: Optional[Dict[str, object]] = None,
) -> Tuple[str, Optional[Dict[str, int]], str, str]:
    """
    Return (content, usage, provider_used, model_id_used).
    provider_used: 'hf' | 'gemini' — Gemini utama, HF fallback.
    """
    route = get_llm_run_route()
    if route is not None and route.mode == "off":
        raise LlmRunRouteOfflineError(route.reason or "llm_off")

    providers = _ordered_chat_providers(prefer_provider=prefer_provider)
    if not providers:
        raise RuntimeError(
            "Tidak ada backend LLM (set GEMINI_API_KEY dan/atau HF_API_TOKEN)"
        )

    last_err: Optional[Exception] = None
    for idx, provider in enumerate(providers):
        model_id = GEMINI_MODEL if provider == "gemini" else (hf_model or HF_MODEL).strip()
        try:
            resp = _create_chat_completion(
                provider=provider,
                model_id=model_id,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                usage_stage=usage_stage,
                response_format=response_format,
            )
            usage = usage_from_chat_response(resp)
            stage = usage_stage or "llm_chat"
            if usage is not None:
                try:
                    from pipeline_telemetry import push_llm_usage

                    if idx > 0:
                        fallback_tag = "hf_fallback" if provider == "hf" else "gemini_fallback"
                        telemetry_stage = f"{stage}:{fallback_tag}"
                    else:
                        telemetry_stage = stage
                    push_llm_usage(
                        stage=telemetry_stage,
                        model=model_id,
                        **usage,
                    )
                except Exception:
                    pass
            content = ((resp.choices or [{}])[0].message.content or "").strip()
            _last_finish_reason.set(finish_reason_from_chat_response(resp))
            _record_last_llm_call(provider, model_id)
            return content, usage, provider, model_id
        except Exception as err:
            last_err = err
            if response_format is not None:
                raise
            has_next = idx < len(providers) - 1
            if has_next and _should_fallback_after_error(provider, err):
                _warn_llm_fallback_once(
                    from_provider=provider,
                    to_provider=providers[idx + 1],
                    err=err,
                )
                continue
            raise

    if last_err is not None:
        raise last_err
    raise RuntimeError(
        "Tidak ada backend LLM (set GEMINI_API_KEY dan/atau HF_API_TOKEN)"
    )


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
    max_new_tokens = _clamp_int(max_new_tokens, min_value=16, max_value=max(32, _MAX_NEW_TOKENS_CAP))
    _ = _clamp_int(min_new_tokens, min_value=0, max_value=max_new_tokens)
    temperature = _normalize_temperature(temperature)
    top_p = _normalize_top_p(top_p)
    _ = _normalize_repetition_penalty(repetition_penalty)
    content, _usage, _prov, _mid = _chat_with_fallback(
        hf_model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_new_tokens,
        temperature=temperature,
        top_p=top_p,
        usage_stage="text_generation",
    )
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
    usage_stage: Optional[str] = None,
    prefer_provider: Optional[Literal["hf", "gemini"]] = None,
    response_format: Optional[Dict[str, object]] = None,
) -> str:
    content, _usage = llm_chat_completions_create_with_usage(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        min_tokens=min_tokens,
        temperature=temperature,
        top_p=top_p,
        repetition_penalty=repetition_penalty,
        usage_stage=usage_stage,
        prefer_provider=prefer_provider,
        response_format=response_format,
    )
    return content


def llm_chat_completions_create_with_usage(
    *,
    model: Optional[str] = None,
    messages: List[Dict[str, str]],
    max_tokens: int = 512,
    min_tokens: int = 0,
    temperature: float = _DEFAULT_TEMPERATURE,
    top_p: float = _DEFAULT_TOP_P,
    repetition_penalty: float = _DEFAULT_REPETITION_PENALTY,
    usage_stage: Optional[str] = None,
    prefer_provider: Optional[Literal["hf", "gemini"]] = None,
    response_format: Optional[Dict[str, object]] = None,
) -> Tuple[str, Optional[Dict[str, int]]]:
    max_tokens = _clamp_int(max_tokens, min_value=16, max_value=max(32, _MAX_CHAT_TOKENS_CAP))
    _ = _clamp_int(min_tokens, min_value=0, max_value=max_tokens)
    temperature = _normalize_temperature(temperature)
    top_p = _normalize_top_p(top_p)
    _ = _normalize_repetition_penalty(repetition_penalty)
    content, usage, provider, model_used = _chat_with_fallback(
        hf_model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        usage_stage=usage_stage,
        prefer_provider=prefer_provider,
        response_format=response_format,
    )
    if provider == "hf" and usage_stage:
        logger.debug(f"LLM via HF fallback stage={usage_stage} model={model_used}")
    return content, usage

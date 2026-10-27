"""LLM / embedding judge RAGAS via Gemini (kredensial sama dengan llm_backend)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Tuple

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


def _load_project_env() -> None:
    load_dotenv(ROOT / ".env")


def gemini_api_key() -> str:
    return (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_AI_STUDIO_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or ""
    ).strip()


def ragas_gemini_model() -> str:
    return (
        os.getenv("COFIND_RAGAS_GEMINI_MODEL")
        or os.getenv("GEMINI_MODEL")
        or "gemini-2.0-flash"
    ).strip()


def ragas_embedding_model() -> str:
    return (
        os.getenv("COFIND_RAGAS_EMBEDDING_MODEL")
        or "gemini-embedding-001"
    ).strip()


def assert_gemini_configured() -> None:
    if not gemini_api_key():
        raise RuntimeError(
            "GEMINI_API_KEY (atau GOOGLE_AI_STUDIO_API_KEY) wajib untuk eval RAGAS. "
            "Isi di .env — lihat .env.example."
        )


def build_ragas_llm(**kwargs: Any):
    """Instructor LLM RAGAS (provider google, SDK google-genai)."""
    assert_gemini_configured()
    from google import genai
    from ragas.llms import llm_factory

    client = genai.Client(api_key=gemini_api_key())
    model = ragas_gemini_model()
    llm_kwargs = {"temperature": 0, **kwargs}
    return llm_factory(model, provider="google", client=client, **llm_kwargs)


def build_ragas_embeddings(**kwargs: Any):
    """Embedding Google untuk AnswerRelevancy (antarmuka LangChain embed_query)."""
    assert_gemini_configured()
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    from ragas.embeddings.base import LangchainEmbeddingsWrapper

    model = ragas_embedding_model()
    lc = GoogleGenerativeAIEmbeddings(
        model=model,
        google_api_key=gemini_api_key(),
        **kwargs,
    )
    return LangchainEmbeddingsWrapper(lc)


def judge_info() -> Tuple[str, str]:
    return ragas_gemini_model(), ragas_embedding_model()

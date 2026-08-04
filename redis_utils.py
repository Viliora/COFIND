"""
Helper koneksi Redis untuk Cofind (lokal / Upstash).

Upstash CLI sering memberi URL redis:// bersama flag --tls.
Klien Python (redis-py, Celery/Kombu) membutuhkan skema rediss:// untuk TLS.
"""
from __future__ import annotations

import os
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse


def get_redis_url(default: str = "redis://127.0.0.1:6379/0") -> str:
    return normalize_redis_url(os.getenv("REDIS_URL", default))


def normalize_redis_url(url: str, *, default: str = "redis://127.0.0.1:6379/0") -> str:
    raw = (url or "").strip()
    if not raw:
        return default

    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    scheme = (parsed.scheme or "redis").lower()

    # Upstash selalu TLS; paksa rediss:// bila masih redis://.
    if host.endswith("upstash.io") and scheme == "redis":
        parsed = parsed._replace(scheme="rediss")
        return urlunparse(parsed)

    return raw


def redis_from_url(url: Optional[str] = None, **kwargs: Any):
    """Buat client redis-py dari REDIS_URL (sudah dinormalisasi)."""
    import redis

    redis_url = normalize_redis_url(url or get_redis_url())
    return redis.Redis.from_url(redis_url, **kwargs)


def ping_redis(timeout: float = 2.0) -> bool:
    client = redis_from_url(socket_connect_timeout=timeout, socket_timeout=timeout)
    try:
        return bool(client.ping())
    finally:
        try:
            client.close()
        except Exception:
            pass

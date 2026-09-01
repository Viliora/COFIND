"""
Cache persisten untuk hasil komputasi mahal pada pipeline semantik:
vektor embedding kalimat dan verdict sentimen dari LLM.

Tiga lapis, dicoba berurutan:
  1. memori proses (paling cepat, hilang saat restart)
  2. Redis bila REDIS_URL tersedia (dipakai bersama antar worker/proses)
  3. file JSON di folder cache/ (fallback ketika Redis tidak ada)

Nilai yang disimpan harus JSON-serializable. Vektor float disimpan sebagai
float16 base64 (lihat encode_vector/decode_vector) supaya ukurannya seperempat
dari representasi list float biasa.

Env:
  COFIND_VECTOR_CACHE            aktifkan cache persisten (default: true)
  COFIND_VECTOR_CACHE_REDIS      izinkan lapis Redis (default: true)
  COFIND_VECTOR_CACHE_TTL_DAYS   umur entri, hari (default: 30)
  COFIND_VECTOR_CACHE_MAX        batas entri per namespace di file (default: 200000)
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence

from cache_paths import CACHE_DIR
from logging_config import get_logger

logger = get_logger('cache')


def _env_flag(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or '').strip().lower()
    if not raw:
        return default
    return raw in ('1', 'true', 'yes', 'on')


def _env_int(name: str, default: int, *, min_value: int, max_value: int) -> int:
    raw = (os.getenv(name) or '').strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(min_value, min(max_value, value))


def cache_enabled() -> bool:
    return _env_flag('COFIND_VECTOR_CACHE', True)


def redis_layer_enabled() -> bool:
    return _env_flag('COFIND_VECTOR_CACHE_REDIS', True)


def cache_ttl_seconds() -> int:
    return _env_int('COFIND_VECTOR_CACHE_TTL_DAYS', 30, min_value=1, max_value=365) * 86400


def cache_max_entries() -> int:
    return _env_int('COFIND_VECTOR_CACHE_MAX', 200_000, min_value=1000, max_value=5_000_000)


def digest_key(*parts: object) -> str:
    """Kunci cache stabil dan pendek dari beberapa bagian teks."""
    blob = '\u241f'.join(str(p or '') for p in parts)
    return hashlib.sha1(blob.encode('utf-8')).hexdigest()


def encode_vector(vector: Sequence[float]) -> str:
    """Vektor float -> base64 float16 (hemat ~4x dibanding JSON list float)."""
    import numpy as np

    arr = np.asarray(vector, dtype=np.float16)
    return base64.b64encode(arr.tobytes()).decode('ascii')


def decode_vector(payload: object):
    """Balikan dari encode_vector; None bila payload rusak."""
    import numpy as np

    try:
        raw = base64.b64decode(str(payload or ''), validate=True)
    except Exception:
        return None
    if not raw:
        return None
    try:
        return np.frombuffer(raw, dtype=np.float16).astype(np.float32)
    except Exception:
        return None


class PersistentCache:
    """Cache key-value sederhana dengan lapis memori + Redis + file."""

    def __init__(self, namespace: str):
        self.namespace = str(namespace or 'default').strip() or 'default'
        self._memory: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._file_entries: Optional[Dict[str, dict]] = None
        self._file_dirty = False
        self._redis = None
        self._redis_checked = False
        self.hits_memory = 0
        self.hits_redis = 0
        self.hits_file = 0
        self.misses = 0

    # ---------------------------------------------------------------- Redis

    def _redis_client(self):
        if not (cache_enabled() and redis_layer_enabled()):
            return None
        if self._redis_checked:
            return self._redis
        self._redis_checked = True
        if not (os.getenv('REDIS_URL') or '').strip():
            self._redis = None
            return None
        try:
            from redis_utils import redis_from_url

            client = redis_from_url(socket_connect_timeout=2.0, socket_timeout=2.0)
            client.ping()
            self._redis = client
        except Exception as err:
            logger.warning(f"Redis tidak dipakai: {str(err)[:120]}")
            self._redis = None
        return self._redis

    def _redis_key(self, key: str) -> str:
        return f"cofind:vcache:{self.namespace}:{key}"

    # ----------------------------------------------------------------- File

    @property
    def _file_path(self) -> str:
        return os.path.join(CACHE_DIR, f'{self.namespace}.json')

    def _load_file_entries(self) -> Dict[str, dict]:
        if self._file_entries is not None:
            return self._file_entries
        entries: Dict[str, dict] = {}
        if cache_enabled() and os.path.exists(self._file_path):
            try:
                with open(self._file_path, 'r', encoding='utf-8') as handle:
                    loaded = json.load(handle)
                if isinstance(loaded, dict):
                    entries = {k: v for k, v in loaded.items() if isinstance(v, dict)}
            except Exception as err:
                logger.warning(f"Gagal load {self._file_path}: {str(err)[:120]}")
        self._file_entries = entries
        return entries

    def _is_fresh(self, entry: dict) -> bool:
        try:
            stored_at = float(entry.get('t') or 0)
        except (TypeError, ValueError):
            return False
        return (time.time() - stored_at) <= cache_ttl_seconds()

    # ------------------------------------------------------------------ API

    def get_many(self, keys: Iterable[str]) -> Dict[str, Any]:
        keys = [k for k in keys if k]
        if not keys:
            return {}
        found: Dict[str, Any] = {}
        pending: List[str] = []

        with self._lock:
            for key in keys:
                if key in self._memory:
                    found[key] = self._memory[key]
                    self.hits_memory += 1
                else:
                    pending.append(key)

        if not pending or not cache_enabled():
            self.misses += len(pending)
            return found

        client = self._redis_client()
        if client is not None:
            try:
                raw_values = client.mget([self._redis_key(k) for k in pending])
            except Exception:
                raw_values = None
            if raw_values:
                still_pending = []
                for key, raw in zip(pending, raw_values):
                    if raw is None:
                        still_pending.append(key)
                        continue
                    try:
                        value = json.loads(raw)
                    except Exception:
                        still_pending.append(key)
                        continue
                    found[key] = value
                    self.hits_redis += 1
                    with self._lock:
                        self._memory[key] = value
                pending = still_pending

        if pending:
            entries = self._load_file_entries()
            still_pending = []
            for key in pending:
                entry = entries.get(key)
                if not isinstance(entry, dict) or not self._is_fresh(entry):
                    still_pending.append(key)
                    continue
                value = entry.get('v')
                found[key] = value
                self.hits_file += 1
                with self._lock:
                    self._memory[key] = value
            pending = still_pending

        self.misses += len(pending)
        return found

    def get(self, key: str) -> Any:
        return self.get_many([key]).get(key)

    def set_many(self, mapping: Dict[str, Any]) -> None:
        if not mapping:
            return
        with self._lock:
            self._memory.update(mapping)
        if not cache_enabled():
            return

        client = self._redis_client()
        if client is not None:
            ttl = cache_ttl_seconds()
            try:
                pipe = client.pipeline()
                for key, value in mapping.items():
                    pipe.setex(self._redis_key(key), ttl, json.dumps(value, ensure_ascii=False))
                pipe.execute()
                return
            except Exception as err:
                logger.debug(f"Tulis Redis gagal, jatuh ke lapis file: {str(err)[:120]}")

        with self._lock:
            entries = self._load_file_entries()
            now = time.time()
            for key, value in mapping.items():
                entries[key] = {'t': now, 'v': value}
            self._file_dirty = True

    def set(self, key: str, value: Any) -> None:
        self.set_many({key: value})

    def flush(self) -> None:
        """Tulis lapis file ke disk bila ada perubahan (no-op untuk Redis)."""
        if not (self._file_dirty and cache_enabled()):
            return
        with self._lock:
            entries = dict(self._load_file_entries())
            limit = cache_max_entries()
            if len(entries) > limit:
                ordered = sorted(entries.items(), key=lambda item: float(item[1].get('t') or 0), reverse=True)
                entries = dict(ordered[:limit])
                self._file_entries = entries
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            tmp_path = f'{self._file_path}.tmp'
            with open(tmp_path, 'w', encoding='utf-8') as handle:
                json.dump(entries, handle, ensure_ascii=False)
            os.replace(tmp_path, self._file_path)
            self._file_dirty = False
        except Exception as err:
            logger.warning(f"Gagal simpan {self._file_path}: {str(err)[:120]}")

    def stats(self) -> Dict[str, int]:
        return {
            'memory_hits': self.hits_memory,
            'redis_hits': self.hits_redis,
            'file_hits': self.hits_file,
            'misses': self.misses,
            'memory_entries': len(self._memory),
        }

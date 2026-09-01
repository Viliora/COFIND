"""Konfigurasi logging terpusat untuk backend Cofind.

Semua modul backend memakai logger anak dari root logger `cofind`, sehingga
level bisa diatur per area tanpa mengubah kode:

    COFIND_LOG_LEVEL=INFO           level default seluruh logger cofind
    COFIND_LOG_LEVEL_RECOMMEND=DEBUG  override untuk area tertentu
                                   (suffix = nama child logger, huruf besar)

Area yang dipakai saat ini: recommend, review, admin, startup, metric, cache.
Log detail per-toko pada pipeline rekomendasi memakai level DEBUG, jadi
produksi cukup di INFO tanpa kehilangan langkah-langkah utama pipeline.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional

ROOT_LOGGER_NAME = 'cofind'

DEFAULT_FORMAT = '%(asctime)s %(levelname)-8s [%(name)s] %(message)s'
DEFAULT_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

_configured = False


def _level_from_env(name: str, default: int) -> int:
    raw = (os.getenv(name) or '').strip().upper()
    if not raw:
        return default
    resolved = logging.getLevelName(raw)
    return resolved if isinstance(resolved, int) else default


def configure_logging(force: bool = False) -> logging.Logger:
    """Siapkan handler stdout untuk logger `cofind` (idempoten)."""
    global _configured
    root = logging.getLogger(ROOT_LOGGER_NAME)
    if _configured and not force:
        return root

    root.setLevel(_level_from_env('COFIND_LOG_LEVEL', logging.INFO))
    # Log Cofind punya handler sendiri agar tidak bergantung pada konfigurasi
    # root logging milik Flask/Gunicorn yang bisa berbeda antar environment.
    root.propagate = False
    for handler in list(root.handlers):
        root.removeHandler(handler)

    # Konsol Windows default cp1252: pesan yang memuat karakter non-ASCII (mis.
    # tanda panah atau kutipan tipografis dari review) membuat handler melempar
    # UnicodeEncodeError dan log hilang. errors='replace' menjaga log tetap tertulis.
    stream = sys.stdout
    try:
        stream.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError, OSError):
        pass

    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter(DEFAULT_FORMAT, datefmt=DEFAULT_DATE_FORMAT))
    root.addHandler(handler)

    _configured = True
    return root


def get_logger(area: Optional[str] = None) -> logging.Logger:
    """Logger untuk satu area, mis. get_logger('recommend') -> `cofind.recommend`."""
    configure_logging()
    if not area:
        return logging.getLogger(ROOT_LOGGER_NAME)

    logger = logging.getLogger(f'{ROOT_LOGGER_NAME}.{area}')
    override = _level_from_env(f'COFIND_LOG_LEVEL_{area.upper()}', 0)
    if override:
        logger.setLevel(override)
    return logger

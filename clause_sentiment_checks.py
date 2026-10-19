"""Smoke check konfigurasi sentimen klausa (Fase 2b)."""

from __future__ import annotations

import os


def main() -> int:
    # Pastikan env kosong memakai default baru (aktif).
    for key in (
        'COFIND_LLM_CLAUSE_SENTIMENT',
        'COFIND_CLAUSE_SENTIMENT_DEDUP',
    ):
        os.environ.pop(key, None)

    from llm_clause_sentiment import (
        clause_dedup_enabled,
        clause_sentiment_enabled,
        sentiment_config,
    )

    assert clause_sentiment_enabled() is True, 'default clause sentiment should be enabled'
    assert clause_dedup_enabled() is True, 'default dedup should be enabled'
    cfg = sentiment_config()
    assert cfg.get('enabled') is True
    assert cfg.get('dedup_enabled') is True
    print('clause_sentiment_checks: OK', cfg)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

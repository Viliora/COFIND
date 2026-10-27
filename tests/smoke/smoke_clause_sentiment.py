"""Smoke test manual: verifikasi sentimen klausa ABSA + cascade _quote_is_caveat."""

import os

try:  # dijalankan sebagai skrip
    import _bootstrap  # noqa: F401
except ModuleNotFoundError:  # dijalankan sebagai modul (python -m tests.smoke...)
    from tests.smoke import _bootstrap  # noqa: F401

os.environ.setdefault('COFIND_SEMANTIC_GATE', 'false')

import app
import llm_clause_sentiment as lcs

QUOTES = [
    'saya merasa lambat sekali untuk semua wifi yang tersedia di sini',
    'Kursinya bagus tapi ngga nyaman, wifinya bagus',
    'Wifi kencang banget, cocok buat kerja online seharian',
    'Kopinya enak dan baristanya ramah sekali',
]

print('ABSA enabled:', lcs.clause_sentiment_enabled())
verdicts, telemetry = lcs.classify_quotes(
    QUOTES,
    preference_line='Wifi kencang',
)
print('telemetry:', telemetry)
for quote in QUOTES:
    verdict = verdicts.get(lcs.quote_key(quote))
    print(f"\n- {quote}\n  verdict: {verdict}")

token = app._set_clause_verdicts(verdicts)
try:
    pref_kws = app._preference_keywords_for_evidence(['wifi_kencang'])
    for quote in QUOTES:
        print(f"caveat={app._quote_is_caveat(quote, pref_kws)!s:5} | {quote}")
finally:
    app._reset_clause_verdicts(token)

lcs.flush_cache()
print('\ncache stats:', lcs.cache_stats())

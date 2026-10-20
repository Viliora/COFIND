"""Smoke test manual: pipeline rekomendasi end-to-end dengan preferensi dua lapis."""

import os
import sys

try:  # dijalankan sebagai skrip
    import _bootstrap  # noqa: F401
except ModuleNotFoundError:  # dijalankan sebagai modul (python -m tests.smoke...)
    from tests.smoke import _bootstrap  # noqa: F401

# Isolasi tahap baru: ekspansi keyword & rerank LLM dimatikan agar yang diuji
# adalah gerbang makna + verifikasi sentimen klausa.
os.environ.setdefault('COFIND_LLM_KEYWORD_EXPANSION', 'false')
os.environ.setdefault('COFIND_LLM_RERANK', 'false')
os.environ.setdefault('COFIND_MODAL_QUOTE_LLM', 'false')

import app

prefs = sys.argv[1:] or ['belajar', 'wifi_kencang']
print(f'>>> preferensi: {prefs}')

auth_user = {'id': 1}
with app.app.test_request_context():
    for kind, payload in app._recommendation_pipeline_events(prefs, auth_user):
        if kind == 'progress':
            print(f"[progress] {payload.get('stage'):18} {payload.get('percent')}% {payload.get('label')}")
            continue
        body, status = payload
        print(f'\n[result] status={status} pesan={body.get("message")}')
        pipeline = body.get('llm_pipeline') or {}
        print('semantic_gate   :', pipeline.get('semantic_gate'))
        print('clause_sentiment:', pipeline.get('clause_sentiment'))
        print('rerank          :', pipeline.get('rerank'))
        for rec in body.get('recommendations') or []:
            evidence = rec.get('supporting_evidence') or {}
            coverage = rec.get('pill_coverage') or {}
            print(
                f"\n  - {rec.get('name')} skor={rec.get('score')} "
                f"final={rec.get('final_score')} cakupan={coverage.get('coverage_ratio')}"
            )
            print(
                f"      terbukti={coverage.get('covered_labels')} "
                f"belum={coverage.get('uncovered_labels')}"
            )
            for quote in evidence.get('modal_display_quotes') or []:
                source = quote.get('match_source') or 'keyword'
                print(
                    f"      [bukti/{source}/{quote.get('sentiment_source', 'heuristik')}]"
                    f" ({quote.get('reason')}) {str(quote.get('quote'))[:100]}"
                )
            for quote in evidence.get('modal_caveat_quotes') or []:
                print(
                    f"      [catatan/{quote.get('sentiment_source', 'heuristik')}]"
                    f" {str(quote.get('quote'))[:100]}"
                )

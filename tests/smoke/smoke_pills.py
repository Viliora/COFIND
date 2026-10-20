"""Smoke test manual: sinkronisasi pill lapis 2 antara frontend dan backend."""

import os
import re

try:  # dijalankan sebagai skrip
    from _bootstrap import repo_path
except ModuleNotFoundError:  # dijalankan sebagai modul (python -m tests.smoke...)
    from tests.smoke._bootstrap import repo_path

os.environ.setdefault('COFIND_SEMANTIC_GATE', 'false')

import app

PILLS_JS = repo_path('frontend-cofind', 'src', 'constants', 'reviewPills.js')
with open(PILLS_JS, encoding='utf-8') as handle:
    SRC = handle.read()
head, _, tail = SRC.partition('FACILITY_ATTRIBUTE_GROUPS')
context_values = set(re.findall(r"value: '([a-z0-9_ ]+)'", head))
attribute_values = set(re.findall(r"value: '([a-z0-9_ ]+)'", tail))
backend_attributes = set(app.FACILITY_ATTRIBUTE_PILLS)

print('atribut frontend:', len(attribute_values), 'backend:', len(backend_attributes))
print('frontend tanpa mapping backend:', sorted(attribute_values - backend_attributes))
print('backend tanpa opsi frontend  :', sorted(backend_attributes - attribute_values))
print('semua punya label   :', all(p in app.PILL_LABELS for p in backend_attributes))
print('semua punya mapping :', all(p in app.PILL_MAPPING for p in backend_attributes))
print('pill konteks lapis 1:', sorted(context_values))

payload = {
    'preferences': ['belajar', 'wifi_kencang', 'pill_ngawur'],
    'attributes': ['musholla', 'ruangan_ac', 'musholla'],
}
with app.app.test_request_context(json=payload):
    combined = app._read_recommendation_preferences()
print('prefs gabungan:', combined)
print('valid di PILL_MAPPING:', [p for p in combined if p in app.PILL_MAPPING])
print('seed keywords (12):', app._seed_search_keywords(['belajar', 'wifi_kencang', 'musholla'])[:12])
print('frasa acuan wifi   :', app._semantic_reference_terms(['wifi_kencang'])[:8])
print('kutipan verifikasi :', app._candidate_quotes_for_sentiment({
    'review_quotes': [{'quote': 'Wifinya lambat sekali di sini, tapi kopinya enak'}],
    'semantic_matches': [{'quote': 'Koneksinya ngebut buat ngerjain tugas online'}],
}))

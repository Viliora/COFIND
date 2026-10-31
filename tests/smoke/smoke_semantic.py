"""Smoke test manual: model embedding, gerbang makna, dan cache vektor."""

try:  # dijalankan sebagai skrip
    import _bootstrap  # noqa: F401
except ModuleNotFoundError:  # dijalankan sebagai modul (python -m tests.smoke...)
    from tests.smoke import _bootstrap  # noqa: F401

from dotenv import load_dotenv

load_dotenv()

from sentence_transformers import SentenceTransformer

import semantic_match

model = SentenceTransformer(semantic_match.model_name())
sentences = [
    'The weather is lovely today.',
    "It's so sunny outside!",
    'He drove to the stadium.',
]
embeddings = model.encode(sentences)
similarities = model.similarity(embeddings, embeddings)
print('shape similarity contoh resmi:', similarities.shape)

reviews = [
    {'text': 'Koneksinya ngebut, enak banget buat ngerjain tugas online.', 'rating': 5},
    {'text': 'Sayangnya jaringannya lelet sekali di jam sibuk.', 'rating': 2},
    {'text': 'Kopinya mantap dan pelayanannya ramah.', 'rating': 5},
    {'text': 'Ada ruang sholat kecil di belakang, bersih.', 'rating': 4},
]

for terms, label in (
    (['wifi kencang', 'wifi cepat', 'internet lancar'], 'wifi_kencang'),
    (['ada musholla', 'tempat sholat', 'ruang sholat'], 'musholla'),
):
    matches, telemetry = semantic_match.match_reviews(reviews, terms)
    print(f'\n[{label}] telemetry={telemetry}')
    for idx, info in sorted(matches.items()):
        print(f"  review#{idx} score={info['score']} term='{info['term']}' clause='{info['clause']}'")

semantic_match.flush_cache()
print('\ncache stats:', semantic_match.cache_stats())

matches2, telemetry2 = semantic_match.match_reviews(reviews, ['wifi kencang', 'wifi cepat', 'internet lancar'])
print('run kedua (harus dari cache):', telemetry2, semantic_match.cache_stats())

"""Kalibrasi ambang cosine similarity gerbang makna dengan contoh berlabel.

Label = apakah klausa MEMBAHAS aspek itu (topikal), bukan apakah nadanya positif.
Penilaian nada tetap tugas LLM di tahap berikutnya.
"""

try:  # dijalankan sebagai skrip
    import _bootstrap  # noqa: F401
except ModuleNotFoundError:  # dijalankan sebagai modul (python -m tests.smoke...)
    from tests.smoke import _bootstrap  # noqa: F401

from dotenv import load_dotenv

load_dotenv()

import numpy as np

import semantic_match as sm

ASPECTS = {
    'wifi_kencang': ['wifi kencang', 'wifi', 'wifi cepat', 'wifi lancar', 'internet cepat', 'koneksi stabil'],
    'musholla': ['ada musholla', 'musholla', 'tempat sholat', 'ruang sholat'],
    'ruangan_ac': ['ruangan sejuk', 'ac', 'adem', 'sejuk', 'ruangan dingin'],
}

# (aspek, klausa, relevan_topikal)
CASES = [
    ('wifi_kencang', 'koneksinya ngebut', True),
    ('wifi_kencang', 'internetnya lancar jaya', True),
    ('wifi_kencang', 'jaringannya lelet sekali di jam sibuk', True),
    ('wifi_kencang', 'sinyal susah masuk di lantai dua', True),
    ('wifi_kencang', 'kopinya enak dan baristanya ramah', False),
    ('wifi_kencang', 'parkirannya sempit sekali', False),
    ('wifi_kencang', 'tempatnya instagramable banget', False),
    ('wifi_kencang', 'harganya masih masuk kantong mahasiswa', False),
    ('musholla', 'ada ruang sholat kecil di belakang', True),
    ('musholla', 'tempat ibadahnya bersih dan wangi', True),
    ('musholla', 'toiletnya lumayan bersih', False),
    ('musholla', 'menunya banyak pilihan', False),
    ('ruangan_ac', 'di dalam adem banget', True),
    ('ruangan_ac', 'ruangannya panas dan pengap', True),
    ('ruangan_ac', 'kursinya empuk dan luas', False),
    ('ruangan_ac', 'wifi lancar buat meeting online', False),
]

if not sm.model_available():
    raise SystemExit('model embedding tidak tersedia')

rows = []
for aspect, clause, expected in CASES:
    terms, matrix = sm.reference_embeddings(ASPECTS[aspect])
    vectors = sm.embed_texts([clause])
    vector = np.asarray(list(vectors.values())[0], dtype=np.float32).reshape(1, -1)
    scores = sm.similarity_matrix(vector, matrix).reshape(-1)
    best = int(np.argmax(scores))
    rows.append((aspect, clause, expected, float(scores[best]), terms[best]))

print(f"{'aspek':14} {'harusnya':9} {'skor':6} klausa -> frasa acuan terdekat")
for aspect, clause, expected, score, term in sorted(rows, key=lambda r: -r[3]):
    print(f"{aspect:14} {str(expected):9} {score:.3f}  {clause[:44]:46} -> {term}")

print('\nambang   presisi  recall  benar/total')
for threshold in (0.40, 0.45, 0.50, 0.55, 0.60, 0.65):
    tp = sum(1 for a, c, e, s, t in rows if e and s >= threshold)
    fp = sum(1 for a, c, e, s, t in rows if not e and s >= threshold)
    fn = sum(1 for a, c, e, s, t in rows if e and s < threshold)
    tn = sum(1 for a, c, e, s, t in rows if not e and s < threshold)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    print(f"{threshold:.2f}     {precision:.2f}     {recall:.2f}    {tp + tn}/{len(rows)}")

sm.flush_cache()

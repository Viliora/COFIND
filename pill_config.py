"""Konfigurasi pill aktivitas dan fasilitas.

Peran field (tests/test_pill_retrieval_text.py):
  - label            teks UI/prompt saja; TIDAK masuk token sparse maupun teks dense.
  - dense_query      teks query dense: satu konsep, gaya bahasa ulasan, <=150 char, tanpa
                     negasi (embedding menangani negasi dengan buruk).
  - definition /     konteks prompt LLM rerank/summary (+ kunci cache rerank).
    negative_scope   negative_scope sengaja tidak pernah masuk dense.
  - facility_fields  hanya pill atribut; penguat lemah (metadata prior). Bukti utama tetap
                     kecocokan preferensi dengan ulasan. Key yang belum ada di data
                     (mis. smoking_area) dibiarkan agar terpakai bila data menyusul.

Kebijakan `review_keywords` (ditegakkan tests/test_pill_keyword_curation.py):
- Sparse (BM25) = jangkar leksikal yang lemah ditangkap dense: slang, singkatan, nama
    khas, ejaan informal ("wfc", "mabar", "nugas"). Parafrase/sentimen
    ("tenang banget", "wifi kencang") adalah tugas dense, bukan daftar ini.
- BM25 meratakan frasa jadi unigram, jadi tiap token harus jangkar. Hindari modifier
    ("cepat", "luas", "bersih"), kata fungsi ("untuk", "bisa", "banyak"), dan kata umum
    yang bertabrakan di ulasan nyata ("manis", "teras", "luar", "laptop").
- Jangan menulis varian ejaan yang sudah dilipat slang normalizer (mushola/musola).
- Pill aktivitas: review_keywords + frasa gerbang dari data/lexicon/activity_lexicon.json.
- Maks 8 keyword (aktivitas) / 7 (atribut). Urutkan paling representatif lebih dulu:
    recommendation/helpers.py memakai 8 pertama sebagai frasa acuan semantic gate.
- Tambahan baru hanya dari ulasan nyata (scripts/eval/mine_pill_keyword_candidates.py,
    scripts/eval/pill_keyword_drift_report.py), setelah dikurasi manual.
"""
from __future__ import annotations

PILL_MAPPING = {
    'belajar': {
        'label': 'Belajar',
        'definition': (
            'Aktivitas mandiri atau kelompok kecil seperti membaca buku, mengerjakan tugas, '
            'skripsi, atau belajar ujian yang menuntut suasana kondusif, tenang, dan tidak bising.'
        ),
        'negative_scope': (
            'Bukan tempat nongkrong komunal yang riuh, kafe dengan live music keras, '
            'atau tempat yang hanya cocok untuk mengobrol santai tanpa konsentrasi.'
        ),
        'dense_query': 'enak buat belajar dan nugas, ngerjain tugas kuliah atau skripsi',
        'review_keywords': [],
    },
    'kerja': {
        'label': 'Kerja/WFC',
        'definition': (
            'Aktivitas kerja jarak jauh (work from cafe/remote/WFA), produktif dengan laptop '
            'dalam durasi lama, rapat daring, atau menyelesaikan deadline profesional.'
        ),
        'negative_scope': (
            'Bukan sekadar mampir minum kopi sebentar (grab-and-go), dan bukan kunjungan santai '
            'tanpa niat kerja remote atau menyelesaikan pekerjaan.'
        ),
        'dense_query': 'cocok buat kerja dan wfc, laptopan berjam-jam, kerja remote',
        'review_keywords': [],
    },
    'bermain game': {
        'label': 'Nge-game',
        'definition': (
            'Aktivitas bermain mobile/online game bersama teman (mabar) seperti Mobile Legends, '
            'PUBG, atau turnamen game.'
        ),
        'negative_scope': (
            'Bukan kafe hening/perpustakaan yang melarang obrolan seru, dan bukan tempat yang '
            'membatasi waktu kunjungan singkat.'
        ),
        'dense_query': 'seru buat main game dan mabar bareng teman, main mobile legends atau pubg',
        # review_keywords aktivitas diisi dari activity_lexicon.json saat import.
        'review_keywords': [],
    },
    'meeting_sosialisasi': {
        'label': 'Meeting/Pertemuan',
        'definition': (
            'Pertemuan terencana kelompok seperti rapat kerja formal, diskusi tim/komunitas, '
            'arisan, presentasi bisnis, atau sesi jejaring yang membutuhkan tata ruang meja '
            'yang memadai untuk banyak orang.'
        ),
        'negative_scope': (
            'Bukan nongkrong santai perorangan, dan bukan tempat dengan kapasitas tempat duduk '
            'sangat sempit untuk kelompok.'
        ),
        'dense_query': 'nyaman buat meeting, rapat, atau pertemuan kelompok, mejanya muat banyak orang',
        # Hindari kata longgar seperti "kumpul"/"grup": "berkumpul dengan keluarga"
        # bukan bukti meeting. Hindari frasa berawalan kata fungsi ("untuk rapat"):
        # BM25 meratakannya jadi unigram "untuk"/"buat" yang menyentuh ~70% review.
        'review_keywords': [],
    },
    'keluarga': {
        'label': 'Keluarga',
        'definition': (
            'Kunjungan santai bersama anggota keluarga lintas usia (anak-anak, orang tua) '
            'yang membutuhkan tempat makan dan minum yang aman untuk anak, nyaman, dan ramah keluarga.'
        ),
        'negative_scope': (
            'Bukan area bar/lounge yang tidak ramah anak, dan bukan tempat sempit yang berbahaya '
            'bagi anak kecil dan orang tua.'
        ),
        'dense_query': 'cocok buat bawa keluarga dan anak kecil, ramah anak, ada kursi bayi',
        'review_keywords': [],
    },
    'instagrammable': {
        'label': 'Feeds Hunter',
        'definition': (
            'Kunjungan untuk berswafoto, konten visual, atau menikmati estetika interior dan '
            'arsitektur tempat yang unik, artistik, trendi, dan memiliki pencahayaan menarik.'
        ),
        'negative_scope': (
            'Bukan tempat dengan visual kumuh, pencahayaan gelap/suram tanpa konsep estetik, '
            'atau kafe ruko polos tanpa elemen dekoratif visual.'
        ),
        # Label branding "Feeds Hunter": datang untuk berfoto demi feed media sosial
        # karena tempatnya estetik.
        'dense_query': 'tempatnya estetik, banyak spot foto bagus buat feed instagram dan konten sosmed',
        'review_keywords': [],
    },
    'nongkrong_hangout': {
        'label': 'Nongkrong/Hangout',
        'definition': (
            'Kunjungan santai untuk ngobrol lama, nongkrong atau nongki bersama teman, tanpa '
            'agenda rapat formal, skripsi, atau kerja laptop berjam-jam.'
        ),
        'negative_scope': (
            'Bukan rapat kerja formal atau meeting presentasi, bukan fokus belajar/skripsi, '
            'dan bukan kunjungan keluarga lintas usia dengan anak kecil sebagai fokus utama.'
        ),
        'dense_query': (
            'cocok nongkrong dan nongki santai bareng teman, hangout lama ngobrol sambil ngopi'
        ),
        # "nongki" dilipat slang normalizer ke "nongkrong"; frasa "nongki" tetap di
        'review_keywords': [],
    },
    # --- Preferensi lapis 2: atribut fasilitas ---------------------------------
    # Struktur identik dengan pill aktivitas, jadi seluruh pipeline (BM25,
    # evidence, rerank) otomatis mengenalinya tanpa cabang khusus.
    'ruangan_ac': {
        # Label "Ruangan sejuk": sejuk karena AC maupun alami (adem), bukan hanya AC.
        'dense_query': 'ruangannya sejuk dan adem, ada AC, udaranya segar',
        # "nyaman" ada di semua toko, bukan bukti sejuk.
        'facility_fields': {
            'atmosphere': ['sejuk'],
        },
        'review_keywords': [
            # "dingin" sengaja tidak masuk (juga lewat frasa "ac dingin"): BM25 meratakan
            # frasa jadi unigram, dan "kopi dingin" bukan bukti ruangan sejuk.
            'sejuk', 'adem', 'ac', 'ruangan ac',
        ],
    },
    'suasana_tenang': {
        'dense_query': 'suasananya tenang, sepi, dan kalem, musiknya pelan',
        # "santai" bukan "tenang" (kafe ramai pun bisa santai).
        'facility_fields': {
            'atmosphere': ['tenang'],
        },
        # Tidak memasukkan "tidak berisik"/"nggak ribut": unigram "berisik"/"ribut" akan
        # menarik toko yang ulasannya justru mengeluh berisik.
        'review_keywords': [
            'tenang', 'ketenangan', 'sepi', 'kondusif',
        ],
    },
    'area_outdoor': {
        'dense_query': 'ada area outdoor buat duduk di luar, semi outdoor atau rooftop',
        'facility_fields': {
            'service_options': ['outdoor_seating'],
        },
        # "teras"/"luar"/"taman"/"terbuka" sengaja tidak masuk: ulasan nyata memakai
        # "teras rumah" untuk parkir motor dan "luar biasa" untuk pelayanan.
        'review_keywords': [
            'outdoor', 'semi outdoor', 'rooftop',
        ],
    },
    'smoking_area': {
        'dense_query': 'ada smoking area, boleh merokok di ruangan khusus perokok',
        'facility_fields': {
            'amenities': ['smoking_area'],
        },
        'review_keywords': [
            'smoking area', 'smoking room', 'merokok', 'rokok',
        ],
    },
    'wifi_kencang': {
        'dense_query': 'wifinya kencang dan stabil, internetnya lancar',
        'facility_fields': {
            'amenities': ['wifi', 'free_wifi'],
        },
        # Kualitas ("kencang"/"lancar"/"stabil") sengaja tidak masuk sparse: sebagai unigram
        # ia cocok ke "pelayanan cepat" dsb. Kualitas dinilai dense + evidence.
        'review_keywords': [
            'wifi', 'internet',
        ],
    },
    'banyak_colokan_terminal': {
        # "terminal" hanya di dense: sebagai token sparse bisa cocok ke "dekat terminal" (lokasi).
        'dense_query': 'banyak colokan dan terminal listrik di meja, gampang ngecas laptop dan hp',
        'facility_fields': {
            'popular_for': ['good_for_working_on_laptop'],
        },
        'review_keywords': [
            'colokan', 'stop kontak', 'ngecas', 'charger',
        ],
    },
    'ruang_privat': {
        'dense_query': 'ada ruang privat, vip room, atau ruang meeting tertutup yang bisa dipesan',
        # accepts_reservations = bisa reservasi meja, bukan bukti ruang privat.
        'facility_fields': {
            'offerings': ['private_dining_room'],
        },
        'review_keywords': [
            'ruang privat', 'private room', 'vip room', 'meeting room',
        ],
    },
    'buka_sampai_malam_24_hours': {
        # Label "24 hours": buka 24 jam, bukan sekadar tutup larut.
        'dense_query': 'buka 24 jam nonstop, bisa datang kapan saja termasuk tengah malam',
        'facility_fields': {
            'offerings': ['late_night_food'],
        },
        # Varian "buka 24 jam"/"open 24 hours"/"operasional 24 jam" melipat ke token yang sama.
        # "malam"/"buka" sengaja tidak masuk: terlalu umum ("malam minggu", "buka jam 9").
        'review_keywords': [
            '24 jam', '24 hours', '24/7', 'nonstop',
        ],
    },
    'musholla': {
        'dense_query': 'ada musholla yang bersih buat sholat, tersedia mukena',
        'facility_fields': {
            'amenities': ['musholla', 'prayer_room'],
        },
        # Variasi ejaan (mushola/musola/musolla, sholat/solat) sudah dilipat slang normalizer.
        'review_keywords': [
            'musholla', 'sholat', 'mukena',
        ],
    },
    'parkir_luas': {
        'dense_query': 'parkirannya luas dan lega, gampang parkir motor dan mobil',
        # parking_available / paid_parking_lot hanya berarti "ada parkir", bukan "luas".
        'facility_fields': {
            'parking': ['lots_of_parking', 'plenty_of_parking'],
        },
        # Hanya jangkar "parkir": "luas"/"mudah"/"lega" adalah kualitas (dense + evidence),
        # dan "luas" sebagai unigram cocok ke "areanya luas".
        'review_keywords': [
            'parkir',
        ],
    },
    'toilet_bersih': {
        'dense_query': 'toiletnya bersih, wangi, dan terawat',
        'facility_fields': {
            'amenities': ['toilet', 'gender_neutral_toilet'],
        },
        'review_keywords': [
            'toilet', 'toiletnya', 'wc', 'kamar mandi', 'restroom',
        ],
    },
    'makanan_berat': {
        'dense_query': 'menu lengkap, ada makanan berat seperti nasi atau pasta dan banyak pilihan minuman',
        # Menu lengkap = toko menyajikan makanan (bukan hanya kopi/minuman).
        # Sinyal utama ada di popular_for / dining_options (breakfast|brunch|
        # lunch|dinner), bukan hanya offerings.restaurant.
        'facility_fields': {
            'popular_for': ['breakfast', 'brunch', 'lunch', 'dinner'],
            'dining_options': ['breakfast', 'brunch', 'lunch', 'dinner'],
            'offerings': ['restaurant'],
        },
        # Jangkar hidangan khas saja. "makan malam"/"kenyang"/"menu lengkap" tidak masuk
        # (unigram malam/menu terlalu umum; "kenyang" = sentimen, ranah dense).
        'review_keywords': [
            'makanan berat', 'nasi', 'steak', 'pasta', 'mie ayam', 'rice bowl', 'sarapan',
        ],
    },
    'dessert': {
        'label': 'Dessert',
        'dense_query': 'dessertnya enak, ada kue, cake, cheesecake, brownies, dan pastry',
        'facility_fields': {
            'highlights': ['good_desserts'],
            'dining_options': ['dessert'],
        },
        # "manis" sengaja tidak masuk: ulasan nyata "kopi susunya manis banget" bukan dessert.
        'review_keywords': [
            'dessert', 'cheesecake', 'cake', 'brownies', 'croissant', 'pastry', 'kue',
        ],
    },
}

# Pill lapis 2 dibedakan dari pill aktivitas hanya saat validasi input & pembatasan
# jumlah; sisanya diperlakukan sama oleh pipeline.
# Nilainya harus sama dengan FACILITY_ATTRIBUTE_GROUPS di
# frontend-cofind/src/constants/reviewPills.js.
FACILITY_ATTRIBUTE_PILLS = frozenset({
    'ruangan_ac', 'suasana_tenang', 'area_outdoor', 'smoking_area',
    'wifi_kencang', 'banyak_colokan_terminal', 'ruang_privat',
    'buka_sampai_malam_24_hours', 'musholla', 'parkir_luas', 'toilet_bersih',
    'makanan_berat', 'dessert',
})

# Label lapis 2: fallback jika mapping fasilitas belum punya kunci `label`.
_FACILITY_PILL_LABELS = {
    'ruangan_ac': 'Ruangan sejuk',
    'suasana_tenang': 'Suasana tenang',
    'area_outdoor': 'Outdoor area',
    'smoking_area': 'Smoking area',
    'wifi_kencang': 'Wifi kencang',
    'banyak_colokan_terminal': 'Banyak colokan / terminal',
    'ruang_privat': 'Ruang privat / meeting',
    'buka_sampai_malam_24_hours': '24 hours',
    'musholla': 'Ada musholla',
    'parkir_luas': 'Parkir luas',
    'toilet_bersih': 'Toilet bersih',
    'makanan_berat': 'Menu Lengkap (Makanan & Minuman)',
    'dessert': 'Dessert',
}

PILL_LABELS = {}
for _pill_key, _pill_spec in PILL_MAPPING.items():
    _spec = _pill_spec if isinstance(_pill_spec, dict) else {}
    PILL_LABELS[_pill_key] = (
        str(_spec.get('label') or '').strip()
        or _FACILITY_PILL_LABELS.get(_pill_key)
        or _pill_key
    )
for _pill_key, _pill_label in _FACILITY_PILL_LABELS.items():
    PILL_LABELS.setdefault(_pill_key, _pill_label)

from activity_lexicon import apply_activity_lexicon_to_mapping

apply_activity_lexicon_to_mapping(PILL_MAPPING)


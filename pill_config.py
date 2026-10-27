"""Konfigurasi pill aktivitas dan fasilitas (sumber tunggal backend)."""
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
        'facility_fields': {
            'popular_for': ['good_for_working_on_laptop'],
            'amenities': ['wifi', 'free_wifi'],
            'crowd': ['mahasiswa'],
        },
        'review_keywords': [
            'belajar', 'tugas', 'nugas', 'ngerjain tugas', 'kuliah', 'kampus', 'ujian',
            'skripsi', 'buku', 'baca buku', 'fokus belajar', 'ruang belajar', 'temen belajar',
            'anak kuliahan', 'mahasiswa', 'tugas sekolah',
        ],
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
        'facility_fields': {
            'popular_for': ['good_for_working_on_laptop'],
            'amenities': ['wifi', 'free_wifi'],
        },
        'review_keywords': [
            # 8 teratas juga dipakai sebagai frasa acuan gerbang makna
            # (_semantic_reference_terms), jadi istilah paling representatif
            # untuk "kerja dari kafe" ditaruh di depan.
            'kerja', 'wfc', 'work from cafe', 'laptopan', 'laptop', 'wfh',
            'kerja remote', 'ngantor',
            'zoom', 'meeting online', 'video call', 'webinar', 'produktif',
            'deadline', 'presentasi', 'dokumen', 'ngerjain kerjaan', 'kerjaan kantor',
            'lembur', 'freelance', 'remote working', 'work from anywhere',
            'bisnis', 'kantor',
        ],
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
        'facility_fields': {
            'popular_for': ['good_for_groups'],
        },
        'review_keywords': [
            'main game', 'gaming', 'gamer', 'game', 'ngegame', 'nge-game', 'nge game',
            'mobile legends', 'mobile legend', 'mlbb', 'main ml', 'main ML',
            'pubg', 'valorant', 'free fire', 'main ff', 'honor of kings',
            'mabar', 'ngemabar', 'gas game', 'turnamen', 'push rank', 'ngerank',
            'bermain game', 'mainbareng', 'playstation', 'ps5', 'esport',
        ],
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
        'facility_fields': {
            'popular_for': ['good_for_groups'],
            'crowd': ['berkelompok'],
        },
        # Hindari kata longgar seperti "kumpul"/"grup": "berkumpul dengan keluarga"
        # bukan bukti meeting. Pakai frasa pertemuan/rapat yang lebih spesifik.
        'review_keywords': [
            'meeting', 'rapat', 'diskusi', 'arisan', 'sosialisasi', 'networking',
            'catch up', 'untuk meeting', 'buat rapat', 'untuk rapat',
            'pertemuan bisnis', 'pertemuan kerja', 'meeting kantor',
            'kumpul kerja', 'kumpul kantor', 'kumpul tim',
        ],
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
        'facility_fields': {
            'children': ['good_for_kids', 'kids_menu', 'high_chairs'],
            'popular_for': ['good_for_groups'],
            'crowd': ['keluarga', 'ramah_keluarga', 'berkelompok'],
        },
        'review_keywords': [
            'keluarga', 'family', 'anak-anak', 'ramah keluarga',
            'cocok keluarga', 'bawa anak kecil', 'family friendly',
            'berkumpul bersama', 'kumpul bersama', 'quality time',
            'ramah anak', 'playground', 'area bermain', 'kursi bayi', 'menu anak',
        ],
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
        'facility_fields': {
            'atmosphere': ['trendi', 'artistic'],
        },
        'review_keywords': [
            'instagrammable', 'instagramable', 'instagenic', 'fotogenik',
            'spot foto', 'photo spot', 'banyak spot foto', 'estetik',
        ],
    },
    # --- Preferensi lapis 2: atribut fasilitas ---------------------------------
    # Struktur identik dengan pill aktivitas, jadi seluruh pipeline (BM25,
    # evidence, rerank) otomatis mengenalinya tanpa cabang khusus.
    'ruangan_ac': {
        'facility_fields': {
            'atmosphere': ['nyaman', 'sejuk'],
        },
        'review_keywords': [
            # "dingin"/"adem" sengaja tidak berdiri sendiri: "kopi dingin" / "tempatnya adem"
            # bukan bukti ruangan ber-AC.
            'ac', 'ber ac', 'ruangan ac', 'sejuk', 'indoor ac',
            'ac dingin', 'ruangan dingin', 'ruangan sejuk', 'udara dingin',
        ],
    },
    'suasana_tenang': {
        'facility_fields': {
            'atmosphere': ['tenang', 'santai'],
        },
        'review_keywords': [
            'tenang', 'sepi', 'sunyi', 'hening', 'tidak berisik', 'ga berisik',
            'nggak ribut', 'suasana tenang', 'kondusif', 'damai',
        ],
    },
    'area_outdoor': {
        'facility_fields': {
            'service_options': ['outdoor_seating'],
        },
        'review_keywords': [
            'outdoor', 'area outdoor', 'outdoor seating', 'tempat outdoor',
            'area terbuka', 'tempat terbuka', 'teras outdoor', 'taman outdoor',
            'duduk di luar', 'kursi outdoor', 'al fresco',
            'di luar ruangan', 'lesehan outdoor', 'rooftop', 'open space',
            'taman',
        ],
    },
    'smoking_area': {
        'facility_fields': {
            'amenities': ['smoking_area'],
        },
        'review_keywords': [
            'smoking area', 'area smoking', 'area merokok', 'tempat merokok',
            'bisa merokok', 'boleh merokok', 'ruang merokok', 'smoking room',
            'kawasan merokok',
        ],
    },
    'wifi_kencang': {
        'facility_fields': {
            'amenities': ['wifi', 'free_wifi'],
        },
        'review_keywords': [
            'wifi', 'wifi kencang', 'wifi cepat', 'wifi lancar', 'wifi stabil',
            'internet cepat', 'internet lancar', 'koneksi stabil', 'sinyal kuat',
            'jaringan lancar', 'kecepatan internet',
        ],
    },
    'banyak_colokan_terminal': {
        'facility_fields': {
            'popular_for': ['good_for_working_on_laptop'],
        },
        'review_keywords': [
            'colokan', 'stop kontak', 'terminal listrik', 'banyak colokan',
            'colokan di tiap meja', 'charge laptop', 'ngecas', 'charging',
            'power outlet',
        ],
    },
    'ruang_privat': {
        'facility_fields': {
            'offerings': ['private_dining_room'],
            'planning': ['accepts_reservations'],
        },
        'review_keywords': [
            'ruang privat', 'private room', 'ruang meeting', 'meeting room',
            'ruangan tertutup', 'vip room', 'ruang khusus', 'ruang diskusi',
            'bisa reservasi ruangan',
        ],
    },
    'buka_sampai_malam_24_hours': {
        'facility_fields': {
            'offerings': ['late_night_food'],
        },
        'review_keywords': [
            '24 jam', '24 hours', 'buka 24 jam', 'open 24 hours', 'operasional 24 jam',
            'buka sepanjang hari', 'buka nonstop', '24/7', 'buka 24/7',
            'never close', 'tutup never', 'jam operasional 24 jam',
        ],
    },
    'musholla': {
        'facility_fields': {
            'amenities': ['musholla', 'prayer_room'],
        },
        'review_keywords': [
            'musholla', 'mushola', 'musola', 'tempat sholat', 'tempat solat',
            'ruang sholat', 'bisa sholat', 'ada mukena', 'sajadah',
        ],
    },
    'parkir_luas': {
        'facility_fields': {
            'parking': ['lots_of_parking', 'parking_available', 'paid_parking_lot'],
        },
        'review_keywords': [
            'parkir', 'parkiran', 'parkir luas', 'parkir lega', 'lahan parkir',
            'parkir mudah', 'tempat parkir', 'parkir motor', 'parkir mobil',
        ],
    },
    'toilet_bersih': {
        'facility_fields': {
            'amenities': ['toilet', 'gender_neutral_toilet'],
        },
        'review_keywords': [
            'toilet', 'toilet bersih', 'kamar mandi', 'wc', 'restroom',
            'toiletnya wangi', 'kamar mandi bersih',
        ],
    },
    'makanan_berat': {
        # Menu lengkap = toko menyajikan makanan (bukan hanya kopi/minuman).
        # Sinyal utama ada di popular_for / dining_options (breakfast|brunch|
        # lunch|dinner), bukan hanya offerings.restaurant.
        'facility_fields': {
            'popular_for': ['breakfast', 'brunch', 'lunch', 'dinner'],
            'dining_options': ['breakfast', 'brunch', 'lunch', 'dinner'],
            'offerings': ['restaurant'],
        },
        'review_keywords': [
            'makanan berat', 'menu makanan berat', 'nasi', 'nasi goreng',
            'makan siang', 'makan malam', 'kenyang', 'lauk', 'ayam goreng',
            'steak', 'pasta', 'rice bowl', 'soto', 'bakso', 'mie ayam',
            'menu lengkap', 'bisa makan berat', 'sarapan', 'brunch',
        ],
    },
    'dessert': {
        'label': 'Dessert',
        'facility_fields': {
            'highlights': ['good_desserts'],
            'dining_options': ['dessert'],
        },
        'review_keywords': [
            'dessert', 'cheesecake', 'kue', 'pastry', 'croissant', 'brownies',
            'tiramisu', 'donat', 'waffle', 'pudding', 'es krim', 'manis',
            'hidangan penutup', 'kue basah', 'kue kering',
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


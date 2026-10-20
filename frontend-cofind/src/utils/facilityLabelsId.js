import { FACILITY_TAB_SPECS } from '../config/facilityTabsConfig';

/** Kunci snake_case / istilah Google → label tampilan Bahasa Indonesia */
const EXTRA_FACILITY_LABELS_ID = {
  wheelchair_accessible_entrance: 'Akses kursi roda',
  wheelchair_accessible_restroom: 'Toilet ramah kursi roda',
  wheelchair_accessible_parking: 'Parkir ramah kursi roda',
  wheelchair_accessible_seating: 'Tempat duduk ramah kursi roda',
  curbside_pickup: 'Ambil pesanan di tepi jalan',
  outdoor_seating: 'Tempat duduk luar ruangan',
  reservable: 'Bisa reservasi',
  dine_in: 'Makan di tempat',
  takeaway: 'Bawa pulang',
  delivery: 'Antar pesanan',
  live_music: 'Musik live',
  great_cocktails: 'Koktail andalan',
  vegetarian_options: 'Menu vegetarian',
  serves_alcohol: 'Menyajikan minuman beralkohol',
  good_coffee: 'Kopi enak',
  good_desserts: 'Hidangan penutup enak',
  good_tea_selection: 'Pilihan teh beragam',
  sports: 'Cocok nonton olahraga',
  fast_service: 'Layanan cepat',
  brunch: 'Sarapan akhir pekan',
  dessert: 'Hidangan penutup',
  solo_dining: 'Makan sendiri',
  good_for_working_on_laptop: 'Cocok kerja dengan laptop',
  good_for_kids: 'Ramah anak',
  good_for_groups: 'Cocok berkelompok',
  late_night_food: 'Makanan larut malam',
  private_dining_room: 'Ruang makan privat',
  gender_neutral_toilet: 'Toilet netral gender',
  smoking_area: 'Area merokok',
  prayer_room: 'Ruang sholat',
  kids_menu: 'Menu anak',
  high_chairs: 'Kursi anak',
  accepts_reservations: 'Menerima reservasi',
  requires_reservations: 'Wajib reservasi',
  credit_cards: 'Kartu kredit',
  debit_cards: 'Kartu debit',
  nfc: 'Pembayaran nirsentuh',
  cash_only: 'Tunai saja',
  parking_available: 'Parkir tersedia',
  lots_of_parking: 'Parkir luas',
  paid_parking_lot: 'Parkir berbayar',
  free_parking_lot: 'Parkir gratis',
  valet_parking: 'Parkir dengan layanan jockey',
  casual: 'Santai',
  cozy: 'Nyaman',
  trendy: 'Kekinian',
  quiet: 'Tenang',
  romantic: 'Romantis',
  family_friendly: 'Ramah keluarga',
  good_for_watching_sports: 'Cocok nonton olahraga',
  good_for_dancing: 'Cocok berdansa',
  groups: 'Berkelompok',
  tourists: 'Wisatawan',
  university_students: 'Mahasiswa',
  lgbtq_friendly: 'Ramah LGBTQ+',
  serves_beer: 'Menyajikan bir',
  serves_wine: 'Menyajikan anggur',
  serves_vegetarian_food: 'Menu vegetarian',
  serves_breakfast: 'Sarapan',
  serves_brunch: 'Sarapan akhir pekan',
  serves_lunch: 'Makan siang',
  serves_dinner: 'Makan malam',
  wifi: 'Wi‑Fi',
  free_wifi: 'Wi‑Fi gratis',
  trendi: 'Trendi',
  artistic: 'Bergaya seni',
  nyaman: 'Nyaman',
  sejuk: 'Sejuk',
  tenang: 'Tenang',
  santai: 'Santai',
  kekinian: 'Kekinian',
};

const PHRASE_LABELS_ID = {
  'curbside pickup': 'Ambil pesanan di tepi jalan',
  'outdoor seating': 'Tempat duduk luar ruangan',
  'live music': 'Musik live',
  'great cocktails': 'Koktail andalan',
  'cocktail recommended': 'Koktail andalan',
  'good for kids': 'Ramah anak',
  'good for groups': 'Cocok berkelompok',
  'good for working on laptop': 'Cocok kerja dengan laptop',
  'gender neutral toilet': 'Toilet netral gender',
  'valet parking': 'Parkir dengan layanan jockey',
  'credit cards': 'Kartu kredit',
  'debit cards': 'Kartu debit',
  'cash only': 'Tunai saja',
  'late night food': 'Makanan larut malam',
  'private dining room': 'Ruang makan privat',
  'wheelchair accessible entrance': 'Akses kursi roda',
  'menu vegetarian': 'Menu vegetarian',
};

function buildLookupFromConfig() {
  const map = { ...EXTRA_FACILITY_LABELS_ID };
  FACILITY_TAB_SPECS.forEach((spec) => {
    Object.entries(spec.labelMap || {}).forEach(([key, label]) => {
      if (key && label) map[key] = label;
    });
  });
  return map;
}

const FACILITY_LABEL_LOOKUP = buildLookupFromConfig();

function normalizeFacilityKey(raw) {
  return String(raw || '')
    .trim()
    .toLowerCase()
    .replace(/-/g, '_')
    .replace(/\s+/g, '_');
}

function looksMostlyIndonesian(text) {
  return /[à-ž]|\b(yang|dan|atau|dengan|untuk|tidak|ada|ramah|cocok|area|tempat|ruang|makan|parkir|layanan|menu|toilet|kursi|gratis|tersedia|wajib|menerima|sarapan|siang|malam|anak|keluarga|luar|dalam|sholat|musholla|nirsentuh|tunai|kartu|enak|cepat|vegetarian|alkohol|koktail|musik|reservasi|pembayaran|akses|nyaman|tenang|santai|sejuk|trendi|kekinian|berkelompok|mahasiswa|wisatawan|musholla)\b/i.test(
    text,
  );
}

/** Teks panjang / snippet editorial Google — jangan tampilkan sebagai pill fasilitas. */
export function isLikelyEnglishFacilityText(text) {
  const t = String(text || '').trim();
  if (!t) return false;
  if (looksMostlyIndonesian(t)) return false;
  if (t.length >= 48) return true;
  return /\b(the|and|with|for|this|that|coffee|great|best|located|offers|known|popular|friendly|cozy|comfortable|atmosphere|serves|features|perfect|ideal|spot|place|enjoy|experience|delicious|beautiful|amazing|wonderful)\b/i.test(
    t,
  );
}

/**
 * Ubah kunci/label fasilitas ke Bahasa Indonesia untuk tampilan UI.
 */
export function localizeFacilityLabel(raw, labelMap = {}) {
  const text = String(raw ?? '').trim();
  if (!text) return '';

  const snake = normalizeFacilityKey(text);
  if (labelMap[snake]) return labelMap[snake];
  if (FACILITY_LABEL_LOOKUP[snake]) return FACILITY_LABEL_LOOKUP[snake];

  const phraseKey = text.toLowerCase().replace(/_/g, ' ').replace(/\s+/g, ' ').trim();
  if (PHRASE_LABELS_ID[phraseKey]) return PHRASE_LABELS_ID[phraseKey];

  if (looksMostlyIndonesian(text)) return text;

  const words = phraseKey.split(' ').filter(Boolean);
  if (words.length > 1) {
    const translated = words
      .map((w) => FACILITY_LABEL_LOOKUP[w] || FACILITY_LABEL_LOOKUP[normalizeFacilityKey(w)] || w)
      .join(' ');
    if (translated !== phraseKey) return translated;
  }

  return FACILITY_LABEL_LOOKUP[snake] || text;
}

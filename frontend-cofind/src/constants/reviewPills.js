/** Pill konteks aktivitas di beranda (rekomendasi berbasis review). */
export const CONTEXT_PILL_OPTIONS = [
  {
    label: 'Belajar',
    value: 'belajar',
    desc: 'Suasana tenang dan kondusif untuk membaca buku atau mengerjakan tugas/skripsi.',
  },
  {
    label: 'Kerja/WFC',
    value: 'kerja',
    desc: 'Kebutuhan kerja remote/WFC berdurasi lama, laptopan, dan fokus deadline.',
  },
  {
    label: 'Nge-game',
    value: 'bermain game',
    desc: 'Koneksi stabil untuk mabar game online tanpa pembatasan waktu ketat.',
  },
  {
    label: 'Meeting/Pertemuan',
    value: 'meeting_sosialisasi',
    desc: 'Kapasitas meja kelompok dan ruang yang nyaman untuk diskusi/rapat.',
  },
  {
    label: 'Keluarga',
    value: 'keluarga',
    desc: 'Tempat luas, ramah anak, nyaman untuk keluarga, dan menu variatif.',
  },
  {
    label: 'Feeds Hunter',
    value: 'instagrammable',
    desc: 'Estetika visual, pencahayaan bagus, dan spot foto untuk konten/feeds.',
  },
  {
    label: 'Nongkrong/Hangout',
    value: 'nongkrong_hangout',
    desc: 'Ngobrol lama, nongkrong atau nongki santai bareng teman tanpa agenda formal.',
  },
];

/**
 * Atribut fasilitas (tab Fasilitas). Bisa dipilih sendiri atau bersama aktivitas.
 * Nilai `value` = kunci preferensi di API (sama pentingnya dengan pill aktivitas).
 */
export const FACILITY_ATTRIBUTE_GROUPS = [
  {
    id: 'kenyamanan',
    label: 'Kenyamanan',
    options: [
      { label: 'Ruangan sejuk', value: 'ruangan_ac', icon: '❄️' },
      { label: 'Suasana tenang', value: 'suasana_tenang', icon: '🔇' },
      { label: 'Outdoor area', value: 'area_outdoor', icon: '🌿' },
      { label: 'Smoking area', value: 'smoking_area', icon: '🚬' },
    ],
  },
  {
    id: 'produktivitas',
    label: 'Produktivitas',
    options: [
      { label: 'Wifi kencang', value: 'wifi_kencang', icon: '📶' },
      { label: 'Banyak colokan / terminal', value: 'banyak_colokan_terminal', icon: '🔌' },
      { label: '24 hours', value: 'buka_sampai_malam_24_hours', icon: '🌙' },
    ],
  },
  {
    id: 'fasilitas_umum',
    label: 'Fasilitas umum',
    options: [
      { label: 'Ada musholla', value: 'musholla', icon: '🕌' },
      { label: 'Parkir luas', value: 'parkir_luas', icon: '🅿️' },
      { label: 'Toilet bersih', value: 'toilet_bersih', icon: '🚻' },
    ],
  },
  {
    id: 'menu',
    label: 'Menu',
    options: [
      { label: 'Menu Lengkap (Makanan & Minuman)', value: 'makanan_berat', icon: '🍽️' },
      { label: 'Dessert', value: 'dessert', icon: '🍰' },
    ],
  },
];

export const FACILITY_ATTRIBUTE_OPTIONS = FACILITY_ATTRIBUTE_GROUPS.flatMap(
  (group) => group.options,
);

export const FACILITY_ATTRIBUTE_LABELS = Object.fromEntries(
  FACILITY_ATTRIBUTE_OPTIONS.map((option) => [option.value, option.label]),
);

/** Chip idle — editorial surface, no gradient fills */
const PILL_IDLE =
  'border border-cofind-rule bg-cofind-surface text-cofind-ink shadow-cofind-sm hover:border-cofind-muted hover:bg-cofind-paper';

const PILL_SELECTED_PRIMARY =
  'border border-cofind-primary bg-cofind-primary text-cofind-on-primary shadow-cofind-md';

const PILL_SELECTED_SECONDARY =
  'border border-cofind-secondary bg-cofind-secondary text-cofind-on-secondary shadow-cofind-md';

/**
 * Gaya Tailwind per nilai pill: `idle` vs `selected` (solid tokens, no indigo/violet gradients).
 */
export const CONTEXT_PILL_THEMES = {
  belajar: {
    idle: PILL_IDLE,
    selected: PILL_SELECTED_SECONDARY,
  },
  kerja: {
    idle: PILL_IDLE,
    selected: PILL_SELECTED_PRIMARY,
  },
  'bermain game': {
    idle: PILL_IDLE,
    selected: 'border border-stone-700 bg-stone-700 text-white shadow-cofind-md',
  },
  meeting_sosialisasi: {
    idle: PILL_IDLE,
    selected: 'border border-amber-800 bg-amber-800 text-white shadow-cofind-md',
  },
  keluarga: {
    idle: PILL_IDLE,
    selected: 'border border-rose-800 bg-rose-800 text-white shadow-cofind-md',
  },
  instagrammable: {
    idle: PILL_IDLE,
    selected: PILL_SELECTED_PRIMARY,
  },
  nongkrong_hangout: {
    idle: PILL_IDLE,
    selected: PILL_SELECTED_SECONDARY,
  },
};

export const CONTEXT_PILL_THEME_DEFAULT = {
  idle: PILL_IDLE,
  selected: PILL_SELECTED_PRIMARY,
};

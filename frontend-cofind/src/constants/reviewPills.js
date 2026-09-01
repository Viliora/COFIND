/** Pill konteks aktivitas di beranda (rekomendasi berbasis review). */
export const CONTEXT_PILL_OPTIONS = [
  { label: 'Belajar', value: 'belajar' },
  { label: 'Kerja/WFC', value: 'kerja' },
  { label: 'Nge-game', value: 'bermain game' },
  { label: 'Meeting/Pertemuan', value: 'meeting_sosialisasi' },
  { label: 'Keluarga', value: 'keluarga' },
  { label: 'Instagrammable', value: 'instagrammable' },
];

/**
 * Preferensi lapis 2: atribut fasilitas yang dipilih setelah konteks aktivitas.
 * Nilai `value` dipakai sebagai kunci preferensi tambahan (bukan teks bebas).
 */
export const FACILITY_ATTRIBUTE_GROUPS = [
  {
    id: 'kenyamanan',
    label: 'Kenyamanan',
    options: [
      { label: 'Ruangan sejuk', value: 'ruangan_ac', icon: '❄️' },
      { label: 'Suasana tenang', value: 'suasana_tenang', icon: '🔇' },
      { label: 'Area non-smoking', value: 'area_non_smoking', icon: '🚭' },
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
];

export const FACILITY_ATTRIBUTE_OPTIONS = FACILITY_ATTRIBUTE_GROUPS.flatMap(
  (group) => group.options,
);

export const FACILITY_ATTRIBUTE_LABELS = Object.fromEntries(
  FACILITY_ATTRIBUTE_OPTIONS.map((option) => [option.value, option.label]),
);

/**
 * Gaya Tailwind per nilai pill: `idle` vs `selected`.
 * Tooltip native (atribut title) tidak dipakai di ShopList; bayangan membesar saat hover.
 */
export const CONTEXT_PILL_THEMES = {
  belajar: {
    idle:
      'border-0 bg-gradient-to-br from-sky-200 via-sky-100 to-blue-200 text-sky-950 dark:from-sky-700/55 dark:via-sky-600/40 dark:to-blue-800/55 dark:text-sky-50 shadow-md shadow-sky-500/15 hover:shadow-lg hover:shadow-sky-500/30',
    selected:
      'border-0 bg-gradient-to-r from-sky-500 via-blue-500 to-blue-600 text-white shadow-lg shadow-sky-600/35 dark:shadow-sky-900/60 hover:shadow-xl hover:shadow-sky-600/45 dark:hover:shadow-sky-900/70',
  },
  kerja: {
    idle:
      'border-0 bg-gradient-to-br from-emerald-200 via-emerald-100 to-teal-200 text-emerald-950 dark:from-emerald-700/50 dark:via-emerald-600/40 dark:to-teal-800/55 dark:text-emerald-50 shadow-md shadow-emerald-500/15 hover:shadow-lg hover:shadow-emerald-500/30',
    selected:
      'border-0 bg-gradient-to-r from-emerald-500 via-teal-500 to-teal-600 text-white shadow-lg shadow-emerald-600/35 dark:shadow-emerald-900/60 hover:shadow-xl hover:shadow-emerald-600/45 dark:hover:shadow-emerald-900/70',
  },
  'bermain game': {
    idle:
      'border-0 bg-gradient-to-br from-violet-200 via-violet-100 to-purple-200 text-violet-950 dark:from-violet-700/50 dark:via-violet-600/40 dark:to-purple-800/55 dark:text-violet-50 shadow-md shadow-violet-500/15 hover:shadow-lg hover:shadow-violet-500/30',
    selected:
      'border-0 bg-gradient-to-r from-violet-500 via-purple-500 to-purple-600 text-white shadow-lg shadow-violet-600/35 dark:shadow-violet-900/60 hover:shadow-xl hover:shadow-violet-600/45 dark:hover:shadow-violet-900/70',
  },
  meeting_sosialisasi: {
    idle:
      'border-0 bg-gradient-to-br from-amber-200 via-amber-100 to-orange-200 text-amber-950 dark:from-amber-700/50 dark:via-amber-600/40 dark:to-orange-800/55 dark:text-amber-50 shadow-md shadow-amber-500/15 hover:shadow-lg hover:shadow-amber-500/30',
    selected:
      'border-0 bg-gradient-to-r from-amber-500 via-orange-500 to-orange-600 text-white shadow-lg shadow-amber-600/35 dark:shadow-amber-900/60 hover:shadow-xl hover:shadow-amber-600/45 dark:hover:shadow-amber-900/70',
  },
  keluarga: {
    idle:
      'border-0 bg-gradient-to-br from-rose-200 via-rose-100 to-pink-200 text-rose-950 dark:from-rose-700/50 dark:via-rose-600/40 dark:to-pink-800/55 dark:text-rose-50 shadow-md shadow-rose-500/15 hover:shadow-lg hover:shadow-rose-500/30',
    selected:
      'border-0 bg-gradient-to-r from-rose-500 via-pink-500 to-pink-600 text-white shadow-lg shadow-rose-600/35 dark:shadow-rose-900/60 hover:shadow-xl hover:shadow-rose-600/45 dark:hover:shadow-rose-900/70',
  },
  instagrammable: {
    idle:
      'border-0 bg-gradient-to-br from-fuchsia-200 via-pink-100 to-rose-200 text-fuchsia-950 dark:from-fuchsia-700/50 dark:via-pink-600/40 dark:to-rose-800/55 dark:text-fuchsia-50 shadow-md shadow-fuchsia-500/15 hover:shadow-lg hover:shadow-fuchsia-500/30',
    selected:
      'border-0 bg-gradient-to-r from-fuchsia-500 via-pink-500 to-rose-500 text-white shadow-lg shadow-fuchsia-600/40 dark:shadow-fuchsia-900/60 hover:shadow-xl hover:shadow-fuchsia-600/50 dark:hover:shadow-fuchsia-900/75',
  },
};

export const CONTEXT_PILL_THEME_DEFAULT = {
  idle:
    'border-0 bg-gradient-to-br from-slate-200 via-slate-100 to-zinc-200 text-slate-900 dark:from-zinc-600 dark:via-zinc-700 dark:to-zinc-800 dark:text-zinc-100 shadow-md shadow-slate-500/10 hover:shadow-lg hover:shadow-slate-500/25',
  selected:
    'border-0 bg-gradient-to-r from-indigo-500 via-violet-500 to-purple-600 text-white shadow-lg shadow-indigo-600/35 dark:shadow-indigo-900/50 hover:shadow-xl hover:shadow-indigo-600/50 dark:hover:shadow-indigo-900/65',
};

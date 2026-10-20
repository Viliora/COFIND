/** Form & payload coffee shop admin — selaras kolom `coffee_shops` di Postgres. */

export const DEFAULT_SHOP_FORM = {
  place_id: '',
  name: '',
  address: '',
  rating: '',
  total_reviews: '',
  latitude: '',
  longitude: '',
  map_embed_url: '',
  opening_hours_display: '',
  opening_day_from: 'Senin',
  opening_day_to: 'Minggu',
  opening_time_from: '08.00',
  opening_time_to: '22.00',
  opening_hours_24h: false,
  phone: '',
  website: '',
  google_maps_url: '',
  price_level: '',
  business_status: '',
};

export const OPENING_HOURS_24H_LABEL = '24 jam';

export const WEEKDAYS = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu'];

export const OPENING_TIME_OPTIONS = (() => {
  const options = [];
  for (let hour = 0; hour < 24; hour += 1) {
    for (const minute of [0, 30]) {
      options.push(`${String(hour).padStart(2, '0')}.${String(minute).padStart(2, '0')}`);
    }
  }
  return options;
})();

export const PRICE_LEVEL_OPTIONS = [
  { value: '', label: '— Tidak diisi —' },
  { value: '0', label: '0 — Gratis' },
  { value: '1', label: '1 — Murah' },
  { value: '2', label: '2 — Sedang' },
  { value: '3', label: '3 — Mahal' },
  { value: '4', label: '4 — Sangat mahal' },
];

export const BUSINESS_STATUS_OPTIONS = [
  { value: '', label: '— Tidak diisi —' },
  { value: 'OPERATIONAL', label: 'Beroperasi' },
  { value: 'CLOSED_TEMPORARILY', label: 'Tutup sementara' },
  { value: 'CLOSED_PERMANENTLY', label: 'Tutup permanen' },
];

export function normalizeOpeningTime(value) {
  const match = String(value || '').trim().match(/^(\d{1,2})[.:](\d{2})$/);
  if (!match) return '';
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return '';
  return `${String(hour).padStart(2, '0')}.${String(minute).padStart(2, '0')}`;
}

export function isOpeningHours24hDisplay(display) {
  return /24\s*jam/i.test(String(display || '').trim());
}

export function parseOpeningHoursDisplay(display) {
  const defaults = {
    opening_day_from: 'Senin',
    opening_day_to: 'Minggu',
    opening_time_from: '08.00',
    opening_time_to: '22.00',
    opening_hours_24h: false,
  };
  const text = String(display || '').trim();
  if (!text) return defaults;

  if (isOpeningHours24hDisplay(text)) {
    const dayMatch = text.match(/^(.+?)-(.+?),/);
    const dayFrom = dayMatch?.[1]?.trim() || 'Senin';
    const dayTo = dayMatch?.[2]?.trim() || 'Minggu';
    return {
      opening_day_from: WEEKDAYS.includes(dayFrom) ? dayFrom : 'Senin',
      opening_day_to: WEEKDAYS.includes(dayTo) ? dayTo : 'Minggu',
      opening_time_from: '00.00',
      opening_time_to: '23.30',
      opening_hours_24h: true,
    };
  }

  const match = text.match(/^(.+?)-(.+?),\s*(.+?)-(.+)$/);
  if (!match) return defaults;

  const dayFrom = match[1].trim();
  const dayTo = match[2].trim();
  const timeFrom = normalizeOpeningTime(match[3]);
  const timeTo = normalizeOpeningTime(match[4]);

  return {
    opening_day_from: WEEKDAYS.includes(dayFrom) ? dayFrom : defaults.opening_day_from,
    opening_day_to: WEEKDAYS.includes(dayTo) ? dayTo : defaults.opening_day_to,
    opening_time_from: OPENING_TIME_OPTIONS.includes(timeFrom) ? timeFrom : defaults.opening_time_from,
    opening_time_to: OPENING_TIME_OPTIONS.includes(timeTo) ? timeTo : defaults.opening_time_to,
    opening_hours_24h: false,
  };
}

export function formatOpeningHoursDisplay(form) {
  const dayFrom = form.opening_day_from || 'Senin';
  const dayTo = form.opening_day_to || 'Minggu';
  if (form.opening_hours_24h) {
    return `${dayFrom}-${dayTo}, ${OPENING_HOURS_24H_LABEL}`;
  }
  const timeFrom = form.opening_time_from || '08.00';
  const timeTo = form.opening_time_to || '22.00';
  return `${dayFrom}-${dayTo}, ${timeFrom}-${timeTo}`;
}

export function shopFormFromRecord(shop) {
  const hours = parseOpeningHoursDisplay(shop.opening_hours_display);
  return {
    place_id: shop.place_id || '',
    name: shop.name || '',
    address: shop.address || '',
    rating: shop.rating ?? '',
    total_reviews: shop.total_reviews ?? '',
    latitude: shop.latitude ?? '',
    longitude: shop.longitude ?? '',
    map_embed_url: shop.map_embed_url || '',
    opening_hours_display: shop.opening_hours_display || '',
    phone: shop.phone || '',
    website: shop.website || '',
    google_maps_url: shop.google_maps_url || '',
    price_level: shop.price_level != null && shop.price_level !== '' ? String(shop.price_level) : '',
    business_status: shop.business_status || '',
    ...hours,
  };
}

export function shopPayloadFromForm(form, mode) {
  const payload = {
    name: form.name,
    address: form.address,
    rating: form.rating === '' ? 0 : Number(form.rating),
    total_reviews: form.total_reviews === '' ? 0 : Number(form.total_reviews),
    latitude: form.latitude === '' ? null : Number(form.latitude),
    longitude: form.longitude === '' ? null : Number(form.longitude),
    map_embed_url: form.map_embed_url,
    opening_hours_display: formatOpeningHoursDisplay(form),
    phone: form.phone || null,
    website: form.website || null,
    google_maps_url: form.google_maps_url || null,
    price_level: form.price_level === '' ? null : Number(form.price_level),
    business_status: form.business_status || null,
  };
  if (mode === 'edit') {
    payload.place_id = form.place_id;
  }
  return payload;
}

export function formatPriceLevelLabel(value) {
  const key = value == null || value === '' ? '' : String(value);
  const found = PRICE_LEVEL_OPTIONS.find((opt) => opt.value === key);
  return found?.label || (key ? `Level ${key}` : '—');
}

export function formatBusinessStatusLabel(value) {
  const key = String(value || '').trim();
  const found = BUSINESS_STATUS_OPTIONS.find((opt) => opt.value === key);
  return found?.label || key || '—';
}

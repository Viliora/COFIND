/** Label tampilan untuk metadata Google Places (selaras dengan google_places_sync.py). */

export const PRICE_LEVEL_LABELS = {
  0: 'Gratis',
  1: 'Murah',
  2: 'Sedang',
  3: 'Mahal',
  4: 'Sangat mahal',
};

export const BUSINESS_STATUS_LABELS = {
  OPERATIONAL: 'Beroperasi',
  CLOSED_TEMPORARILY: 'Tutup sementara',
  CLOSED_PERMANENTLY: 'Tutup permanen',
};

export function parseJsonField(value) {
  if (value == null) return null;
  if (typeof value === 'object') return value;
  if (typeof value === 'string') {
    try {
      return JSON.parse(value);
    } catch {
      return null;
    }
  }
  return null;
}

export function priceLevelLabel(level) {
  if (level == null || level === '') return null;
  const n = Number(level);
  if (Number.isNaN(n)) return null;
  return PRICE_LEVEL_LABELS[n] ?? `Level ${n}`;
}

export function businessStatusLabel(status) {
  if (!status) return null;
  return BUSINESS_STATUS_LABELS[status] || String(status).replace(/_/g, ' ');
}

/** Urutan hari admin + locale Google Places (id). */
export const WEEKDAYS_ID = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu'];

/** Minggu=0 … Sabtu=6 (Date.getDay()). */
export function todayWeekdayNameId() {
  const jsDay = new Date().getDay();
  const map = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu'];
  return map[jsDay] || WEEKDAYS_ID[0];
}

function isWeekdayInRange(day, from, to) {
  const i = WEEKDAYS_ID.indexOf(day);
  const a = WEEKDAYS_ID.indexOf(from);
  const b = WEEKDAYS_ID.indexOf(to);
  if (i < 0 || a < 0 || b < 0) return true;
  if (a <= b) return i >= a && i <= b;
  return i >= a || i <= b;
}

/**
 * Dari teks jam (multiline Google atau format admin), ambil slot hari ini saja.
 * Mengembalikan string jam (mis. "08.00–22.00") tanpa nama hari.
 */
export function openingHoursLineForToday(display) {
  const text = String(display || '').trim();
  if (!text) return null;

  const today = todayWeekdayNameId();

  if (text.includes('\n')) {
    for (const line of text.split('\n')) {
      const trimmed = line.trim();
      const m = trimmed.match(/^([^:]+):\s*(.+)$/);
      if (m && m[1].trim() === today) {
        return m[2].trim();
      }
    }
    return null;
  }

  if (/24\s*jam/i.test(text)) {
    return text.match(/buka\s*24\s*jam/i) ? 'Buka 24 jam' : '24 jam';
  }

  const adminMatch = text.match(/^(.+?)-(.+?),\s*(.+)$/);
  if (adminMatch) {
    const from = adminMatch[1].trim();
    const to = adminMatch[2].trim();
    const times = adminMatch[3].trim();
    if (isWeekdayInRange(today, from, to)) {
      return times.replace(/-/g, '–');
    }
    return null;
  }

  if (/^\d/.test(text)) {
    return text.replace(/\.$/, '');
  }

  return text;
}

const GOOGLE_WEEKDAY_TO_ID = {
  monday: 'Senin',
  tuesday: 'Selasa',
  wednesday: 'Rabu',
  thursday: 'Kamis',
  friday: 'Jumat',
  saturday: 'Sabtu',
  sunday: 'Minggu',
};

function normalizeWeekdayLabel(name) {
  const raw = String(name || '').trim();
  if (!raw) return raw;
  const mapped = GOOGLE_WEEKDAY_TO_ID[raw.toLowerCase()];
  return mapped || raw;
}

/** Parse baris multiline "Hari: jam" (Google weekday_text atau display admin). */
export function parseOpeningHoursDayLines(display) {
  const text = String(display || '').trim();
  if (!text || !text.includes('\n')) return [];

  const rows = [];
  for (const line of text.split('\n')) {
    const trimmed = line.trim();
    const m = trimmed.match(/^([^:]+):\s*(.+)$/);
    if (!m) continue;
    rows.push({
      day: normalizeWeekdayLabel(m[1]),
      hours: m[2].trim(),
    });
  }
  return rows;
}

/** Perluas format admin "Senin-Jumat, 08.00-22.00" menjadi satu baris per hari. */
function expandAdminOpeningHoursRange(display) {
  const text = String(display || '').trim();
  const adminMatch = text.match(/^(.+?)-(.+?),\s*(.+)$/);
  if (!adminMatch) return [];

  const from = normalizeWeekdayLabel(adminMatch[1]);
  const to = normalizeWeekdayLabel(adminMatch[2]);
  const times = adminMatch[3].trim().replace(/-/g, '–');
  const rows = [];
  let inRange = false;
  for (const day of WEEKDAYS_ID) {
    if (day === from) inRange = true;
    if (inRange) rows.push({ day, hours: times });
    if (day === to) inRange = false;
  }
  if (!rows.length && from === to) {
    rows.push({ day: from, hours: times });
  }
  return rows;
}

function sortScheduleRows(rows) {
  const order = new Map(WEEKDAYS_ID.map((d, i) => [d, i]));
  return [...rows].sort((a, b) => {
    const ia = order.get(a.day);
    const ib = order.get(b.day);
    if (ia == null && ib == null) return 0;
    if (ia == null) return 1;
    if (ib == null) return -1;
    return ia - ib;
  });
}

/**
 * Jadwal lengkap + jam hari ini untuk halaman detail.
 * @returns {{ today: string, todayHours: string|null, allDays: { day: string, hours: string }[] }}
 */
export function resolveOpeningHoursSchedule(shop) {
  const today = todayWeekdayNameId();
  const snap = parseJsonField(shop?.google_places_snapshot);
  const weekdayText = snap?.opening_hours?.weekday_text;
  let allDays = [];

  if (Array.isArray(weekdayText) && weekdayText.length) {
    allDays = parseOpeningHoursDayLines(weekdayText.join('\n'));
  }

  const display = String(shop?.opening_hours_display || '').trim();
  if (!allDays.length && display.includes('\n')) {
    allDays = parseOpeningHoursDayLines(display);
  }
  if (!allDays.length && display) {
    allDays = expandAdminOpeningHoursRange(display);
  }
  if (!allDays.length && display && /24\s*jam/i.test(display)) {
    const hours = /buka\s*24\s*jam/i.test(display) ? 'Buka 24 jam' : '24 jam';
    allDays = WEEKDAYS_ID.map((day) => ({ day, hours }));
  }
  if (!allDays.length && display && /^\d/.test(display)) {
    allDays = [{ day: 'Setiap hari', hours: display.replace(/\.$/, '') }];
  }

  allDays = sortScheduleRows(allDays);

  let todayHours = allDays.find((row) => row.day === today)?.hours ?? null;
  if (!todayHours) {
    todayHours = openingHoursForTodayFromShop(shop);
  }
  if (!todayHours && allDays.length === 1) {
    todayHours = allDays[0].hours;
  }

  return { today, todayHours, allDays };
}

/** Jam operasional hari ini untuk kartu katalog (prioritas snapshot Google). */
export function openingHoursForTodayFromShop(shop) {
  const snap = parseJsonField(shop?.google_places_snapshot);
  const weekdayText = snap?.opening_hours?.weekday_text;
  if (Array.isArray(weekdayText) && weekdayText.length) {
    const fromSnap = openingHoursLineForToday(weekdayText.join('\n'));
    if (fromSnap) return fromSnap;
  }
  return openingHoursLineForToday(shop?.opening_hours_display);
}

export function displayTypes(snapshot) {
  const list = snapshot?.types_display;
  if (Array.isArray(list) && list.length) return list;
  const raw = snapshot?.types;
  if (!Array.isArray(raw)) return [];
  const skip = new Set(['establishment', 'point_of_interest', 'food', 'store']);
  return raw
    .map((t) => String(t || '').trim())
    .filter((t) => t && !skip.has(t))
    .map((t) => t.replace(/_/g, ' '))
    .slice(0, 6);
}

/**
 * Satu sumber metadata toko: utamakan google_places_snapshot (fetch terbaru),
 * fallback ke kolom coffee_shops jika snapshot kosong.
 */
export function resolveShopPlacesMeta(detail, googleSnapshot) {
  const snap = googleSnapshot || {};
  const agg = snap.aggregates || {};

  const rating = agg.rating ?? detail?.rating ?? null;
  const userRatingsTotal =
    agg.user_ratings_total
    ?? detail?.total_reviews
    ?? detail?.user_ratings_total
    ?? null;

  const priceLevel = snap.price_level ?? detail?.price_level ?? null;
  const priceLevelLabelResolved =
    snap.price_level_label || priceLevelLabel(priceLevel);

  const businessStatus = snap.business_status ?? detail?.business_status ?? null;
  const businessStatusLabelResolved =
    snap.business_status_label || businessStatusLabel(businessStatus);

  const openNow = snap.opening_hours?.open_now ?? detail?.opening_hours?.open_now;

  const typeItems = displayTypes(snap);
  const types =
    typeItems.length > 0
      ? typeItems
      : (Array.isArray(detail?.types) ? detail.types : []).map((t) =>
          String(t || '').replace(/_/g, ' '),
        );

  return {
    rating,
    userRatingsTotal,
    priceLevelLabel: priceLevelLabelResolved,
    businessStatusLabel: businessStatusLabelResolved,
    openNow,
    typeItems: types.slice(0, 6),
    fetchedAt: snap.fetched_at || detail?.google_places_fetched_at || null,
  };
}

export function accessibilityLabels(businessAttributes) {
  const attrs = businessAttributes || {};
  const items = [];
  if (attrs.wheelchair_accessible_entrance === true) {
    items.push('Akses kursi roda');
  } else if (attrs.wheelchair_accessible_entrance === false) {
    items.push('Tanpa akses kursi roda');
  }
  if (attrs.serves_vegetarian_food === true) items.push('Menu vegetarian');
  return items;
}

/** Pisahkan label atribut Google ke tab target (aksesibilitas / keunggulan / lainnya). */
export function partitionGoogleBusinessLabels(businessAttributes) {
  const accessibility = [];
  const highlights = [];
  const lainnya = [];
  accessibilityLabels(businessAttributes).forEach((item) => {
    if (/kursi roda/i.test(item)) {
      accessibility.push(item);
    } else if (/vegetarian/i.test(item)) {
      highlights.push(item);
    } else {
      lainnya.push(item);
    }
  });
  return { accessibility, highlights, lainnya };
}

/**
 * Foto coffee shop dari frontend-cofind/src/assets/*.webp
 * Nama file = Google place_id (atau alias di PLACE_IMAGE_ALIAS).
 */

const webpModules = import.meta.glob('../assets/*.webp', {
  eager: true,
  import: 'default',
});

/** @type {Record<string, string>} place_id → URL hasil bundler Vite */
const imagesByPlaceId = Object.fromEntries(
  Object.entries(webpModules).map(([path, url]) => {
    const match = path.match(/\/([^/]+)\.webp$/);
    return match ? [match[1], url] : null;
  }).filter(Boolean),
);

const allImageUrls = Object.keys(imagesByPlaceId)
  .sort()
  .map((pid) => imagesByPlaceId[pid]);

/**
 * Toko aktif tanpa file .webp sendiri → foto cadangan (masing-masing unik).
 * Perbarui saat menambah toko/foto baru.
 */
const PLACE_IMAGE_ALIAS = {
  'ChIJBYqZVwBZHS4Rk3hdsQzoQSo': 'ChIJKX36yixZHS4ROQfX-hNWhj0',
  'ChIJ2Xb_uKFZHS4R6PYxDLj5m_A': 'ChIJIRuUuwNZHS4RrhnXINPqQQ4',
  'ChIJnZIEEABZHS4RBs_9Iy6wESM': 'ChIJE8-LfABZHS4R_MsSOwiHNL8',
  'ChIJp8-aIJdZHS4RntlOSrphQj8': 'ChIJC3_RpddZHS4RMiDp7-6TemY',
  'ChIJpXpEsPNZHS4Rciespc96M5o': 'ChIJpVctpWBZHS4RdUbSlT-pSl8',
  'ChIJV7mtlzNZHS4R0rK_eHkd0LU': 'ChIJBVWfsoFZHS4Rakb44yanMjs',
  'ChIJW0ypCwBZHS4RXZ7renLGdwo': 'ChIJ4U6K9hdZHS4RKE7QPIKbn4Y',
};

function hashPlaceId(placeId) {
  let h = 0;
  const s = String(placeId);
  for (let i = 0; i < s.length; i += 1) {
    h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

function resolveImageUrl(placeId) {
  if (!placeId) return allImageUrls[0] || '';
  const key = String(placeId).trim();
  if (imagesByPlaceId[key]) return imagesByPlaceId[key];
  const alias = PLACE_IMAGE_ALIAS[key];
  if (alias && imagesByPlaceId[alias]) return imagesByPlaceId[alias];
  if (allImageUrls.length === 0) return '';
  return allImageUrls[hashPlaceId(key) % allImageUrls.length];
}

/**
 * @param {string|number} identifier - place_id (disarankan) atau nama toko
 * @returns {string} URL foto untuk OptimizedImage / img
 */
export function getCoffeeShopImage(identifier) {
  if (identifier == null || (typeof identifier === 'string' && !identifier.trim())) {
    return allImageUrls[0] || '';
  }
  if (typeof identifier === 'number') {
    return allImageUrls[identifier % allImageUrls.length] || '';
  }
  return resolveImageUrl(identifier);
}

/** Kompatibilitas: pemetaan stabil tanpa localStorage. */
export function ensureCoffeeShopImageMap(shops = []) {
  const map = {};
  (shops || []).forEach((shop) => {
    const key = shop?.place_id || shop?.name;
    if (!key) return;
    map[key] = getCoffeeShopImage(key);
  });
  return map;
}

export function getAllCoffeeShopImages() {
  return [...allImageUrls];
}

export default getCoffeeShopImage;

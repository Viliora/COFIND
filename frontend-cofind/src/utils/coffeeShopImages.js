// Utility untuk assign foto coffee shop dari asset lokal

import photo1 from '../assets/ChIJ9RWUkaZZHS4RYeuZOYAMQ-4.webp';
import photo2 from '../assets/ChIJDcJgropZHS4RKuh8s52jy9U.webp';
import photo3 from '../assets/ChIJ6fOdOEBZHS4RcV3VfZzhYx0.webp';
import photo4 from '../assets/ChIJBVWfsoFZHS4Rakb44yanMjs.webp';
import photo5 from '../assets/ChIJhx6zl0BZHS4RGNla_oPoIJ0.webp';
import photo6 from '../assets/ChIJyRLXBlJYHS4RWNj0yvAvSAQ.webp';
import photo7 from '../assets/ChIJG-xwV2ZZHS4R0WyGi5bbvoM.webp';
import photo8 from '../assets/ChIJPa6swGtZHS4RrbIlRvgBgok.webp';
import photo9 from '../assets/ChIJC3_RpddZHS4RMiDp7-6TemY.webp';
import photo10 from '../assets/ChIJE8-LfABZHS4R_MsSOwiHNL8.webp';
import photo11 from '../assets/ChIJKX36yixZHS4ROQfX-hNWhj0.webp';
import photo12 from '../assets/ChIJIRuUuwNZHS4RrhnXINPqQQ4.webp';
import photo13 from '../assets/ChIJ4U6K9hdZHS4RKE7QPIKbn4Y.webp';
import photo14 from '../assets/ChIJ71m2hZZZHS4RrOgKJYP_7zw.webp';
import photo15 from '../assets/ChIJpVctpWBZHS4RdUbSlT-pSl8.webp';

const coffeeShopImages = [
  photo1,
  photo2,
  photo3,
  photo4,
  photo5,
  photo6,
  photo7,
  photo8,
  photo9,
  photo10,
  photo11,
  photo12,
  photo13,
  photo14,
  photo15,
];

const IMAGE_MAP_KEY = 'cofind_image_map_v1';

const loadImageMap = () => {
  try {
    const stored = localStorage.getItem(IMAGE_MAP_KEY);
    return stored ? JSON.parse(stored) : {};
  } catch (error) {
    console.warn('[getCoffeeShopImage] Failed to load image map:', error);
    return {};
  }
};

const saveImageMap = (map) => {
  try {
    localStorage.setItem(IMAGE_MAP_KEY, JSON.stringify(map));
  } catch (error) {
    console.warn('[getCoffeeShopImage] Failed to save image map:', error);
  }
};

const getNextAvailableIndex = (usedIndices) => {
  for (let i = 0; i < coffeeShopImages.length; i += 1) {
    if (!usedIndices.has(i)) {
      return i;
    }
  }
  console.warn('[getCoffeeShopImage] Image pool exhausted, reusing indexes');
  return usedIndices.size % coffeeShopImages.length;
};

export const ensureCoffeeShopImageMap = (shops = []) => {
  if (shops.length > coffeeShopImages.length) {
    console.warn('[getCoffeeShopImage] Jumlah coffee shop melebihi jumlah foto .webp');
  }
  const map = loadImageMap();
  const usedIndices = new Set(
    Object.values(map).map((value) => Number(value)).filter((value) => Number.isInteger(value))
  );

  let changed = false;
  shops.forEach((shop) => {
    const key = shop?.place_id || shop?.name;
    if (!key) return;
    if (map[key] === undefined) {
      const nextIndex = getNextAvailableIndex(usedIndices);
      map[key] = nextIndex;
      usedIndices.add(nextIndex);
      changed = true;
    }
  });

  if (changed) {
    saveImageMap(map);
  }

  return map;
};

/**
 * Mendapatkan foto coffee shop fallback dari local assets
 * Digunakan sebagai fallback jika photo_url dari Supabase tidak tersedia
 * @param {string|number} identifier - place_id atau nama coffee shop
 * @returns {string} URL foto coffee shop dari local assets
 */
export const getCoffeeShopImage = (identifier) => {
  // Handle missing identifier - return first image as default
  if (!identifier || (typeof identifier === 'string' && identifier.trim() === '')) {
    console.warn('[getCoffeeShopImage] Missing or empty identifier, using default image');
    return coffeeShopImages[0]; // Default to first image
  }

  let imageIndex = 0;

  if (typeof identifier === 'string') {
    const map = ensureCoffeeShopImageMap([{ place_id: identifier }]);
    imageIndex = Number(map[identifier]);
    if (!Number.isInteger(imageIndex) || imageIndex < 0) {
      imageIndex = 0;
    }
  } else {
    // Jika identifier adalah number, gunakan langsung sebagai index
    imageIndex = (identifier || 0) % coffeeShopImages.length;
  }

  return coffeeShopImages[imageIndex];
};

/**
 * Mendapatkan semua foto coffee shop untuk swiper
 * @returns {Array<string>} Array URL foto coffee shop
 */
export const getAllCoffeeShopImages = () => {
  return [...coffeeShopImages];
};

export default getCoffeeShopImage;

// Utility untuk assign foto coffee shop dari asset lokal
import coffeeshop1 from '../assets/coffeeshop_1.webp';
import coffeeshop2 from '../assets/coffeeshop_2.webp';
import coffeeshop3 from '../assets/coffeeshop_3.webp';
import coffeeshop4 from '../assets/coffeeshop_4.webp';
import coffeeshop5 from '../assets/coffeeshop_5.webp';
import coffeeshop6 from '../assets/coffeeshop_6.webp';
import coffeeshop7 from '../assets/coffeeshop_7.webp';
import coffeeshop8 from '../assets/coffeeshop_8.webp';
import coffeeshop9 from '../assets/coffeeshop_9.webp';
import coffeeshop10 from '../assets/coffeeshop_10.webp';
import coffeeshop11 from '../assets/coffeeshop_11.webp';
import coffeeshop12 from '../assets/coffeeshop_12.webp';
import coffeeshop13 from '../assets/coffeeshop_13.webp';
import coffeeshop14 from '../assets/coffeeshop_14.webp';
import coffeeshop15 from '../assets/coffeeshop_15.webp';

import localPlacesData from '../data/places.json';

const coffeeShopImages = [
  coffeeshop1,
  coffeeshop2,
  coffeeshop3,
  coffeeshop4,
  coffeeshop5,
  coffeeshop6,
  coffeeshop7,
  coffeeshop8,
  coffeeshop9,
  coffeeshop10,
  coffeeshop11,
  coffeeshop12,
  coffeeshop13,
  coffeeshop14,
  coffeeshop15,
];

// Mapping place_id ke index di places.json untuk konsistensi
let placeIdToIndexMap = null;

const getPlaceIdToIndexMap = () => {
  if (placeIdToIndexMap === null) {
    placeIdToIndexMap = {};
    if (localPlacesData && localPlacesData.data && Array.isArray(localPlacesData.data)) {
      localPlacesData.data.forEach((shop, index) => {
        if (shop.place_id) {
          placeIdToIndexMap[shop.place_id] = index;
        }
      });
    }
  }
  return placeIdToIndexMap;
};

/**
 * Mendapatkan foto coffee shop berdasarkan place_id atau index
 * Setiap coffee shop mendapat foto yang berbeda berdasarkan urutan di places.json
 * @param {string|number} identifier - place_id atau index coffee shop
 * @returns {string} URL foto coffee shop
 */
export const getCoffeeShopImage = (identifier) => {
  let imageIndex = 0;
  
  if (typeof identifier === 'string') {
    // Jika identifier adalah place_id, cari index-nya di places.json
    const map = getPlaceIdToIndexMap();
    const shopIndex = map[identifier];
    
    if (shopIndex !== undefined) {
      // Gunakan index dari places.json untuk konsistensi
      imageIndex = shopIndex % coffeeShopImages.length;
    } else {
      // Fallback: hash place_id jika tidak ditemukan di places.json
      let hash = 0;
      for (let i = 0; i < identifier.length; i++) {
        hash = ((hash << 5) - hash) + identifier.charCodeAt(i);
        hash = hash & hash;
      }
      imageIndex = Math.abs(hash) % coffeeShopImages.length;
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

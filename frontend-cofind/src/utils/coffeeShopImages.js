// Utility untuk assign foto coffee shop dari asset lokal
// Fallback untuk photo_url dari Supabase jika tidak tersedia

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
    // For place_id, use first 8 characters and convert to number
    // place_id format: ChIJ9RWUkaZZHS4RYeuZOYAMQ-4
    // Extract hex-like characters and mod with array length
    const placeIdPrefix = identifier.substring(0, 8); // "ChIJ9RWU"
    let hash = 0;
    
    for (let i = 0; i < placeIdPrefix.length; i++) {
      const code = placeIdPrefix.charCodeAt(i);
      hash = ((hash << 5) - hash) + code;
      hash = hash & hash; // Convert to 32bit integer
    }
    
    imageIndex = Math.abs(hash) % coffeeShopImages.length;
    console.log(`[getCoffeeShopImage] place_id: ${identifier}, prefix: ${placeIdPrefix}, index: ${imageIndex}`);
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

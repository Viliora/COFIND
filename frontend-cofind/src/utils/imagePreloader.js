// src/utils/imagePreloader.js

/**
 * Image Preloader Utility
 * Preload images untuk featured coffee shops (high priority)
 */

/**
 * Preload single image
 * @param {string} src - Image URL
 * @returns {Promise} - Resolves when image loaded
 */
export const preloadImage = (src) => {
  return new Promise((resolve, reject) => {
    if (!src) {
      reject(new Error('No image source provided'));
      return;
    }

    const img = new Image();
    
    img.onload = () => {
      resolve(src);
    };
    
    img.onerror = () => {
      reject(new Error(`Failed to load image: ${src}`));
    };
    
    img.src = src;
  });
};

/**
 * Preload multiple images
 * @param {Array<string>} srcArray - Array of image URLs
 * @param {Function} onProgress - Callback for progress updates
 * @returns {Promise} - Resolves when all images loaded
 */
export const preloadImages = async (srcArray, onProgress = null) => {
  const validSrcs = srcArray.filter(src => src && typeof src === 'string');
  
  if (validSrcs.length === 0) {
    return [];
  }

  let loadedCount = 0;
  const total = validSrcs.length;

  const promises = validSrcs.map(async (src) => {
    try {
      const result = await preloadImage(src);
      loadedCount++;
      
      if (onProgress) {
        onProgress({
          loaded: loadedCount,
          total: total,
          percentage: Math.round((loadedCount / total) * 100),
          currentSrc: src
        });
      }
      
      return { src, status: 'success' };
    } catch (error) {
      loadedCount++;
      
      if (onProgress) {
        onProgress({
          loaded: loadedCount,
          total: total,
          percentage: Math.round((loadedCount / total) * 100),
          currentSrc: src
        });
      }
      
      return { src, status: 'error', error: error.message };
    }
  });

  return Promise.all(promises);
};

/**
 * Preload featured coffee shop images
 * @param {Array<Object>} featuredShops - Array of coffee shop objects
 * @returns {Promise} - Resolves when featured images loaded
 */
export const preloadFeaturedImages = (featuredShops) => {
  const imageUrls = featuredShops
    .filter(shop => shop.photos && shop.photos.length > 0)
    .map(shop => shop.photos[0]);
  
  return preloadImages(imageUrls, (progress) => {
    console.log(`[Image Preload] Featured images: ${progress.loaded}/${progress.total} (${progress.percentage}%)`);
  });
};

/**
 * Check if image is already cached in browser
 * @param {string} src - Image URL
 * @returns {boolean} - True if cached
 */
export const isImageCached = (src) => {
  if (!src) return false;
  
  const img = new Image();
  img.src = src;
  
  // If complete and naturalWidth > 0, image is cached
  return img.complete && img.naturalWidth > 0;
};

/**
 * Get cache status for multiple images
 * @param {Array<string>} srcArray - Array of image URLs
 * @returns {Object} - Cache statistics
 */
export const getCacheStats = (srcArray) => {
  const validSrcs = srcArray.filter(src => src && typeof src === 'string');
  
  const cached = validSrcs.filter(src => isImageCached(src));
  const notCached = validSrcs.filter(src => !isImageCached(src));
  
  return {
    total: validSrcs.length,
    cached: cached.length,
    notCached: notCached.length,
    cacheRate: validSrcs.length > 0 
      ? Math.round((cached.length / validSrcs.length) * 100) 
      : 0
  };
};


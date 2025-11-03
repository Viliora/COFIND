// Cache Manager Utility untuk mengelola cache storage dari aplikasi

/**
 * Menambahkan atau memperbarui data ke cache storage
 * @param {string} url - URL dari request yang akan di-cache
 * @param {any} data - Data yang akan di-cache (akan di-stringify jika bukan Response)
 * @param {string} cacheType - Tipe cache: 'shell', 'static', 'content', 'pages'
 * @returns {Promise<boolean>}
 */
export async function putCache(url, data, cacheType = 'content') {
  try {
    // Pastikan service worker tersedia
    if (!('serviceWorker' in navigator) || !navigator.serviceWorker.controller) {
      console.warn('[Cache Manager] Service Worker tidak tersedia');
      return false;
    }

    // Kirim message ke service worker
    return new Promise((resolve, reject) => {
      const messageChannel = new MessageChannel();
      
      messageChannel.port1.onmessage = (event) => {
        if (event.data.type === 'CACHE_UPDATED') {
          console.log('[Cache Manager] Cache berhasil di-update:', url);
          resolve(true);
        } else if (event.data.error) {
          reject(new Error(event.data.error));
        }
      };

      navigator.serviceWorker.controller.postMessage(
        {
          type: 'CACHE_PUT',
          url,
          responseData: data,
          cacheType,
        },
        [messageChannel.port2]
      );

      // Timeout setelah 5 detik
      setTimeout(() => {
        reject(new Error('Cache update timeout'));
      }, 5000);
    });
  } catch (error) {
    console.error('[Cache Manager] Error putting cache:', error);
    return false;
  }
}

/**
 * Menghapus item dari cache storage
 * @param {string} url - URL dari request yang akan dihapus dari cache
 * @param {string} cacheType - Tipe cache: 'shell', 'static', 'content', 'pages'
 * @returns {Promise<boolean>}
 */
export async function deleteCache(url, cacheType = 'content') {
  try {
    if (!('serviceWorker' in navigator) || !navigator.serviceWorker.controller) {
      console.warn('[Cache Manager] Service Worker tidak tersedia');
      return false;
    }

    return new Promise((resolve, reject) => {
      const messageChannel = new MessageChannel();
      
      messageChannel.port1.onmessage = (event) => {
        if (event.data.type === 'CACHE_DELETED') {
          console.log('[Cache Manager] Cache berhasil dihapus:', url);
          resolve(true);
        } else if (event.data.error) {
          reject(new Error(event.data.error));
        }
      };

      navigator.serviceWorker.controller.postMessage(
        {
          type: 'CACHE_DELETE',
          url,
          cacheType,
        },
        [messageChannel.port2]
      );

      setTimeout(() => {
        reject(new Error('Cache delete timeout'));
      }, 5000);
    });
  } catch (error) {
    console.error('[Cache Manager] Error deleting cache:', error);
    return false;
  }
}

/**
 * Menghapus semua cache atau cache dari tipe tertentu
 * @param {string|null} cacheType - Tipe cache yang akan dihapus, atau null untuk semua
 * @returns {Promise<boolean>}
 */
export async function clearCache(cacheType = null) {
  try {
    if (!('serviceWorker' in navigator) || !navigator.serviceWorker.controller) {
      console.warn('[Cache Manager] Service Worker tidak tersedia');
      return false;
    }

    return new Promise((resolve, reject) => {
      const messageChannel = new MessageChannel();
      
      messageChannel.port1.onmessage = (event) => {
        if (event.data.type === 'CACHE_CLEARED') {
          console.log('[Cache Manager] Cache berhasil di-clear:', cacheType || 'all');
          resolve(true);
        } else if (event.data.error) {
          reject(new Error(event.data.error));
        }
      };

      navigator.serviceWorker.controller.postMessage(
        {
          type: 'CACHE_CLEAR',
          cacheType,
        },
        [messageChannel.port2]
      );

      setTimeout(() => {
        reject(new Error('Cache clear timeout'));
      }, 5000);
    });
  } catch (error) {
    console.error('[Cache Manager] Error clearing cache:', error);
    return false;
  }
}

/**
 * Mengambil data dari cache storage
 * @param {string} url - URL dari request yang akan diambil
 * @param {string} cacheType - Tipe cache: 'shell', 'static', 'content', 'pages'
 * @returns {Promise<any|null>}
 */
export async function getCache(url, cacheType = 'content') {
  try {
    if (!('caches' in window)) {
      console.warn('[Cache Manager] Cache API tidak tersedia');
      return null;
    }

    const cacheName = getCacheName(cacheType);
    const cache = await caches.open(cacheName);
    const response = await cache.match(url);

    if (response) {
      // Cek apakah response adalah JSON
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        return await response.json();
      }
      return await response.text();
    }

    return null;
  } catch (error) {
    console.error('[Cache Manager] Error getting cache:', error);
    return null;
  }
}

/**
 * Menyimpan response API ke cache setelah fetch
 * @param {string} apiUrl - URL dari API
 * @param {Response} response - Response object dari fetch
 * @param {string} cacheType - Tipe cache
 * @returns {Promise<boolean>}
 */
export async function cacheApiResponse(apiUrl, response, cacheType = 'content') {
  try {
    if (!response || response.status !== 200) {
      return false;
    }

    const cacheName = getCacheName(cacheType);
    const cache = await caches.open(cacheName);
    
    // Clone response karena response stream hanya bisa dibaca sekali
    await cache.put(apiUrl, response.clone());
    
    console.log('[Cache Manager] API response cached:', apiUrl);
    return true;
  } catch (error) {
    console.error('[Cache Manager] Error caching API response:', error);
    return false;
  }
}

/**
 * Fetch dengan auto-caching
 * @param {string} url - URL yang akan di-fetch
 * @param {RequestInit} options - Fetch options
 * @param {string} cacheType - Tipe cache
 * @returns {Promise<Response>}
 */
export async function fetchWithCache(url, options = {}, cacheType = 'content') {
  try {
    // Cek cache dulu
    const cachedData = await getCache(url, cacheType);
    if (cachedData) {
      console.log('[Cache Manager] Serving from cache:', url);
      // Return cached data sebagai Response
      return new Response(JSON.stringify(cachedData), {
        headers: { 'Content-Type': 'application/json' },
        status: 200,
      });
    }

    // Fetch dari network
    const response = await fetch(url, options);
    
    if (response.ok) {
      // Cache response untuk next time
      await cacheApiResponse(url, response, cacheType);
    }
    
    return response;
  } catch (error) {
    console.error('[Cache Manager] Error fetching with cache:', error);
    throw error;
  }
}

/**
 * Mendapatkan informasi tentang cache storage
 * @returns {Promise<Object>}
 */
export async function getCacheInfo() {
  try {
    if (!('caches' in window)) {
      return { available: false };
    }

    const cacheNames = await caches.keys();
    const cacheInfo = {
      available: true,
      cacheCount: cacheNames.length,
      caches: {},
    };

    // Hitung ukuran setiap cache
    for (const cacheName of cacheNames) {
      const cache = await caches.open(cacheName);
      const keys = await cache.keys();
      cacheInfo.caches[cacheName] = {
        itemCount: keys.length,
        urls: keys.map(req => req.url).slice(0, 10), // First 10 URLs
      };
    }

    return cacheInfo;
  } catch (error) {
    console.error('[Cache Manager] Error getting cache info:', error);
    return { available: false, error: error.message };
  }
}

/**
 * Helper untuk mendapatkan nama cache
 */
function getCacheName(type) {
  const version = 'v2'; // Harus sesuai dengan versi di service worker
  switch(type) {
    case 'shell': return `cofind-shell-${version}`;
    case 'static': return `cofind-static-${version}`;
    case 'content': return `cofind-content-${version}`;
    case 'pages': return `cofind-pages-${version}`;
    default: return `cofind-content-${version}`;
  }
}

// Export untuk digunakan di React components
export default {
  putCache,
  deleteCache,
  clearCache,
  getCache,
  cacheApiResponse,
  fetchWithCache,
  getCacheInfo,
};


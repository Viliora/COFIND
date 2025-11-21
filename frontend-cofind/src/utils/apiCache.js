// API Cache Manager - untuk caching data API dengan IndexedDB dan Cache API

import { openDB, saveToDB, getFromDB } from './indexedDB';

const API_CACHE_STORE = 'userData'; // Gunakan userData store untuk cache API
const CACHE_EXPIRY = 24 * 60 * 60 * 1000; // 24 jam dalam milliseconds

/**
 * Initialize API Cache Database
 */
export async function initAPICache() {
  try {
    await openDB();
    console.log('[API Cache] Database initialized');
  } catch (error) {
    console.error('[API Cache] Error initializing database:', error);
  }
}

/**
 * Check if cached data is still valid (not expired)
 */
function isCacheValid(cachedData) {
  if (!cachedData || !cachedData.timestamp) return false;
  const now = Date.now();
  const age = now - cachedData.timestamp;
  return age < CACHE_EXPIRY;
}

/**
 * Fetch data from API dengan caching strategy
 * Strategy: Network First dengan fallback ke cache
 * 
 * @param {string} apiUrl - URL API endpoint
 * @param {Object} options - Fetch options (method, headers, body, dll)
 * @returns {Promise<Object>} - Data dari API atau cache
 */
export async function fetchWithCache(apiUrl, options = {}) {
  try {
    console.log('[API Cache] Fetching from network:', apiUrl);
    
    // 1. Coba fetch dari network dulu (timeout 10 detik untuk data besar)
    const networkResponse = await Promise.race([
      fetch(apiUrl, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      }),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Network timeout after 10s')), 10000)
      ),
    ]);
    
    console.log('[API Cache] Network response status:', networkResponse.status);

    if (networkResponse && networkResponse.ok) {
      const data = await networkResponse.json();
      
      // 2. Simpan ke cache untuk next time
      await cacheAPIData(apiUrl, data);
      
      // 3. Simpan ke Cache API juga (untuk service worker)
      if ('caches' in window) {
        const cache = await caches.open('cofind-content-v2');
        await cache.put(apiUrl, new Response(JSON.stringify(data), {
          headers: { 'Content-Type': 'application/json' },
        }));
      }
      
      console.log('[API Cache] Data fetched from network and cached:', apiUrl);
      return { data, fromCache: false };
    }

    throw new Error(`Network response not OK: ${networkResponse.status} ${networkResponse.statusText}`);
  } catch (networkError) {
    console.error('[API Cache] Network failed:', {
      message: networkError.message,
      url: apiUrl,
      type: networkError.name
    });
    console.log('[API Cache] Trying cache fallback...');
    
    // 3. Fallback ke cache jika network gagal
    const cachedData = await getCachedData(apiUrl);
    
    if (cachedData && isCacheValid(cachedData)) {
      console.log('[API Cache] Serving from cache:', apiUrl);
      return { data: cachedData.data, fromCache: true };
    }
    
    // 4. Jika cache juga tidak valid, coba dari Cache API
    if ('caches' in window) {
      const cache = await caches.open('cofind-content-v2');
      const cachedResponse = await cache.match(apiUrl);
      
      if (cachedResponse) {
        const data = await cachedResponse.json();
        console.log('[API Cache] Serving from Cache API:', apiUrl);
        return { data, fromCache: true };
      }
    }
    
    // 5. Jika semua gagal, throw error
    throw new Error('Network failed and no valid cache available');
  }
}

/**
 * Cache API data ke IndexedDB
 */
async function cacheAPIData(apiUrl, data) {
  try {
    await initAPICache();
    
    const cacheEntry = {
      key: `api_cache_${apiUrl}`,
      url: apiUrl,
      data: data,
      timestamp: Date.now(),
    };
    
    await saveToDB(API_CACHE_STORE, cacheEntry);
    console.log('[API Cache] Data cached:', apiUrl);
  } catch (error) {
    console.error('[API Cache] Error caching data:', error);
  }
}

/**
 * Get cached data dari IndexedDB
 */
async function getCachedData(apiUrl) {
  try {
    await initAPICache();
    const cacheKey = `api_cache_${apiUrl}`;
    const cached = await getFromDB(API_CACHE_STORE, cacheKey);
    return cached || null;
  } catch (error) {
    console.error('[API Cache] Error getting cached data:', error);
    return null;
  }
}

/**
 * Get all cached coffee shops
 */
export async function getAllCachedCoffeeShops() {
  try {
    await initAPICache();
    const allCached = await getFromDB(API_CACHE_STORE);
    
    if (!Array.isArray(allCached)) return null;
    
    // Filter hanya coffee shops data dan valid cache
    const validCaches = allCached.filter(
      (entry) => entry && entry.key?.startsWith('api_cache_') && isCacheValid(entry) && entry.data?.data
    );
    
    if (validCaches.length > 0) {
      // Ambil data terbaru
      const latest = validCaches.reduce((prev, current) =>
        current.timestamp > prev.timestamp ? current : prev
      );
      
      return latest.data;
    }
    
    return null;
  } catch (error) {
    console.error('[API Cache] Error getting all cached coffee shops:', error);
    return null;
  }
}

/**
 * Clear expired cache entries
 */
export async function clearExpiredCache() {
  try {
    await initAPICache();
    const allCached = await getFromDB(API_CACHE_STORE);
    const now = Date.now();
    
    if (!Array.isArray(allCached)) return;
    
    // TODO: Implement delete expired entries
    // Untuk sekarang, cache akan expire otomatis saat di-check
    console.log('[API Cache] Expired cache cleanup (deferred)');
  } catch (error) {
    console.error('[API Cache] Error clearing expired cache:', error);
  }
}

/**
 * Clear all API cache
 */
export async function clearAPICache() {
  try {
    const { clearStore } = await import('./indexedDB');
    await clearStore(API_CACHE_STORE);
    
    // Clear dari Cache API juga
    if ('caches' in window) {
      const cache = await caches.open('cofind-content-v2');
      const keys = await cache.keys();
      for (const key of keys) {
        if (key.url.includes('/api/')) {
          await cache.delete(key);
        }
      }
    }
    
    console.log('[API Cache] All cache cleared');
  } catch (error) {
    console.error('[API Cache] Error clearing cache:', error);
  }
}

/**
 * Pre-cache data untuk offline access
 * Call ini setelah fetch berhasil untuk memastikan data di-cache
 */
export async function preCacheCoffeeShops(data) {
  try {
    const apiUrl = '/api/search/coffeeshops'; // Default API URL
    await cacheAPIData(apiUrl, data);
    console.log('[API Cache] Coffee shops pre-cached');
  } catch (error) {
    console.error('[API Cache] Error pre-caching:', error);
  }
}


// Development Cache Manager
// Untuk mempercepat development dengan caching data di memory dan localStorage

const DEV_CACHE_PREFIX = 'cofind_dev_cache_';
const DEV_CACHE_TTL = 5 * 60 * 1000; // 5 menit (adjustable)

// In-memory cache untuk speed (hilang saat refresh)
const memoryCache = new Map();

// Pending requests map untuk request deduplication
const pendingRequests = new Map();

/**
 * Check if we're in development mode
 */
export function isDevelopmentMode() {
  return import.meta.env.DEV || 
         window.location.hostname === 'localhost' || 
         window.location.hostname === '127.0.0.1' ||
         window.location.hostname === '[::1]';
}

/**
 * Get cache key
 */
function getCacheKey(url) {
  return `${DEV_CACHE_PREFIX}${url}`;
}

/**
 * Check if cache is valid
 */
function isCacheValid(cacheEntry) {
  if (!cacheEntry || !cacheEntry.timestamp) return false;
  const age = Date.now() - cacheEntry.timestamp;
  return age < DEV_CACHE_TTL;
}

/**
 * Get from memory cache first, then localStorage
 */
export function getFromDevCache(url) {
  try {
    // 1. Check memory cache first (fastest)
    if (memoryCache.has(url)) {
      const cached = memoryCache.get(url);
      if (isCacheValid(cached)) {
        console.log('[Dev Cache] HIT (memory):', url);
        return cached.data;
      } else {
        memoryCache.delete(url);
      }
    }

    // 2. Check localStorage (persistent across refresh)
    const cacheKey = getCacheKey(url);
    const stored = localStorage.getItem(cacheKey);
    
    if (stored) {
      const cached = JSON.parse(stored);
      if (isCacheValid(cached)) {
        console.log('[Dev Cache] HIT (localStorage):', url);
        // Restore to memory cache
        memoryCache.set(url, cached);
        return cached.data;
      } else {
        localStorage.removeItem(cacheKey);
      }
    }

    console.log('[Dev Cache] MISS:', url);
    return null;
  } catch (error) {
    console.error('[Dev Cache] Error reading cache:', error);
    return null;
  }
}

/**
 * Save to both memory and localStorage
 */
export function saveToDevCache(url, data) {
  try {
    const cacheEntry = {
      data,
      timestamp: Date.now(),
      url
    };

    // Save to memory
    memoryCache.set(url, cacheEntry);

    // Save to localStorage (persistent)
    const cacheKey = getCacheKey(url);
    localStorage.setItem(cacheKey, JSON.stringify(cacheEntry));

    console.log('[Dev Cache] SAVED:', url);
  } catch (error) {
    console.error('[Dev Cache] Error saving cache:', error);
  }
}

/**
 * Clear all dev cache
 */
export function clearDevCache() {
  try {
    // Clear memory
    memoryCache.clear();

    // Clear localStorage
    const keys = Object.keys(localStorage);
    keys.forEach(key => {
      if (key.startsWith(DEV_CACHE_PREFIX)) {
        localStorage.removeItem(key);
      }
    });

    console.log('[Dev Cache] CLEARED');
  } catch (error) {
    console.error('[Dev Cache] Error clearing cache:', error);
  }
}

/**
 * Fetch with cache and request deduplication
 * STALE-WHILE-REVALIDATE strategy:
 * - Return cached data immediately if available
 * - Fetch fresh data in background
 * - Update cache and notify when fresh data arrives
 */
export async function fetchWithDevCache(url, options = {}) {
  try {
    // 1. Check cache first (STALE-WHILE-REVALIDATE)
    const cachedData = getFromDevCache(url);
    
    if (cachedData) {
      console.log('[Dev Cache] Returning cached data, fetching fresh in background...');
      
      // Return cached data immediately
      const cachedResult = { data: cachedData, fromCache: true, stale: true };
      
      // Fetch fresh data in background (non-blocking)
      fetchFreshData(url, options).catch(err => {
        console.warn('[Dev Cache] Background fetch failed:', err.message);
      });
      
      return cachedResult;
    }

    // 2. No cache - fetch fresh data (blocking)
    console.log('[Dev Cache] No cache, fetching fresh data...');
    return await fetchFreshData(url, options);

  } catch (error) {
    console.error('[Dev Cache] Error in fetchWithDevCache:', error);
    throw error;
  }
}

/**
 * Fetch fresh data with request deduplication
 */
async function fetchFreshData(url, options = {}) {
  // Request deduplication: prevent multiple identical requests
  if (pendingRequests.has(url)) {
    console.log('[Dev Cache] Request deduplication - waiting for pending request:', url);
    return await pendingRequests.get(url);
  }

  // Create fetch promise
  const fetchPromise = (async () => {
    try {
      console.log('[Dev Cache] Fetching from network:', url);
      
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      
      // Save to cache
      saveToDevCache(url, data);
      
      console.log('[Dev Cache] Fresh data fetched and cached');
      
      return { data, fromCache: false, stale: false };
    } finally {
      // Remove from pending requests
      pendingRequests.delete(url);
    }
  })();

  // Store pending request
  pendingRequests.set(url, fetchPromise);

  return await fetchPromise;
}

/**
 * Get cache info for debugging
 */
export function getDevCacheInfo() {
  const memorySize = memoryCache.size;
  const localStorageKeys = Object.keys(localStorage).filter(k => 
    k.startsWith(DEV_CACHE_PREFIX)
  );
  
  return {
    memoryCache: {
      size: memorySize,
      entries: Array.from(memoryCache.keys())
    },
    localStorage: {
      size: localStorageKeys.length,
      entries: localStorageKeys
    },
    ttl: DEV_CACHE_TTL,
    isDevelopment: isDevelopmentMode()
  };
}

// Expose to window for debugging
if (isDevelopmentMode()) {
  window.__cofindDevCache = {
    clear: clearDevCache,
    info: getDevCacheInfo,
    get: getFromDevCache,
    save: saveToDevCache
  };
  
  console.log('[Dev Cache] Debug tools available: window.__cofindDevCache');
}


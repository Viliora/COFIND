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
 * Check if URL is auth-related and should not be cached
 * CRITICAL: Session dan auth endpoints harus SELALU fresh
 */
function isAuthRelated(url) {
  if (!url) return false;
  const lowerUrl = url.toLowerCase();
  
  // EXTENDED: Tambahan endpoint yang auth/session sensitive
  return (
    lowerUrl.includes('/auth/') ||
    lowerUrl.includes('/session') ||
    lowerUrl.includes('/validate') ||
    lowerUrl.includes('/refresh') ||
    lowerUrl.includes('/profile') ||
    lowerUrl.includes('/user') ||
    (lowerUrl.includes('/reviews') && lowerUrl.includes('user_id')) ||
    lowerUrl.includes('/favorites') ||
    lowerUrl.includes('/want-to-visit') ||
    lowerUrl.endsWith('.html') ||
    lowerUrl.endsWith('index.html')
  );
}

/**
 * Get from memory cache first, then localStorage
 */
export function getFromDevCache(url) {
  try {
    // CRITICAL: Never cache auth-related requests
    if (isAuthRelated(url)) {
      console.log('[Dev Cache] SKIP CACHE (auth-related):', url);
      return null;
    }

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
    // CRITICAL: Never cache auth-related requests
    if (isAuthRelated(url)) {
      console.log('[Dev Cache] SKIP SAVE (auth-related):', url);
      return;
    }

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
 * Clear all auth-related cache entries
 * CRITICAL: Call this on logout or auth state changes
 */
export function clearAuthCache() {
  try {
    // Clear from memory cache
    const memoryKeys = Array.from(memoryCache.keys());
    memoryKeys.forEach(url => {
      if (isAuthRelated(url)) {
        memoryCache.delete(url);
        console.log('[Dev Cache] Removed auth cache from memory:', url);
      }
    });

    // Clear from localStorage
    const keys = Object.keys(localStorage);
    keys.forEach(key => {
      if (key.startsWith(DEV_CACHE_PREFIX)) {
        try {
          const stored = localStorage.getItem(key);
          if (stored) {
            const cached = JSON.parse(stored);
            if (cached.url && isAuthRelated(cached.url)) {
              localStorage.removeItem(key);
              console.log('[Dev Cache] Removed auth cache from localStorage:', cached.url);
            }
          }
        } catch {
          void 0;
        }
      }
    });

    console.log('[Dev Cache] Auth cache cleared');
  } catch (error) {
    console.error('[Dev Cache] Error clearing auth cache:', error);
  }
}

/**
 * Fetch with cache and request deduplication
 * STALE-WHILE-REVALIDATE strategy:
 * - Return cached data immediately if available
 * - Fetch fresh data in background
 * - Update cache and notify when fresh data arrives
 * 
 * CRITICAL: Cache is DISABLED for now to fix auth/profile issues
 * All requests fetch fresh data from network only
 */
export async function fetchWithDevCache(url, options = {}) {
  try {
    // DISABLED: All caching disabled due to auth/profile sync issues
    // Always fetch fresh data from network
    console.log('[Dev Cache] CACHING DISABLED - fetching fresh from network:', url);
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
          // CRITICAL: Add no-cache headers for auth-related requests
          ...(isAuthRelated(url) ? {
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
          } : {}),
          ...options.headers,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      
      // Save to cache (will skip if auth-related)
      saveToDevCache(url, data);
      
      console.log('[Dev Cache] Fresh data fetched', isAuthRelated(url) ? '(NOT cached - auth-related)' : 'and cached');
      
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
    clearAuth: clearAuthCache,
    info: getDevCacheInfo,
    get: getFromDevCache,
    save: saveToDevCache
  };
  
  console.log('[Dev Cache] Debug tools available: window.__cofindDevCache');
}


/**
 * Session Persistence Fix
 *
 * Memastikan session tetap valid setelah refresh page
 * - Prevent service worker dari cache HTML pages
 * - Prevent localStorage dari cache auth tokens yang expired
 * - Force fresh fetch dari backend setiap kali
 */

// Clear old Service Worker caches dari version lama
export async function clearOldServiceWorkerCaches() {
  try {
    const allCacheNames = await caches.keys();
    const oldVersions = allCacheNames.filter(name =>
      name.startsWith('cofind-') && !name.includes('v6')
    );

    for (const cacheName of oldVersions) {
      await caches.delete(cacheName);
      console.log('[Session Fix] Deleted old cache:', cacheName);
    }

    if (oldVersions.length > 0) {
      console.log('[Session Fix] Cleared', oldVersions.length, 'old service worker caches');
    }
  } catch (error) {
    console.error('[Session Fix] Error clearing old caches:', error);
  }
}

// Force browser to NOT cache HTML pages by clearing browser cache headers
export function setAggressiveCacheControl() {
  try {
    // Inject meta tags dinamis untuk cache control (jika belum ada)
    const existingMeta = document.querySelector('meta[http-equiv="Cache-Control"]');
    if (!existingMeta) {
      const meta = document.createElement('meta');
      meta.httpEquiv = 'Cache-Control';
      meta.content = 'no-cache, no-store, must-revalidate, max-age=0';
      document.head.appendChild(meta);
    }

    // Disable browser bfcache (back-forward cache) untuk prevent stale sessions
    window.addEventListener('beforeunload', () => {
      // Clear critical session markers
      sessionStorage.setItem('page_unload_time', Date.now().toString());
    });

    console.log('[Session Fix] Aggressive cache control enabled');
  } catch (error) {
    console.error('[Session Fix] Error setting cache control:', error);
  }
}

// Detect dan notify jika page di-load dari browser cache (bfcache)
export function detectBackForwardCache() {
  try {
    // Jika page di-load dari bfcache, pageshow event akan fire dengan persisted=true
    window.addEventListener('pageshow', (event) => {
      if (event.persisted) {
        console.warn('[Session Fix] Page loaded from bfcache (back-forward cache), session might be stale!');
        // Reload page untuk ensure fresh session
        window.location.reload();
      }
    });

    // pagehide event untuk cleanup
    window.addEventListener('pagehide', (event) => {
      if (event.persisted) {
        console.log('[Session Fix] Page might enter bfcache');
      }
    });

    console.log('[Session Fix] Back-forward cache detector enabled');
  } catch (error) {
    console.error('[Session Fix] Error setting up bfcache detector:', error);
  }
}

// Main initialization - call this di App.jsx useEffect
export function initializeSessionFix() {
  try {
    console.log('[Session Fix] Initializing session persistence fixes...');

    // 1. Clear old caches
    clearOldServiceWorkerCaches().catch(err =>
      console.error('[Session Fix] Error in clearOldServiceWorkerCaches:', err)
    );

    // 2. Set aggressive cache control headers
    setAggressiveCacheControl();

    // 3. Detect back-forward cache issues
    detectBackForwardCache();

    console.log('[Session Fix] Initialization complete');
  } catch (error) {
    console.error('[Session Fix] Fatal error during initialization:', error);
  }
}

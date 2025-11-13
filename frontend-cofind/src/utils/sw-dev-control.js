// Development Control untuk Service Worker
// Gunakan ini untuk enable/disable service worker di development untuk testing cache

/**
 * Force enable service worker di development mode (untuk testing cache)
 * Note: Ini akan mengganggu HMR, jadi gunakan hanya jika perlu test cache
 */
export function forceEnableServiceWorkerInDev() {
  // Override development detection
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker
        .register('/sw.js')
        .then((registration) => {
          console.log('[SW Dev Control] Service Worker FORCED enabled di development mode');
          console.log('[SW Dev Control] WARNING: HMR mungkin tidak bekerja dengan baik');
          return registration;
        })
        .catch((error) => {
          console.error('[SW Dev Control] Gagal register Service Worker:', error);
        });
    });
  }
}

/**
 * Check apakah service worker aktif
 */
export async function isServiceWorkerActive() {
  if ('serviceWorker' in navigator) {
    const registration = await navigator.serviceWorker.getRegistration();
    return registration !== undefined && navigator.serviceWorker.controller !== null;
  }
  return false;
}

/**
 * Get cache storage info
 */
export async function getCacheStorageInfo() {
  if ('caches' in window) {
    const cacheNames = await caches.keys();
    const cacheInfo = await Promise.all(
      cacheNames.map(async (name) => {
        const cache = await caches.open(name);
        const keys = await cache.keys();
        return {
          name,
          size: keys.length,
          keys: keys.map(k => k.url),
        };
      })
    );
    return cacheInfo;
  }
  return [];
}







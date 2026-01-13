// Script untuk menghapus semua cache - jalankan di browser console
// Paste ke console dan jalankan untuk membersihkan semua development cache

console.log('🧹 Clearing all caches...');

// 1. Clear localStorage (dev cache)
const keys = Object.keys(localStorage);
let localStorageCount = 0;
keys.forEach(key => {
  if (key.startsWith('cofind_dev_cache_')) {
    localStorage.removeItem(key);
    localStorageCount++;
    console.log('❌ Removed localStorage:', key);
  }
});
console.log(`✅ Cleared ${localStorageCount} localStorage entries`);

// 2. Clear sessionStorage
sessionStorage.clear();
console.log('✅ Cleared sessionStorage');

// 3. Clear IndexedDB
if (window.indexedDB) {
  const dbs = await indexedDB.databases();
  dbs.forEach(db => {
    if (db.name.includes('cofind') || db.name.includes('cache')) {
      indexedDB.deleteDatabase(db.name);
      console.log('❌ Deleted IndexedDB:', db.name);
    }
  });
  console.log('✅ Cleared IndexedDB');
}

// 4. Clear Service Worker cache
if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
  navigator.serviceWorker.controller.postMessage({
    type: 'CLEAR_ALL_CACHE'
  });
  console.log('✅ Sent clear cache message to Service Worker');
}

// 5. Clear browser cache (via Service Worker)
if ('caches' in window) {
  const cacheNames = await caches.keys();
  cacheNames.forEach(async (cacheName) => {
    if (cacheName.includes('cofind') || cacheName.includes('v1')) {
      await caches.delete(cacheName);
      console.log('❌ Deleted cache:', cacheName);
    }
  });
  console.log('✅ Cleared browser caches');
}

console.log('\n✨ All caches have been cleared!');
console.log('⚠️  Reload the page now (Ctrl+Shift+R or Cmd+Shift+R)');

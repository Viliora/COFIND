// Service Worker untuk Cofind
const CACHE_NAME = 'cofind-v1';
const CACHE_STATIC_NAME = 'cofind-static-v1';
const CACHE_DYNAMIC_NAME = 'cofind-dynamic-v1';

// Assets yang akan di-cache saat instalasi
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/src/main.jsx',
  '/src/App.jsx',
  '/src/index.css',
];

// ============================================
// LIFECYCLE: INSTALLATION
// ============================================
self.addEventListener('install', (event) => {
  console.log('[Service Worker] Installing...', event);
  
  // Menunggu hingga semua assets di-cache sebelum mengaktifkan service worker baru
  event.waitUntil(
    caches.open(CACHE_STATIC_NAME)
      .then((cache) => {
        console.log('[Service Worker] Precaching static assets');
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => {
        // Skip waiting untuk segera mengaktifkan service worker baru
        return self.skipWaiting();
      })
      .catch((error) => {
        console.error('[Service Worker] Error during installation:', error);
      })
  );
});

// ============================================
// LIFECYCLE: ACTIVATION
// ============================================
self.addEventListener('activate', (event) => {
  console.log('[Service Worker] Activating...', event);
  
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        // Hapus cache lama yang tidak digunakan
        return Promise.all(
          cacheNames.map((cacheName) => {
            if (cacheName !== CACHE_STATIC_NAME && 
                cacheName !== CACHE_DYNAMIC_NAME &&
                cacheName !== CACHE_NAME) {
              console.log('[Service Worker] Removing old cache:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      })
      .then(() => {
        // Claim clients untuk mengendalikan semua klien tanpa reload
        return self.clients.claim();
      })
      .catch((error) => {
        console.error('[Service Worker] Error during activation:', error);
      })
  );
});

// ============================================
// LIFECYCLE: IDLE STATE
// ============================================
// Service worker akan masuk ke idle state setelah tidak ada event yang ditangani
// Tidak ada event handler khusus untuk idle, tapi kita bisa menambahkan log
self.addEventListener('message', (event) => {
  console.log('[Service Worker] Message received:', event.data);
  
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  if (event.data && event.data.type === 'GET_VERSION') {
    event.ports[0].postMessage({ version: CACHE_NAME });
  }
});

// ============================================
// EVENT: FETCH
// ============================================
self.addEventListener('fetch', (event) => {
  console.log('[Service Worker] Fetch event:', event.request.url);
  
  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }
  
  // Skip chrome-extension dan chrome:// requests
  if (event.request.url.startsWith('chrome-extension://') || 
      event.request.url.startsWith('chrome://')) {
    return;
  }
  
  event.respondWith(
    caches.match(event.request)
      .then((cachedResponse) => {
        // Jika ada di cache, return dari cache
        if (cachedResponse) {
          console.log('[Service Worker] Serving from cache:', event.request.url);
          return cachedResponse;
        }
        
        // Jika tidak ada di cache, fetch dari network
        return fetch(event.request)
          .then((response) => {
            // Validasi response
            if (!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }
            
            // Clone response karena response stream hanya bisa dibaca sekali
            const responseToCache = response.clone();
            
            // Cache response dinamis untuk request API atau resources
            caches.open(CACHE_DYNAMIC_NAME)
              .then((cache) => {
                // Hanya cache GET requests yang valid
                if (event.request.method === 'GET') {
                  cache.put(event.request, responseToCache);
                }
              });
            
            return response;
          })
          .catch((error) => {
            console.error('[Service Worker] Fetch failed:', error);
            
            // Fallback: jika network gagal dan request untuk halaman HTML,
            // return halaman offline (jika ada)
            if (event.request.headers.get('accept').includes('text/html')) {
              return caches.match('/index.html');
            }
            
            throw error;
          });
      })
  );
});

// ============================================
// EVENT: PUSH (Push Notifications)
// ============================================
self.addEventListener('push', (event) => {
  console.log('[Service Worker] Push notification received:', event);
  
  let notificationData = {
    title: 'Cofind',
    body: 'Anda memiliki notifikasi baru',
    icon: '/vite.svg',
    badge: '/vite.svg',
    tag: 'cofind-notification',
    requireInteraction: false,
  };
  
  // Parse data dari push message jika ada
  if (event.data) {
    try {
      const data = event.data.json();
      notificationData = {
        ...notificationData,
        ...data,
      };
    } catch (e) {
      // Jika bukan JSON, gunakan sebagai teks
      notificationData.body = event.data.text();
    }
  }
  
  event.waitUntil(
    self.registration.showNotification(notificationData.title, {
      body: notificationData.body,
      icon: notificationData.icon,
      badge: notificationData.badge,
      tag: notificationData.tag,
      requireInteraction: notificationData.requireInteraction,
      data: notificationData,
      actions: [
        {
          action: 'open',
          title: 'Buka Aplikasi',
        },
        {
          action: 'close',
          title: 'Tutup',
        },
      ],
    })
  );
});

// ============================================
// EVENT: SYNC (Background Sync)
// ============================================
self.addEventListener('sync', (event) => {
  console.log('[Service Worker] Background sync event:', event.tag);
  
  // Sync untuk data offline
  if (event.tag === 'sync-offline-data') {
    event.waitUntil(syncOfflineData());
  }
  
  // Sync untuk favorit/penanda
  if (event.tag === 'sync-favorites') {
    event.waitUntil(syncFavorites());
  }
});

// Fungsi helper untuk sync data offline
async function syncOfflineData() {
  try {
    console.log('[Service Worker] Syncing offline data...');
    
    // Ambil data dari IndexedDB atau cache yang perlu di-sync
    const cache = await caches.open(CACHE_DYNAMIC_NAME);
    const keys = await cache.keys();
    
    console.log('[Service Worker] Found', keys.length, 'items to sync');
    
    // Di sini Anda bisa mengimplementasikan logika sync dengan server
    // Contoh: kirim data yang tersimpan offline ke server
    
    return Promise.resolve();
  } catch (error) {
    console.error('[Service Worker] Error syncing offline data:', error);
    return Promise.reject(error);
  }
}

// Fungsi helper untuk sync favorites
async function syncFavorites() {
  try {
    console.log('[Service Worker] Syncing favorites...');
    
    // Di sini Anda bisa mengimplementasikan logika sync favorites dengan server
    
    return Promise.resolve();
  } catch (error) {
  console.error('[Service Worker] Error syncing favorites:', error);
    return Promise.reject(error);
  }
}

// ============================================
// EVENT: NOTIFICATION CLICK
// ============================================
self.addEventListener('notificationclick', (event) => {
  console.log('[Service Worker] Notification clicked:', event);
  
  event.notification.close();
  
  if (event.action === 'open') {
    event.waitUntil(
      clients.openWindow('/')
    );
  }
  
  // Default action: buka aplikasi
  if (!event.action) {
    event.waitUntil(
      clients.openWindow('/')
    );
  }
});


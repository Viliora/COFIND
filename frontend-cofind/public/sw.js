// Service Worker untuk Cofind dengan Optimized Caching Strategy
// UPDATE CACHE VERSION SETIAP KALI ADA PERUBAHAN PENTING
const CACHE_VERSION = 'cofind-v5'; // Updated untuk fix HTML page caching (login page issue)
const CACHE_SHELL = 'cofind-shell-v5';      // Navbar, Footer, App.jsx, CSS
const CACHE_STATIC = 'cofind-static-v5';    // Images, fonts, dll
const CACHE_CONTENT = 'cofind-content-v5';  // API responses, dynamic content (DISABLED)
// CACHE_PAGES dihapus - HTML pages tidak di-cache untuk prevent stale pages

// Application Shell Assets - di-cache pertama kali dan jarang update
const SHELL_ASSETS = [
  '/',
  '/index.html',
  '/src/main.jsx',
  '/src/App.jsx',
  '/src/index.css',
  '/src/components/Navbar.jsx',
  '/src/components/Footer.jsx',
];

// Static Assets - tidak sering berubah
const STATIC_ASSETS = [
  '/src/assets/cofind.svg',
  '/src/assets/user.png',
];

// ============================================
// LIFECYCLE: INSTALLATION
// ============================================
self.addEventListener('install', (event) => {
  console.log('[Service Worker] Installing version', CACHE_VERSION);
  
  event.waitUntil(
    // Pre-cache shell assets terlebih dahulu untuk instant loading
    caches.open(CACHE_SHELL)
      .then((cache) => {
        console.log('[Service Worker] Pre-caching shell assets');
        return cache.addAll(SHELL_ASSETS).catch(err => {
          console.warn('[Service Worker] Some shell assets failed to cache:', err);
        });
      })
      .then(() => {
        // Pre-cache static assets
        return caches.open(CACHE_STATIC)
          .then((cache) => {
            console.log('[Service Worker] Pre-caching static assets');
            return cache.addAll(STATIC_ASSETS).catch(err => {
              console.warn('[Service Worker] Some static assets failed to cache:', err);
            });
          });
      })
      .then(() => {
        console.log('[Service Worker] Installation complete');
        return self.skipWaiting(); // Aktifkan segera
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
  console.log('[Service Worker] Activating version', CACHE_VERSION);
  
  // Daftar cache yang valid untuk versi ini (tidak boleh dihapus)
  const validCaches = [
    CACHE_SHELL,
    CACHE_STATIC,
    CACHE_CONTENT,
    // CACHE_PAGES dihapus - HTML pages tidak di-cache
  ];
  
  event.waitUntil(
    Promise.all([
      // Hapus cache lama - AGGRESSIVE CLEANUP
      caches.keys()
        .then((cacheNames) => {
          return Promise.all(
            cacheNames.map((cacheName) => {
              // Hapus cache lama yang bukan bagian dari versi ini
              if (cacheName.startsWith('cofind-') && !validCaches.includes(cacheName)) {
                console.log('[Service Worker] Removing old cache:', cacheName);
                return caches.delete(cacheName);
              }
              // Hapus cache dengan version lama (v1, v2, v3, v4, dll jika bukan v5)
              if (cacheName.startsWith('cofind-') && !cacheName.includes('v5')) {
                console.log('[Service Worker] Removing old version cache:', cacheName);
                return caches.delete(cacheName);
              }
              // Skip cache yang bukan cofind- atau cache valid untuk versi ini
              return Promise.resolve();
            })
          );
        }),
      // Claim clients tanpa reload
      self.clients.claim()
    ])
    .then(() => {
      console.log('[Service Worker] Activation complete');
      // Broadcast ke semua clients bahwa SW sudah aktif
      return self.clients.matchAll().then(clients => {
        clients.forEach(client => {
          client.postMessage({ type: 'SW_ACTIVATED', version: CACHE_VERSION });
        });
      });
    })
    .catch((error) => {
      console.error('[Service Worker] Error during activation:', error);
    })
  );
});

// ============================================
// EVENT: MESSAGE (Communication dengan App)
// ============================================
self.addEventListener('message', (event) => {
  console.log('[Service Worker] Message received:', event.data);
  
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  if (event.data && event.data.type === 'GET_VERSION') {
    event.ports[0].postMessage({ version: CACHE_VERSION });
  }
  
  // Cache management dari aplikasi
  if (event.data && event.data.type === 'CACHE_PUT') {
    handleCachePut(event.data);
  }
  
  if (event.data && event.data.type === 'CACHE_DELETE') {
    handleCacheDelete(event.data);
  }
  
  if (event.data && event.data.type === 'CACHE_CLEAR') {
    handleCacheClear(event.data);
  }
});

// Handler untuk menambah/memperbarui cache
async function handleCachePut(data) {
  const { url, responseData, cacheType = 'content' } = data;
  
  try {
    const cacheName = getCacheName(cacheType);
    const cache = await caches.open(cacheName);
    
    // Buat response object dari data
    const response = new Response(
      JSON.stringify(responseData),
      {
        headers: { 'Content-Type': 'application/json' },
        status: 200,
        statusText: 'OK'
      }
    );
    
    await cache.put(url, response);
    console.log('[Service Worker] Cache updated:', url);
    
    // Notify client
    const clients = await self.clients.matchAll();
    clients.forEach(client => {
      client.postMessage({ 
        type: 'CACHE_UPDATED', 
        url, 
        cacheType 
      });
    });
  } catch (error) {
    console.error('[Service Worker] Error caching data:', error);
  }
}

// Handler untuk menghapus item dari cache
async function handleCacheDelete(data) {
  const { url, cacheType } = data;
  
  try {
    const cacheName = getCacheName(cacheType);
    const cache = await caches.open(cacheName);
    await cache.delete(url);
    console.log('[Service Worker] Cache deleted:', url);
    
    // Notify client
    const clients = await self.clients.matchAll();
    clients.forEach(client => {
      client.postMessage({ 
        type: 'CACHE_DELETED', 
        url 
      });
    });
  } catch (error) {
    console.error('[Service Worker] Error deleting cache:', error);
  }
}

// Handler untuk clear semua cache
async function handleCacheClear(data) {
  const { cacheType } = data || {};
  
  try {
    if (cacheType) {
      // Clear specific cache type
      const cacheName = getCacheName(cacheType);
      await caches.delete(cacheName);
      console.log('[Service Worker] Cache cleared:', cacheType);
    } else {
      // Clear all caches
      const cacheNames = await caches.keys();
      await Promise.all(cacheNames.map(name => caches.delete(name)));
      console.log('[Service Worker] All caches cleared');
    }
    
    // Notify client
    const clients = await self.clients.matchAll();
    clients.forEach(client => {
      client.postMessage({ 
        type: 'CACHE_CLEARED', 
        cacheType: cacheType || 'all'
      });
    });
  } catch (error) {
    console.error('[Service Worker] Error clearing cache:', error);
  }
}

// Helper untuk mendapatkan nama cache
function getCacheName(type) {
  switch(type) {
    case 'shell': return CACHE_SHELL;
    case 'static': return CACHE_STATIC;
    case 'content': return CACHE_CONTENT;
    default: return CACHE_CONTENT;
  }
}

// ============================================
// EVENT: FETCH (Caching Strategy)
// ============================================
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);
  
  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }
  
  // Skip chrome-extension dan chrome:// requests
  if (url.protocol === 'chrome-extension:' || 
      url.protocol === 'chrome:') {
    return;
  }
  
  // Skip external image requests (Unsplash, dll) - biarkan browser handle langsung tanpa cache
  // Ini mencegah service worker terus-menerus load gambar dari network
  if (isExternalImageRequest(request)) {
    // Biarkan browser fetch langsung, tidak melalui service worker
    return;
  }
  
  // Routing berdasarkan tipe request
  // PRIORITY: API requests (Supabase, backend) - NEVER CACHE
  if (isAPIRequest(request)) {
    // NETWORK ONLY untuk API requests - NO CACHING
    // Ini termasuk Supabase API, backend API, dll
    event.respondWith(networkOnlyStrategy(request));
    return; // Exit early - jangan process lebih lanjut
  }
  
  // Static assets dan shell - boleh cache
  if (isShellAsset(request)) {
    // CACHE FIRST untuk shell (Navbar, Footer, App.jsx, CSS)
    event.respondWith(cacheFirstStrategy(request, CACHE_SHELL));
  } else if (isStaticAsset(request)) {
    // CACHE FIRST untuk static assets (images, fonts)
    event.respondWith(cacheFirstStrategy(request, CACHE_STATIC));
  } else if (isHTMLRequest(request)) {
    // NETWORK ONLY untuk HTML pages - TIDAK DI-CACHE untuk prevent stale pages
    // Ini memastikan /login dan semua routes selalu fresh
    event.respondWith(networkOnlyStrategyForHTML(request));
  } else {
    // Default: NETWORK FIRST (untuk dynamic content)
    event.respondWith(networkFirstStrategy(request, CACHE_CONTENT));
  }
});

// ============================================
// CACHING STRATEGIES
// ============================================

// CACHE FIRST: Cek cache dulu, jika tidak ada baru fetch dari network
async function cacheFirstStrategy(request, cacheName) {
  try {
    const cache = await caches.open(cacheName);
    const cachedResponse = await cache.match(request);
    
    if (cachedResponse) {
      console.log('[Service Worker] Cache First - Serving from cache:', request.url);
      return cachedResponse;
    }
    
    // Fetch dari network dan cache untuk next time
    const networkResponse = await fetch(request);
    
    if (networkResponse && networkResponse.status === 200) {
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    console.error('[Service Worker] Cache First error:', error);
    
    // Fallback: coba dari cache lain atau return error
    const fallbackCache = await caches.open(CACHE_CONTENT);
    const fallback = await fallbackCache.match(request);
    if (fallback) return fallback;
    
    return new Response('Network error', { 
      status: 408,
      headers: { 'Content-Type': 'text/plain' }
    });
  }
}

// NETWORK ONLY FOR HTML: Always fetch HTML pages from network, no caching
// Ini memastikan routes seperti /login selalu fresh dan tidak stale
async function networkOnlyStrategyForHTML(request) {
  try {
    console.log('[Service Worker] Network Only (HTML) - Fetching from network (NO CACHE):', request.url);
    
    // Create new request with aggressive cache-busting headers
    const cacheBustingHeaders = new Headers(request.headers);
    cacheBustingHeaders.set('Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0');
    cacheBustingHeaders.set('Pragma', 'no-cache');
    cacheBustingHeaders.set('Expires', '0');
    cacheBustingHeaders.set('If-Modified-Since', '0'); // Prevent 304 responses
    cacheBustingHeaders.set('If-None-Match', '*'); // Prevent 304 responses
    
    // Add cache-busting query parameter untuk HTML pages
    const url = new URL(request.url);
    url.searchParams.set('_html_t', Date.now().toString()); // HTML timestamp
    
    const cacheBustingRequest = new Request(url.toString(), {
      method: request.method,
      headers: cacheBustingHeaders,
      body: request.body,
      mode: request.mode,
      credentials: request.credentials,
      cache: 'no-store', // Force no cache
      redirect: request.redirect
    });
    
    const networkResponse = await fetch(cacheBustingRequest, {
      cache: 'no-store', // Double ensure no cache
      headers: cacheBustingHeaders
    });
    
    if (networkResponse && networkResponse.ok) {
      // Create new response with no-cache headers
      const responseHeaders = new Headers(networkResponse.headers);
      responseHeaders.set('Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0');
      responseHeaders.set('Pragma', 'no-cache');
      responseHeaders.set('Expires', '0');
      
      const noCacheResponse = new Response(networkResponse.body, {
        status: networkResponse.status,
        statusText: networkResponse.statusText,
        headers: responseHeaders
      });
      
      // CRITICAL: Don't cache HTML pages - always fetch fresh
      return noCacheResponse;
    }
    
    throw new Error('Network response not OK');
  } catch (error) {
    console.error('[Service Worker] Network Only (HTML) - Failed:', request.url, error);
    
    // Return error response - jangan fallback ke cache untuk HTML
    return new Response(
      '<!DOCTYPE html><html><head><title>Network Error</title></head><body><h1>Network Error</h1><p>Unable to load page. Please check your connection.</p><script>setTimeout(() => window.location.reload(), 2000);</script></body></html>',
      {
        status: 503,
        statusText: 'Service Unavailable',
        headers: { 
          'Content-Type': 'text/html',
          'Cache-Control': 'no-cache'
        }
      }
    );
  }
}

// NETWORK ONLY: Always fetch from network, no caching (for API requests)
async function networkOnlyStrategy(request) {
  try {
    console.log('[Service Worker] Network Only - Fetching from network (NO CACHE):', request.url);
    
    // Check if this is a Supabase request
    const url = new URL(request.url);
    const isSupabaseRequest = url.hostname.includes('supabase.co') || url.hostname.includes('supabase');
    
    if (isSupabaseRequest) {
      const networkResponse = await fetch(request);
      if (networkResponse && networkResponse.ok) {
        return networkResponse;
      }
      throw new Error('Network response not OK');
    }
    
    url.searchParams.set('_sw_t', Date.now().toString());
    const cacheBustingHeaders = new Headers(request.headers);
    cacheBustingHeaders.set('Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0');
    cacheBustingHeaders.set('Pragma', 'no-cache');
    cacheBustingHeaders.set('Expires', '0');
    cacheBustingHeaders.set('If-Modified-Since', '0');
    cacheBustingHeaders.set('If-None-Match', '*');
    
    const cacheBustingRequest = new Request(url.toString(), {
      method: request.method,
      headers: cacheBustingHeaders,
      body: request.body,
      mode: request.mode,
      credentials: request.credentials,
      cache: 'no-store',
      redirect: request.redirect
    });
    
    const networkResponse = await fetch(cacheBustingRequest, {
      cache: 'no-store',
      headers: cacheBustingHeaders
    });
    
    if (networkResponse && networkResponse.ok) {
      // Create new response with no-cache headers
      const responseHeaders = new Headers(networkResponse.headers);
      responseHeaders.set('Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0');
      responseHeaders.set('Pragma', 'no-cache');
      responseHeaders.set('Expires', '0');
      
      const noCacheResponse = new Response(networkResponse.body, {
        status: networkResponse.status,
        statusText: networkResponse.statusText,
        headers: responseHeaders
      });
      
      // CRITICAL: Don't cache this response
      return noCacheResponse;
    }
    
    throw new Error('Network response not OK');
  } catch (error) {
    console.error('[Service Worker] Network Only - Failed:', request.url, error);
    
    // Return error response without cache fallback
    return new Response(
      JSON.stringify({ 
        error: 'Network Error', 
        message: 'Unable to fetch data from server. Please check your connection and ensure the backend is running.',
        details: {
          url: request.url,
          timestamp: new Date().toISOString(),
          suggestion: 'Check if the backend server is running at ' + new URL(request.url).origin
        }
      }),
      {
        status: 503,
        statusText: 'Service Unavailable',
        headers: { 
          'Content-Type': 'application/json',
          'Cache-Control': 'no-cache'
        }
      }
    );
  }
}

// NETWORK FIRST: Fetch dari network dulu, jika gagal baru pakai cache
async function networkFirstStrategy(request, cacheName) {
  try {
    const cache = await caches.open(cacheName);
    
    // Coba fetch dari network dengan timeout
    const networkResponse = await Promise.race([
      fetch(request),
      new Promise((_, reject) => 
        setTimeout(() => reject(new Error('Network timeout')), 3000)
      )
    ]);
    
    if (networkResponse && networkResponse.status === 200) {
      // Update cache dengan response terbaru
      cache.put(request, networkResponse.clone());
      console.log('[Service Worker] Network First - Serving from network:', request.url);
      return networkResponse;
    }
    
    throw new Error('Network response not OK');
  } catch (error) {
    console.log('[Service Worker] Network First - Network failed, trying cache:', request.url, error.message);
    
    // Fallback ke cache
    const cache = await caches.open(cacheName);
    const cachedResponse = await cache.match(request);
    
    if (cachedResponse) {
      console.log('[Service Worker] Network First - Serving from cache:', request.url);
      return cachedResponse;
    }
    
    // Jika tidak ada di cache juga, return error response yang lebih informatif
    return new Response(
      JSON.stringify({ 
        error: 'Offline', 
        message: 'Server tidak dapat diakses dan tidak ada data tersimpan. Pastikan server backend berjalan.',
        details: {
          url: request.url,
          timestamp: new Date().toISOString(),
          suggestion: 'Periksa apakah server backend berjalan di ' + new URL(request.url).origin
        }
      }),
      {
        status: 503,
        statusText: 'Service Unavailable',
        headers: { 
          'Content-Type': 'application/json',
          'Cache-Control': 'no-cache'
        }
      }
    );
  }
}

// ============================================
// HELPER FUNCTIONS
// ============================================

function isShellAsset(request) {
  const url = request.url;
  return url.includes('/src/App.jsx') ||
         url.includes('/src/main.jsx') ||
         url.includes('/src/components/Navbar') ||
         url.includes('/src/components/Footer') ||
         url.includes('/src/index.css') ||
         url === self.location.origin + '/' ||
         url === self.location.origin + '/index.html';
}

function isStaticAsset(request) {
  const url = request.url;
  return url.includes('/src/assets/') ||
         url.includes('.svg') ||
         url.includes('.png') ||
         url.includes('.jpg') ||
         url.includes('.jpeg') ||
         url.includes('.gif') ||
         url.includes('.woff') ||
         url.includes('.woff2');
}

function isAPIRequest(request) {
  const url = new URL(request.url);
  
  // Backend API requests
  if (url.pathname.startsWith('/api/')) {
    return true;
  }
  
  // Supabase API requests - NEVER CACHE
  if (url.hostname.includes('supabase.co') || 
      url.hostname.includes('supabase')) {
    return true;
  }
  
  // External API requests
  if (url.hostname !== self.location.hostname) {
    return true;
  }
  
  return false;
}

function isHTMLRequest(request) {
  return request.headers.get('accept')?.includes('text/html');
}

function isExternalImageRequest(request) {
  const url = request.url;
  // Skip Unsplash dan external image CDNs
  return url.includes('source.unsplash.com') ||
         url.includes('images.unsplash.com') ||
         url.includes('unsplash.com') ||
         (url.startsWith('http') && 
          !url.startsWith(self.location.origin) && 
          (request.headers.get('accept')?.includes('image/') || 
           url.match(/\.(jpg|jpeg|png|gif|webp|svg)$/i)));
}

// ============================================
// EVENT: PUSH (Push Notifications)
// ============================================
self.addEventListener('push', (event) => {
  console.log('[Service Worker] Push notification received:', event);
  
  let notificationData = {
    title: 'Cofind',
    body: 'Anda memiliki notifikasi baru',
    icon: '/cofind.svg',
    badge: '/cofind.svg',
    tag: 'cofind-notification',
    requireInteraction: false,
  };
  
  if (event.data) {
    try {
      const data = event.data.json();
      notificationData = {
        ...notificationData,
        ...data,
      };
    } catch (error) {
      console.warn('[Service Worker] Failed to parse push data:', error);
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
        { action: 'open', title: 'Buka Aplikasi' },
        { action: 'close', title: 'Tutup' },
      ],
    })
  );
});

// ============================================
// EVENT: SYNC (Background Sync)
// ============================================
self.addEventListener('sync', (event) => {
  console.log('[Service Worker] Background sync event:', event.tag);
  
  if (event.tag === 'sync-offline-data') {
    event.waitUntil(syncOfflineData());
  }
  
  if (event.tag === 'sync-favorites') {
    event.waitUntil(syncFavorites());
  }
});

async function syncOfflineData() {
  try {
    console.log('[Service Worker] Syncing offline data...');
    const cache = await caches.open(CACHE_CONTENT);
    const keys = await cache.keys();
    console.log('[Service Worker] Found', keys.length, 'items to sync');
    return Promise.resolve();
  } catch (error) {
    console.error('[Service Worker] Error syncing offline data:', error);
    return Promise.reject(error);
  }
}

async function syncFavorites() {
  try {
    console.log('[Service Worker] Syncing favorites...');
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
  
  // Open window menggunakan self.clients
  const openApp = () => {
    return self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        // Jika ada window yang sudah terbuka, focus ke window tersebut
        for (let i = 0; i < clientList.length; i++) {
          const client = clientList[i];
          if (client.url === '/' && 'focus' in client) {
            return client.focus();
          }
        }
        // Jika tidak ada window terbuka, buka window baru
        if (self.clients.openWindow) {
          return self.clients.openWindow('/');
        }
      });
  };
  
  if (event.action === 'open' || !event.action) {
    event.waitUntil(openApp());
  }
});

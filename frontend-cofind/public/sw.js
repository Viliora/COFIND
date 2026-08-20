// Service Worker untuk Cofind dengan Optimized Caching Strategy
// UPDATE CACHE VERSION SETIAP KALI ADA PERUBAHAN PENTING
const CACHE_VERSION = 'cofind-v9';
const CACHE_SHELL = 'cofind-shell-v9';    // JS/CSS chunks (bukan HTML)
const CACHE_STATIC = 'cofind-static-v9';  // Images, fonts, dll
// HTML, API, dan data dinamis: network only — tidak di-cache di klien.

// Application Shell Assets - HANYA static assets, bukan HTML pages
// HTML pages harus SELALU fresh untuk session persistence
const SHELL_ASSETS = [
  // Static JS chunks (built dengan hash di filename)
  // Auto-discovered saat build (entry-[hash].js, chunk-[hash].js)
  
  // Static CSS
  // Auto-discovered dari HTML

  // Note: /index.html dan / TIDAK di-cache untuk prevent stale pages with wrong session
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
  
  // Hanya aset tampilan yang boleh dipertahankan.
  const validCaches = [
    CACHE_SHELL,
    CACHE_STATIC,
  ];
  
  event.waitUntil(
    Promise.all([
      caches.keys()
        .then((cacheNames) => {
          return Promise.all(
            cacheNames.map((cacheName) => {
              if (cacheName.startsWith('cofind-') && !validCaches.includes(cacheName)) {
                console.log('[Service Worker] Removing unused/old cache:', cacheName);
                return caches.delete(cacheName);
              }
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
});

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
    // Request yang tidak dikenali: jangan di-cache (bisa data dinamis).
    event.respondWith(networkOnlyStrategy(request));
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
    return new Response('Network error', { 
      status: 408,
      headers: { 'Content-Type': 'text/plain' }
    });
  }
}

// NETWORK ONLY FOR HTML: Always fetch HTML pages from network, no caching
// Untuk SPA deep-link (/shop/:id, dll.) fallback ke index.html agar React Router bisa handle.
async function networkOnlyStrategyForHTML(request) {
  const acceptHtml = (request.headers.get('accept') || '').includes('text/html');
  const isNavigation = request.mode === 'navigate' || acceptHtml;

  const withNoCacheHeaders = (response) => {
    const responseHeaders = new Headers(response.headers);
    responseHeaders.set('Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0');
    responseHeaders.set('Pragma', 'no-cache');
    responseHeaders.set('Expires', '0');
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  };

  const fetchSpaShell = async () => {
    // Ambil shell SPA tanpa mengubah path browser (React Router baca URL asli).
    const candidates = ['/index.html', '/'];
    for (const path of candidates) {
      try {
        const resp = await fetch(new Request(path, {
          method: 'GET',
          headers: { Accept: 'text/html' },
          cache: 'no-store',
        }));
        if (resp && resp.ok) {
          console.log('[Service Worker] SPA shell fallback:', path, 'for', request.url);
          return withNoCacheHeaders(resp);
        }
      } catch (err) {
        console.warn('[Service Worker] SPA shell fetch failed:', path, err);
      }
    }
    return null;
  };

  try {
    console.log('[Service Worker] Network Only (HTML):', request.url);

    // Jangan manipulasi URL/header agresif — itu sering memecah navigasi "Open in new tab".
    const networkResponse = await fetch(request, { cache: 'no-store' });

    if (networkResponse && networkResponse.ok) {
      return withNoCacheHeaders(networkResponse);
    }

    // Deep link tanpa rewrite hosting biasanya 404 → fallback shell SPA.
    if (isNavigation && networkResponse && (networkResponse.status === 404 || networkResponse.status >= 500)) {
      const shell = await fetchSpaShell();
      if (shell) return shell;
    }

    throw new Error(`Network response not OK (${networkResponse && networkResponse.status})`);
  } catch (error) {
    console.error('[Service Worker] Network Only (HTML) - Failed:', request.url, error);

    if (isNavigation) {
      const shell = await fetchSpaShell();
      if (shell) return shell;
    }

    return new Response(
      '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Cofind</title></head><body><p>Tidak dapat memuat halaman. <a href="/">Kembali ke beranda</a>.</p></body></html>',
      {
        status: 503,
        statusText: 'Service Unavailable',
        headers: {
          'Content-Type': 'text/html; charset=utf-8',
          'Cache-Control': 'no-cache',
        },
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
    
    // Cache-bust via query only — jangan set If-None-Match / Cache-Control di request
    // (header non-simple memicu CORS preflight yang sering gagal ke backend cross-origin).
    url.searchParams.set('_sw_t', Date.now().toString());
    const cacheBustingRequest = new Request(url.toString(), {
      method: request.method,
      headers: request.headers,
      body: request.body,
      mode: request.mode,
      credentials: request.credentials,
      cache: 'no-store',
      redirect: request.redirect
    });
    
    const networkResponse = await fetch(cacheBustingRequest, { cache: 'no-store' });
    
    if (networkResponse && networkResponse.ok) {
      // CRITICAL: Don't cache this response — return as-is
      return networkResponse;
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

// ============================================
// HELPER FUNCTIONS
// ============================================

function isShellAsset(request) {
  const url = request.url;
  // Static JS chunks (built dengan hash, tidak include HTML)
  return url.includes('.js') && !url.includes('.html') ||
         url.includes('.css') ||
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
  const url = new URL(request.url);
  const accept = request.headers.get('accept') || '';
  const pathname = url.pathname;
  
  // Check if this is an HTML page request
  return (
    // Browser requesting HTML pages
    accept.includes('text/html') ||
    // Any .html files
    pathname.endsWith('.html') ||
    // Routes (no extension = HTML page)
    (!pathname.includes('.') && pathname !== '/api' && !pathname.startsWith('/api/'))
  );
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

// Utility untuk mendaftarkan Service Worker

/**
 * Mendaftarkan Service Worker dengan penanganan lifecycle
 * Di development mode, Service Worker di-disable untuk memungkinkan HMR bekerja dengan baik
 */
export function registerServiceWorker() {
  // Cek apakah ini development mode (Vite development server)
  // Gunakan import.meta.env.DEV sebagai sumber utama kebenaran
  // Fallback ke hostname check hanya jika env tidak tersedia
  const isDevelopment = import.meta.env.DEV || 
                       window.location.hostname === 'localhost' || 
                       window.location.hostname === '127.0.0.1' ||
                       window.location.hostname === '[::1]';

  // Di development mode, unregister service worker yang ada dan tidak register yang baru
  // Ini memungkinkan Hot Module Replacement (HMR) bekerja tanpa refresh
  if (isDevelopment) {
    console.log('[SW Register] Development mode detected - Service Worker disabled untuk HMR');
    
    // Aggressively unregister service worker yang mungkin sudah terdaftar
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.getRegistrations().then((registrations) => {
        registrations.forEach((registration) => {
          registration.unregister().then((success) => {
            if (success) {
              console.log('[SW Register] Service Worker unregistered untuk development mode');
            }
          });
        });
      });

      // Aggressively clear semua cache yang mungkin ada
      if ('caches' in window) {
        caches.keys().then((cacheNames) => {
          return Promise.all(
            cacheNames.map((cacheName) => {
              console.log('[SW Register] Clearing cache:', cacheName);
              return caches.delete(cacheName);
            })
          );
        }).then(() => {
          console.log('[SW Register] All caches cleared for development mode');
        });
      }
      
      // Clear browser cache headers by adding cache-busting
      // This is handled by Vite dev server, but we ensure it here
      if (window.location.search.indexOf('_sw_skip') === -1) {
        // Add query param to force fresh load
        const url = new URL(window.location);
        url.searchParams.set('_sw_skip', '1');
        // Don't reload automatically - let user do it if needed
      }
    }
    return; // Exit early - tidak register service worker di development
  }

  // Production mode: Register Service Worker seperti biasa
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker
        .register('/sw.js')
        .then((registration) => {
          console.log('[SW Register] Service Worker berhasil didaftarkan:', registration.scope);

          // Track lifecycle events
          trackServiceWorkerLifecycle(registration);

          return registration;
        })
        .catch((error) => {
          console.error('[SW Register] Gagal mendaftarkan Service Worker:', error);
        });
    });

    // Listen untuk service worker updates
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      console.log('[SW Register] Service Worker controller changed');
      // Di production, bisa auto-reload atau tampilkan notification
      // Untuk development, jangan auto-reload karena HMR sudah handle
    });
  } else {
    console.warn('[SW Register] Browser tidak mendukung Service Worker');
  }
}

/**
 * Track lifecycle events dari Service Worker
 */
function trackServiceWorkerLifecycle(registration) {
  // Installed state
  registration.addEventListener('updatefound', () => {
    const newWorker = registration.installing;
    console.log('[SW Lifecycle] Service Worker baru ditemukan');

    newWorker.addEventListener('statechange', () => {
      switch (newWorker.state) {
        case 'installed':
          if (navigator.serviceWorker.controller) {
            console.log('[SW Lifecycle] Service Worker baru tersedia (update)');
            // Bisa menampilkan notifikasi ke user untuk update
            showUpdateAvailableNotification();
          } else {
            console.log('[SW Lifecycle] Service Worker terpasang untuk pertama kali');
          }
          break;
        case 'activating':
          console.log('[SW Lifecycle] Service Worker sedang mengaktifkan...');
          break;
        case 'activated':
          console.log('[SW Lifecycle] Service Worker telah aktif');
          break;
        case 'redundant':
          console.log('[SW Lifecycle] Service Worker menjadi redundant');
          break;
      }
    });
  });

  // Periodic update check (hanya di production)
  const isDevelopment = import.meta.env.DEV || 
                       window.location.hostname === 'localhost' || 
                       window.location.hostname === '127.0.0.1' ||
                       window.location.hostname === '[::1]';

  if (!isDevelopment) {
    setInterval(() => {
      registration.update();
    }, 60000); // Check setiap 1 menit di production
  }
}

/**
 * Menampilkan notifikasi ketika update tersedia
 * Di development mode, tidak menampilkan notifikasi karena HMR sudah handle update
 */
function showUpdateAvailableNotification() {
  const isDevelopment = import.meta.env.DEV || 
                       window.location.hostname === 'localhost' || 
                       window.location.hostname === '127.0.0.1' ||
                       window.location.hostname === '[::1]';

  // Skip notification di development mode
  if (isDevelopment) {
    console.log('[SW Register] Update available (development mode - HMR will handle)');
    return;
  }

  // Di production, tampilkan notifikasi untuk reload
  // Bisa diganti dengan UI notification yang lebih baik
  if (window.confirm('Versi baru aplikasi tersedia. Reload halaman?')) {
    window.location.reload();
  }
}

/**
 * Unregister Service Worker (untuk development/debugging)
 */
export function unregisterServiceWorker() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.ready
      .then((registration) => {
        registration.unregister();
        console.log('[SW Register] Service Worker di-unregister');
      })
      .catch((error) => {
        console.error('[SW Register] Error unregistering Service Worker:', error);
      });
  }
}

/**
 * Request permission untuk push notifications
 */
export async function requestPushPermission() {
  if ('Notification' in window && 'serviceWorker' in navigator) {
    try {
      const permission = await Notification.requestPermission();
      console.log('[SW Register] Push permission:', permission);
      return permission;
    } catch (error) {
      console.error('[SW Register] Error requesting push permission:', error);
      return 'denied';
    }
  }
  return 'unsupported';
}

/**
 * Trigger background sync
 */
export async function triggerBackgroundSync(tag = 'sync-offline-data') {
  if ('serviceWorker' in navigator) {
    try {
      const registration = await navigator.serviceWorker.ready;
      if ('sync' in registration) {
        await registration.sync.register(tag);
        console.log('[SW Register] Background sync registered:', tag);
        return true;
      } else {
        console.warn('[SW Register] Background sync tidak didukung di browser ini');
        return false;
      }
    } catch (error) {
      console.error('[SW Register] Error registering background sync:', error);
      return false;
    }
  }
  console.warn('[SW Register] Service Worker tidak didukung');
  return false;
}


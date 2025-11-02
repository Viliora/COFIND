// Utility untuk mendaftarkan Service Worker

/**
 * Mendaftarkan Service Worker dengan penanganan lifecycle
 */
export function registerServiceWorker() {
  // Cek apakah browser mendukung Service Worker
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
      window.location.reload();
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

  // Periodic update check
  setInterval(() => {
    registration.update();
  }, 60000); // Check setiap 1 menit
}

/**
 * Menampilkan notifikasi ketika update tersedia
 */
function showUpdateAvailableNotification() {
  // Di sini Anda bisa menampilkan UI notification ke user
  // untuk meminta mereka reload halaman
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


/**
 * Storage Cleanup Utility
 * 
 * Membersihkan data localStorage yang basi atau corrupt
 */

// Current app version
const CURRENT_APP_VERSION = '1.0.0';
const APP_VERSION_KEY = 'cofind_app_version';

// Maximum cache age (7 days)
const MAX_CACHE_AGE = 7 * 24 * 60 * 60 * 1000;

/**
 * Bersihkan data cache yang basi
 */
export function cleanupStaleData() {
  if (typeof window === 'undefined' || !window.localStorage) {
    return;
  }

  try {
    const keys = Object.keys(localStorage);
    let cleanedCount = 0;

    for (const key of keys) {
      // Hapus cache lama
      if (key.startsWith('cache_') || key.startsWith('temp_')) {
        try {
          const value = localStorage.getItem(key);
          const parsed = JSON.parse(value);
          
          if (parsed?.timestamp) {
            const age = Date.now() - parsed.timestamp;
            if (age > MAX_CACHE_AGE) {
              localStorage.removeItem(key);
              cleanedCount++;
            }
          }
        } catch (e) {
          // Bukan cache dengan timestamp
        }
      }
    }

    if (cleanedCount > 0) {
      console.log(`[StorageCleanup] Removed ${cleanedCount} stale cache items`);
    }
  } catch (error) {
    console.warn('[StorageCleanup] Error:', error);
  }
}

/**
 * Cek versi app
 */
export function checkAppVersion() {
  if (typeof window === 'undefined' || !window.localStorage) {
    return false;
  }

  try {
    const storedVersion = localStorage.getItem(APP_VERSION_KEY);
    
    if (!storedVersion || storedVersion !== CURRENT_APP_VERSION) {
      localStorage.setItem(APP_VERSION_KEY, CURRENT_APP_VERSION);
      return !storedVersion ? false : true; // True jika versi berubah
    }

    return false;
  } catch (error) {
    return false;
  }
}

/**
 * Bersihkan JSON yang corrupt
 */
export function cleanupCorruptedData() {
  if (typeof window === 'undefined' || !window.localStorage) {
    return;
  }

  try {
    const keys = Object.keys(localStorage);

    for (const key of keys) {
      try {
        const value = localStorage.getItem(key);
        
        if (value === null || value === undefined) {
          localStorage.removeItem(key);
          continue;
        }

        // Coba parse JSON jika terlihat seperti JSON
        if (value.startsWith('{') || value.startsWith('[')) {
          JSON.parse(value);
        }
      } catch (e) {
        // JSON corrupt, hapus
        localStorage.removeItem(key);
      }
    }
  } catch (error) {
    console.warn('[StorageCleanup] Error:', error);
  }
}

/**
 * Validasi Supabase session
 */
export async function validateSupabaseSession(supabase) {
  if (!supabase) {
    return false;
  }

  try {
    const { data: { session }, error } = await supabase.auth.getSession();

    if (error || !session) {
      return false;
    }

    // Cek apakah session expired
    const expiresAt = session.expires_at ? session.expires_at * 1000 : null;
    if (expiresAt && expiresAt < Date.now()) {
      await supabase.auth.signOut();
      return false;
    }

    return true;
  } catch (error) {
    return false;
  }
}

/**
 * Full cleanup routine - dipanggil saat app init (opsional)
 */
export async function performFullCleanup(supabase) {
  checkAppVersion();
  cleanupCorruptedData();
  cleanupStaleData();
  
  if (supabase) {
    await validateSupabaseSession(supabase);
  }
}

/**
 * Emergency cleanup - clear semua kecuali theme
 */
export function emergencyCleanup() {
  if (typeof window === 'undefined' || !window.localStorage) {
    return;
  }

  try {
    const theme = localStorage.getItem('theme-dark');
    localStorage.clear();
    
    if (theme !== null) {
      localStorage.setItem('theme-dark', theme);
    }
    
    localStorage.setItem(APP_VERSION_KEY, CURRENT_APP_VERSION);
    window.location.reload();
  } catch (error) {
    console.error('[StorageCleanup] Emergency cleanup failed:', error);
  }
}

/**
 * Get storage info untuk debugging
 */
export function getStorageInfo() {
  if (typeof window === 'undefined' || !window.localStorage) {
    return { available: false };
  }

  try {
    const keys = Object.keys(localStorage);
    const totalSize = keys.reduce((acc, key) => {
      const value = localStorage.getItem(key);
      return acc + (value ? value.length : 0);
    }, 0);

    return {
      available: true,
      keyCount: keys.length,
      totalSizeKB: Math.round(totalSize / 1024),
      keys: keys
    };
  } catch (error) {
    return { available: true, error: error.message };
  }
}

export default {
  cleanupStaleData,
  checkAppVersion,
  cleanupCorruptedData,
  validateSupabaseSession,
  performFullCleanup,
  emergencyCleanup,
  getStorageInfo
};

/**
 * Storage Cleanup Utility
 * 
 * Automatically cleans up stale, corrupted, or outdated localStorage data
 * to prevent app malfunction and weird behavior.
 * 
 * This fixes the issue where users need to manually logout + hard reload
 * or clear localStorage to make the app work again.
 */

// Current app version - increment this when localStorage schema changes
const CURRENT_APP_VERSION = '1.0.0';
const APP_VERSION_KEY = 'cofind_app_version';

// Keys that should be cleaned up
const STALE_KEYS_PATTERNS = [
  /^cofind_migrated_/,  // Old migration flags
  /^sb-.*-auth-token/,  // Old Supabase session tokens
  /^supabase\.auth\./,  // Old Supabase auth keys
];

// Maximum age for cached data (7 days)
const MAX_CACHE_AGE = 7 * 24 * 60 * 60 * 1000; // 7 days in milliseconds

/**
 * Clean up stale localStorage data
 */
export function cleanupStaleData() {
  if (typeof window === 'undefined' || !window.localStorage) {
    console.warn('[StorageCleanup] localStorage not available');
    return;
  }

  try {
    console.log('[StorageCleanup] 🧹 Starting cleanup...');
    let cleanedCount = 0;

    // Get all localStorage keys
    const keys = Object.keys(localStorage);
    
    for (const key of keys) {
      let shouldDelete = false;

      // Check if key matches stale patterns
      for (const pattern of STALE_KEYS_PATTERNS) {
        if (pattern.test(key)) {
          shouldDelete = true;
          break;
        }
      }

      // Check for old cached data with timestamps
      if (key.startsWith('cache_') || key.startsWith('temp_')) {
        try {
          const value = localStorage.getItem(key);
          const parsed = JSON.parse(value);
          
          if (parsed && parsed.timestamp) {
            const age = Date.now() - parsed.timestamp;
            if (age > MAX_CACHE_AGE) {
              shouldDelete = true;
              console.log(`[StorageCleanup] 🗑️ Removing old cache: ${key} (age: ${Math.round(age / 1000 / 60 / 60 / 24)} days)`);
            }
          }
        } catch (e) {
          // Not a timestamped cache, skip
        }
      }

      // Delete if marked
      if (shouldDelete) {
        try {
          localStorage.removeItem(key);
          cleanedCount++;
          console.log(`[StorageCleanup] 🗑️ Removed stale key: ${key}`);
        } catch (e) {
          console.warn(`[StorageCleanup] ⚠️ Failed to remove key: ${key}`, e);
        }
      }
    }

    if (cleanedCount > 0) {
      console.log(`[StorageCleanup] ✅ Cleanup complete! Removed ${cleanedCount} stale items`);
    } else {
      console.log('[StorageCleanup] ✅ No stale data found');
    }
  } catch (error) {
    console.error('[StorageCleanup] ❌ Error during cleanup:', error);
  }
}

/**
 * Check and migrate app version
 * Returns true if app version changed (requires cleanup)
 */
export function checkAppVersion() {
  if (typeof window === 'undefined' || !window.localStorage) {
    return false;
  }

  try {
    const storedVersion = localStorage.getItem(APP_VERSION_KEY);
    
    if (!storedVersion) {
      // First run - set version
      console.log('[StorageCleanup] 🆕 First run - setting app version:', CURRENT_APP_VERSION);
      localStorage.setItem(APP_VERSION_KEY, CURRENT_APP_VERSION);
      return false;
    }

    if (storedVersion !== CURRENT_APP_VERSION) {
      // Version changed - cleanup needed
      console.log('[StorageCleanup] 🔄 App version changed:', storedVersion, '→', CURRENT_APP_VERSION);
      localStorage.setItem(APP_VERSION_KEY, CURRENT_APP_VERSION);
      return true;
    }

    return false;
  } catch (error) {
    console.error('[StorageCleanup] ❌ Error checking app version:', error);
    return false;
  }
}

/**
 * Clean up corrupted data by key patterns
 */
export function cleanupCorruptedData() {
  if (typeof window === 'undefined' || !window.localStorage) {
    return;
  }

  try {
    const keys = Object.keys(localStorage);
    let cleanedCount = 0;

    for (const key of keys) {
      try {
        const value = localStorage.getItem(key);
        
        // Skip null/undefined
        if (value === null || value === undefined) {
          localStorage.removeItem(key);
          cleanedCount++;
          continue;
        }

        // Skip non-JSON keys (like theme-dark)
        if (!value.startsWith('{') && !value.startsWith('[')) {
          continue;
        }

        // Try to parse JSON - if it fails, it's corrupted
        JSON.parse(value);
      } catch (e) {
        // Corrupted JSON - remove it
        console.warn(`[StorageCleanup] 🗑️ Removing corrupted data: ${key}`);
        localStorage.removeItem(key);
        cleanedCount++;
      }
    }

    if (cleanedCount > 0) {
      console.log(`[StorageCleanup] ✅ Removed ${cleanedCount} corrupted items`);
    }
  } catch (error) {
    console.error('[StorageCleanup] ❌ Error cleaning corrupted data:', error);
  }
}

/**
 * Validate Supabase session
 * Returns true if session is valid, false if expired/corrupted
 */
export async function validateSupabaseSession(supabase) {
  if (!supabase) {
    return false;
  }

  try {
    // Get current session
    const { data: { session }, error } = await supabase.auth.getSession();

    if (error) {
      console.warn('[StorageCleanup] ⚠️ Session validation error:', error);
      return false;
    }

    if (!session) {
      console.log('[StorageCleanup] ℹ️ No active session');
      return false;
    }

    // Check if session is expired
    const expiresAt = session.expires_at ? session.expires_at * 1000 : null;
    if (expiresAt && expiresAt < Date.now()) {
      console.warn('[StorageCleanup] ⚠️ Session expired');
      
      // Clear expired session
      await supabase.auth.signOut();
      return false;
    }

    // Session is valid
    console.log('[StorageCleanup] ✅ Session is valid');
    return true;
  } catch (error) {
    console.error('[StorageCleanup] ❌ Error validating session:', error);
    return false;
  }
}

/**
 * Full cleanup routine
 * Should be called on app initialization
 */
export async function performFullCleanup(supabase) {
  console.log('[StorageCleanup] 🚀 Starting full cleanup routine...');

  // 1. Check app version
  const versionChanged = checkAppVersion();
  if (versionChanged) {
    console.log('[StorageCleanup] 🔄 Version changed - performing deep clean');
    cleanupStaleData();
  }

  // 2. Clean corrupted data
  cleanupCorruptedData();

  // 3. Clean stale data (always)
  cleanupStaleData();

  // 4. Validate session
  if (supabase) {
    const sessionValid = await validateSupabaseSession(supabase);
    if (!sessionValid) {
      console.log('[StorageCleanup] 🔒 Invalid session - clearing auth data');
      // Session will be cleared by signOut in validateSupabaseSession
    }
  }

  console.log('[StorageCleanup] ✅ Full cleanup complete!');
}

/**
 * Emergency cleanup - clears everything except theme
 * Use this as a last resort
 */
export function emergencyCleanup() {
  if (typeof window === 'undefined' || !window.localStorage) {
    return;
  }

  try {
    console.warn('[StorageCleanup] 🚨 EMERGENCY CLEANUP - Clearing all data except theme!');
    
    // Save theme before clearing
    const theme = localStorage.getItem('theme-dark');
    
    // Clear everything
    localStorage.clear();
    
    // Restore theme
    if (theme !== null) {
      localStorage.setItem('theme-dark', theme);
    }
    
    // Set app version
    localStorage.setItem(APP_VERSION_KEY, CURRENT_APP_VERSION);
    
    console.log('[StorageCleanup] ✅ Emergency cleanup complete - page will reload');
    
    // Reload page to reset state
    window.location.reload();
  } catch (error) {
    console.error('[StorageCleanup] ❌ Emergency cleanup failed:', error);
  }
}

/**
 * Get storage info for debugging
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
      keys: keys,
      version: localStorage.getItem(APP_VERSION_KEY) || 'unknown'
    };
  } catch (error) {
    console.error('[StorageCleanup] Error getting storage info:', error);
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


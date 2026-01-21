/**
 * Storage Cleanup Utility - Local version without Supabase
 * Manages localStorage cleanup for the application
 */

/**
 * Get storage information
 */
export function getStorageInfo() {
  try {
    let totalSize = 0;
    let keyCount = 0;

    for (let key in localStorage) {
      if (localStorage.hasOwnProperty(key)) {
        const value = localStorage.getItem(key);
        if (value) {
          totalSize += key.length + value.length;
          keyCount++;
        }
      }
    }

    return {
      available: true,
      keyCount,
      totalSizeKB: (totalSize / 1024).toFixed(2),
      version: 'v1.0'
    };
  } catch (error) {
    console.error('[Storage] Error getting storage info:', error);
    return {
      available: false,
      keyCount: 0,
      totalSizeKB: 0,
      version: 'unknown'
    };
  }
}

/**
 * Emergency cleanup - clears all localStorage except theme
 */
export function emergencyCleanup() {
  try {
    console.log('[Storage] Starting emergency cleanup...');
    
    // Save theme preference if it exists
    const theme = localStorage.getItem('theme');
    
    // Clear all localStorage
    localStorage.clear();
    
    // Restore theme
    if (theme) {
      localStorage.setItem('theme', theme);
    }
    
    console.log('[Storage] Emergency cleanup complete');
    
    // Reload page to reset app state
    window.location.reload();
  } catch (error) {
    console.error('[Storage] Error during emergency cleanup:', error);
    // Force reload anyway
    window.location.reload();
  }
}

/**
 * Clear specific cache types
 */
export function clearCache(cacheType = 'all') {
  try {
    console.log(`[Storage] Clearing cache: ${cacheType}`);
    
    const keysToDelete = [];
    
    for (let key in localStorage) {
      if (localStorage.hasOwnProperty(key)) {
        let shouldDelete = false;
        
        switch (cacheType) {
          case 'auth':
            shouldDelete = key.includes('auth') || key.includes('token') || key.includes('session');
            break;
          case 'images':
            shouldDelete = key.includes('image') || key.includes('photo');
            break;
          case 'reviews':
            shouldDelete = key.includes('review');
            break;
          case 'favorites':
            shouldDelete = key.includes('favorite') || key.includes('want_to_visit');
            break;
          case 'all':
            shouldDelete = key !== 'theme'; // Keep theme
            break;
          default:
            shouldDelete = false;
        }
        
        if (shouldDelete) {
          keysToDelete.push(key);
        }
      }
    }
    
    keysToDelete.forEach(key => localStorage.removeItem(key));
    
    console.log(`[Storage] Cleared ${keysToDelete.length} cache entries`);
    return keysToDelete.length;
  } catch (error) {
    console.error('[Storage] Error clearing cache:', error);
    return 0;
  }
}

/**
 * Clean up old/expired cache entries
 */
export function cleanupOldCache() {
  try {
    console.log('[Storage] Cleaning up old cache...');
    
    const now = Date.now();
    const keysToDelete = [];
    
    for (let key in localStorage) {
      if (localStorage.hasOwnProperty(key)) {
        try {
          const value = localStorage.getItem(key);
          if (!value) continue;
          
          // Try to parse as JSON to check for timestamp
          const data = JSON.parse(value);
          if (data && data.timestamp) {
            const age = now - data.timestamp;
            const maxAge = 7 * 24 * 60 * 60 * 1000; // 7 days
            
            if (age > maxAge) {
              keysToDelete.push(key);
            }
          }
        } catch {
          // Not JSON or no timestamp, skip
          continue;
        }
      }
    }
    
    keysToDelete.forEach(key => localStorage.removeItem(key));
    
    console.log(`[Storage] Cleaned up ${keysToDelete.length} old cache entries`);
    return keysToDelete.length;
  } catch (error) {
    console.error('[Storage] Error cleaning up old cache:', error);
    return 0;
  }
}

export default {
  getStorageInfo,
  emergencyCleanup,
  clearCache,
  cleanupOldCache
};

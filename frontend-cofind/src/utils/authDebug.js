/**
 * Utility functions untuk debugging authentication dan session management
 * 
 * Usage:
 * import { checkAuthState, checkStorage, clearAllSessions } from '../utils/authDebug';
 * 
 * // Di browser console atau component
 * checkAuthState();
 * checkStorage();
 * clearAllSessions(); // Emergency clear
 */

/**
 * Check current authentication state
 * @returns {Object} Auth state information
 */
export const checkAuthState = () => {
  const state = {
    localStorage: {
      logoutFlag: localStorage.getItem('cofind_user_logged_out'),
      supabaseKeys: Object.keys(localStorage).filter(k => 
        k.includes('supabase') || k.includes('sb-') || k.match(/auth-token/i)
      ),
      allKeys: Object.keys(localStorage)
    },
    sessionStorage: {
      keys: Object.keys(sessionStorage)
    },
    timestamp: new Date().toISOString()
  };

  console.group('🔐 Auth State Check');
  console.log('Logout Flag:', state.localStorage.logoutFlag);
  console.log('Supabase Keys:', state.localStorage.supabaseKeys);
  console.log('All LocalStorage Keys:', state.localStorage.allKeys);
  console.log('SessionStorage Keys:', state.sessionStorage.keys);
  console.log('Timestamp:', state.timestamp);
  console.groupEnd();

  return state;
};

/**
 * Check storage for Supabase-related data
 * @returns {Object} Storage information
 */
export const checkStorage = () => {
  const supabaseKeys = Object.keys(localStorage).filter(k => 
    k.includes('supabase') || k.includes('sb-') || k.match(/auth-token/i)
  );

  const storageInfo = {
    supabaseKeys: supabaseKeys.map(key => ({
      key,
      value: localStorage.getItem(key)?.substring(0, 100) + '...' // Truncate untuk keamanan
    })),
    logoutFlag: {
      key: 'cofind_user_logged_out',
      value: localStorage.getItem('cofind_user_logged_out')
    },
    sessionStorageCount: Object.keys(sessionStorage).length
  };

  console.group('🗄️ Storage Check');
  console.table(storageInfo.supabaseKeys);
  console.log('Logout Flag:', storageInfo.logoutFlag);
  console.log('SessionStorage Items:', storageInfo.sessionStorageCount);
  console.groupEnd();

  return storageInfo;
};

/**
 * Clear all Supabase-related storage (Emergency function)
 * WARNING: This will log out the user immediately
 * @param {boolean} keepLogoutFlag - Keep the logout flag after clearing
 * @returns {Object} Result of clearing operation
 */
export const clearAllSessions = (keepLogoutFlag = true) => {
  const logoutFlag = localStorage.getItem('cofind_user_logged_out');
  
  // Clear all Supabase keys
  const clearedKeys = [];
  Object.keys(localStorage).forEach(key => {
    if (key.includes('supabase') || key.includes('sb-') || key.match(/auth-token/i)) {
      localStorage.removeItem(key);
      clearedKeys.push(key);
    }
  });

  // Clear sessionStorage
  sessionStorage.clear();

  // Restore logout flag if needed
  if (keepLogoutFlag && logoutFlag === 'true') {
    localStorage.setItem('cofind_user_logged_out', 'true');
  }

  const result = {
    clearedKeys,
    logoutFlagRestored: keepLogoutFlag && logoutFlag === 'true',
    timestamp: new Date().toISOString()
  };

  console.group('🧹 Session Cleared');
  console.log('Cleared Keys:', clearedKeys);
  console.log('Logout Flag Restored:', result.logoutFlagRestored);
  console.log('Timestamp:', result.timestamp);
  console.groupEnd();

  return result;
};

/**
 * Check if user should be in guest mode
 * @returns {boolean} True if user should be guest
 */
export const shouldBeGuest = () => {
  const logoutFlag = localStorage.getItem('cofind_user_logged_out') === 'true';
  const supabaseKeys = Object.keys(localStorage).filter(k => 
    k.includes('supabase') || k.includes('sb-') || k.match(/auth-token/i)
  );

  const result = {
    shouldBeGuest: logoutFlag || supabaseKeys.length === 0,
    reason: logoutFlag ? 'Logout flag is set' : 'No Supabase session found',
    logoutFlag,
    hasSupabaseSession: supabaseKeys.length > 0
  };

  console.log('👤 Guest Mode Check:', result);
  return result;
};

/**
 * Monitor auth state changes (for debugging)
 * @param {Function} callback - Callback function to call on state change
 * @returns {Function} Cleanup function
 */
export const monitorAuthState = (callback) => {
  const interval = setInterval(() => {
    const state = checkAuthState();
    if (callback) callback(state);
  }, 1000);

  return () => clearInterval(interval);
};

// Export all functions
export default {
  checkAuthState,
  checkStorage,
  clearAllSessions,
  shouldBeGuest,
  monitorAuthState
};


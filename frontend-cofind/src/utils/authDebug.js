/**
 * Enhanced Auth Debug Utilities
 * Comprehensive debugging tools for authentication and session management
 * 
 * Usage in browser console:
 * window.__cofindAuthDebug.checkState()
 * window.__cofindAuthDebug.triggerBug('auto-login')
 * window.__cofindAuthDebug.monitorAuth()
 */

import { supabase } from '../lib/supabase';

// Error log storage (in-memory, cleared on refresh)
const errorLog = [];
const MAX_ERROR_LOG = 100;

/**
 * Enhanced error logging with context
 */
export const logAuthError = (error, context = {}) => {
  const errorEntry = {
    timestamp: new Date().toISOString(),
    error: {
      message: error?.message || String(error),
      code: error?.code,
      name: error?.name,
      stack: error?.stack
    },
    context,
    userAgent: navigator.userAgent,
    url: window.location.href
  };

  errorLog.push(errorEntry);
  
  // Keep only last MAX_ERROR_LOG entries
  if (errorLog.length > MAX_ERROR_LOG) {
    errorLog.shift();
  }

  console.error('[Auth Debug]', errorEntry);
  
  return errorEntry;
};

/**
 * Check current authentication state with detailed info
 */
export const checkAuthState = async () => {
  const state = {
    timestamp: new Date().toISOString(),
    localStorage: {
      logoutFlag: localStorage.getItem('cofind_user_logged_out'),
      supabaseKeys: Object.keys(localStorage).filter(k => 
        k.includes('supabase') || k.includes('sb-') || k.match(/auth-token/i)
      ),
      allKeys: Object.keys(localStorage),
      keyCount: localStorage.length
    },
    sessionStorage: {
      browserSession: sessionStorage.getItem('cofind_browser_session'),
      keys: Object.keys(sessionStorage),
      keyCount: sessionStorage.length
    },
    supabaseSession: null,
    supabaseUser: null,
    errorLog: errorLog.slice(-10) // Last 10 errors
  };

  // Try to get Supabase session
  if (supabase) {
    try {
      const { data: { session }, error } = await supabase.auth.getSession();
      state.supabaseSession = {
        exists: !!session,
        userId: session?.user?.id,
        email: session?.user?.email,
        expiresAt: session?.expires_at,
        error: error?.message
      };
      state.supabaseUser = session?.user ? {
        id: session.user.id,
        email: session.user.email,
        created_at: session.user.created_at
      } : null;
    } catch (e) {
      state.supabaseSession = { error: e.message };
    }
  }

  console.group('🔐 Auth State Check (Enhanced)');
  console.log('Timestamp:', state.timestamp);
  console.log('Logout Flag:', state.localStorage.logoutFlag);
  console.log('Supabase Keys:', state.localStorage.supabaseKeys);
  console.log('SessionStorage:', state.sessionStorage);
  console.log('Supabase Session:', state.supabaseSession);
  console.log('Supabase User:', state.supabaseUser);
  console.log('Recent Errors:', state.errorLog);
  console.table(state.localStorage.supabaseKeys.map(k => ({
    key: k,
    length: localStorage.getItem(k)?.length || 0
  })));
  console.groupEnd();

  return state;
};

/**
 * Check storage for Supabase-related data
 */
export const checkStorage = () => {
  const supabaseKeys = Object.keys(localStorage).filter(k => 
    k.includes('supabase') || k.includes('sb-') || k.match(/auth-token/i)
  );

  const storageInfo = {
    supabaseKeys: supabaseKeys.map(key => ({
      key,
      length: localStorage.getItem(key)?.length || 0,
      preview: localStorage.getItem(key)?.substring(0, 50) + '...'
    })),
    logoutFlag: {
      key: 'cofind_user_logged_out',
      value: localStorage.getItem('cofind_user_logged_out')
    },
    sessionStorage: {
      browserSession: sessionStorage.getItem('cofind_browser_session'),
      count: Object.keys(sessionStorage).length
    },
    totalLocalStorage: localStorage.length,
    totalSessionStorage: sessionStorage.length
  };

  console.group('🗄️ Storage Check (Enhanced)');
  console.table(storageInfo.supabaseKeys);
  console.log('Logout Flag:', storageInfo.logoutFlag);
  console.log('SessionStorage:', storageInfo.sessionStorage);
  console.log('Total Keys:', {
    localStorage: storageInfo.totalLocalStorage,
    sessionStorage: storageInfo.totalSessionStorage
  });
  console.groupEnd();

  return storageInfo;
};

/**
 * Clear all Supabase-related storage (Emergency function)
 */
export const clearAllSessions = async (keepLogoutFlag = true) => {
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

  // Sign out from Supabase
  if (supabase) {
    try {
      await supabase.auth.signOut({ scope: 'global' });
    } catch (e) {
      console.warn('[Auth Debug] Error signing out:', e);
    }
  }

  // Restore logout flag if needed
  if (keepLogoutFlag && logoutFlag === 'true') {
    localStorage.setItem('cofind_user_logged_out', 'true');
  }

  const result = {
    clearedKeys,
    logoutFlagRestored: keepLogoutFlag && logoutFlag === 'true',
    timestamp: new Date().toISOString()
  };

  console.group('🧹 Session Cleared (Enhanced)');
  console.log('Cleared Keys:', clearedKeys);
  console.log('Logout Flag Restored:', result.logoutFlagRestored);
  console.log('Timestamp:', result.timestamp);
  console.groupEnd();

  return result;
};

/**
 * Trigger specific auth bugs for testing
 */
export const triggerBug = async (bugType) => {
  console.group(`🐛 Triggering Bug: ${bugType}`);
  
  switch (bugType) {
    case 'auto-login':
      // Simulate auto-login after logout
      console.log('1. Setting logout flag...');
      localStorage.setItem('cofind_user_logged_out', 'true');
      
      console.log('2. Waiting 1 second...');
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      console.log('3. Checking if session still exists...');
      if (supabase) {
        const { data: { session } } = await supabase.auth.getSession();
        if (session) {
          console.warn('⚠️ BUG DETECTED: Session still exists after logout flag!');
          console.log('Session:', session);
        } else {
          console.log('✅ No session found (expected)');
        }
      }
      break;

    case 'session-restore':
      // Test session restore after hard reload
      console.log('1. Saving current state...');
      const currentState = await checkAuthState();
      
      console.log('2. Simulating hard reload...');
      console.log('   (In real scenario, user would do Ctrl+Shift+R)');
      console.log('   Current logout flag:', currentState.localStorage.logoutFlag);
      console.log('   Current session:', currentState.supabaseSession);
      
      break;

    case 'timeout':
      // Simulate timeout
      console.log('1. Testing Supabase connection...');
      if (supabase) {
        const startTime = Date.now();
        try {
          const { data, error } = await Promise.race([
            supabase.auth.getSession(),
            new Promise((_, reject) => 
              setTimeout(() => reject(new Error('Timeout after 5s')), 5000)
            )
          ]);
          const duration = Date.now() - startTime;
          console.log(`✅ Request completed in ${duration}ms`);
          if (error) {
            console.error('Error:', error);
          }
        } catch (e) {
          console.error('⚠️ TIMEOUT DETECTED:', e.message);
        }
      }
      break;

    case 'storage-conflict':
      // Test storage conflicts
      console.log('1. Checking for storage conflicts...');
      const supabaseKeys = Object.keys(localStorage).filter(k => 
        k.includes('supabase') || k.includes('sb-')
      );
      const logoutFlag = localStorage.getItem('cofind_user_logged_out');
      
      if (supabaseKeys.length > 0 && logoutFlag === 'true') {
        console.warn('⚠️ CONFLICT DETECTED: Supabase keys exist but logout flag is set!');
        console.log('Supabase Keys:', supabaseKeys);
        console.log('Logout Flag:', logoutFlag);
      } else {
        console.log('✅ No storage conflicts detected');
      }
      break;

    default:
      console.warn('Unknown bug type:', bugType);
      console.log('Available bug types: auto-login, session-restore, timeout, storage-conflict');
  }
  
  console.groupEnd();
};

/**
 * Monitor auth state changes in real-time
 */
export const monitorAuth = (duration = 30000) => {
  console.log(`🔍 Monitoring auth state for ${duration / 1000} seconds...`);
  
  let previousState = null;
  const interval = setInterval(async () => {
    const currentState = await checkAuthState();
    
    if (previousState) {
      // Check for changes
      const changes = {
        logoutFlag: previousState.localStorage.logoutFlag !== currentState.localStorage.logoutFlag,
        session: previousState.supabaseSession?.exists !== currentState.supabaseSession?.exists,
        userId: previousState.supabaseSession?.userId !== currentState.supabaseSession?.userId
      };
      
      if (Object.values(changes).some(v => v)) {
        console.warn('⚠️ Auth state changed!', changes);
        console.log('Previous:', previousState);
        console.log('Current:', currentState);
      }
    }
    
    previousState = currentState;
  }, 1000);

  setTimeout(() => {
    clearInterval(interval);
    console.log('✅ Monitoring stopped');
  }, duration);

  return () => clearInterval(interval);
};

/**
 * Test Supabase connection with retry
 */
export const testSupabaseConnection = async (retries = 3) => {
  console.group('🧪 Testing Supabase Connection');
  
  for (let i = 0; i < retries; i++) {
    console.log(`Attempt ${i + 1}/${retries}...`);
    const startTime = Date.now();
    
    try {
      if (!supabase) {
        throw new Error('Supabase not configured');
      }

      const { data, error } = await Promise.race([
        supabase.auth.getSession(),
        new Promise((_, reject) => 
          setTimeout(() => reject(new Error('Timeout after 10s')), 10000)
        )
      ]);

      const duration = Date.now() - startTime;
      
      if (error) {
        console.error(`❌ Error (${duration}ms):`, error);
        if (i < retries - 1) {
          console.log('Retrying...');
          await new Promise(resolve => setTimeout(resolve, 1000));
          continue;
        }
        return { success: false, error, duration };
      }

      console.log(`✅ Success (${duration}ms)`);
      return { success: true, data, duration };
    } catch (e) {
      const duration = Date.now() - startTime;
      console.error(`❌ Exception (${duration}ms):`, e.message);
      
      if (i < retries - 1) {
        console.log('Retrying...');
        await new Promise(resolve => setTimeout(resolve, 1000));
        continue;
      }
      
      return { success: false, error: e, duration };
    }
  }
  
  console.groupEnd();
};

/**
 * Get error log
 */
export const getErrorLog = (limit = 20) => {
  const recentErrors = errorLog.slice(-limit);
  console.group('📋 Error Log');
  console.table(recentErrors.map(e => ({
    timestamp: e.timestamp,
    message: e.error.message,
    code: e.error.code,
    context: JSON.stringify(e.context)
  })));
  console.groupEnd();
  return recentErrors;
};

/**
 * Clear error log
 */
export const clearErrorLog = () => {
  errorLog.length = 0;
  console.log('✅ Error log cleared');
};

// Expose to window for debugging
if (typeof window !== 'undefined') {
  window.__cofindAuthDebug = {
    checkState: checkAuthState,
    checkStorage,
    clearAll: clearAllSessions,
    triggerBug,
    monitorAuth,
    testConnection: testSupabaseConnection,
    getErrorLog,
    clearErrorLog,
    logError: logAuthError
  };
  
  console.log('🔧 Auth Debug Tools Available: window.__cofindAuthDebug');
  console.log('Try: window.__cofindAuthDebug.checkState()');
}

export default {
  checkAuthState,
  checkStorage,
  clearAllSessions,
  triggerBug,
  monitorAuth,
  testSupabaseConnection,
  getErrorLog,
  clearErrorLog,
  logAuthError
};

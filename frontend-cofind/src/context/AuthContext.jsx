import React, { useEffect, useState, useRef, useCallback } from 'react';
import { authService } from '../services/authService';
import { AuthContext } from './authContext';

// =====================================================
// AUTH CONTEXT - LOCAL SQLITE BACKEND VERSION
// =====================================================
// NEW FEATURES:
// - Uses local SQLite backend instead of Supabase
// - Immediate response times (~50ms vs 2-30s)
// - No external dependencies
// - Session persists on page refresh
// =====================================================

function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [initialized, setInitialized] = useState(false);

  // Refs untuk mencegah race condition
  const isMountedRef = useRef(true);
  const isInitializingRef = useRef(false);

  // Initialize auth state on mount
  useEffect(() => {
    isMountedRef.current = true;

    const initializeAuth = async () => {
      if (isInitializingRef.current) return;
      isInitializingRef.current = true;

      try {
        console.log('[Auth] Initializing with local backend...');

        // Get token from localStorage
        const token = authService.getToken();
        console.log('[Auth] Token found:', !!token);

        if (token) {
          // Verify token and get user
          console.log('[Auth] Verifying token...');
          const result = await authService.verifySession();

          if (isMountedRef.current) {
            if (result.valid && result.user) {
              console.log('[Auth] ✅ User restored from token:', result.user.username);
              setUser(result.user);
              setProfile(result.user);
            } else {
              console.log('[Auth] ❌ Token invalid or expired');
              setUser(null);
              setProfile(null);
            }
          }
        } else {
          console.log('[Auth] No token found, starting as guest');
          setUser(null);
          setProfile(null);
        }
      } catch (error) {
        console.error('[Auth] Initialization error:', error);
        if (isMountedRef.current) {
          setUser(null);
          setProfile(null);
        }
      } finally {
        if (isMountedRef.current) {
          setLoading(false);
          setInitialized(true);
          isInitializingRef.current = false;
        }
      }
    };

    initializeAuth();

    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Sign up
  const signUp = useCallback(async (username, password, fullName = '') => {
    try {
      console.log('[Auth] Signing up:', { username });

      // Validate input
      if (!username || username.length < 3) {
        return { error: { message: 'Username minimal 3 karakter' } };
      }

      if (!password || password.length < 6) {
        return { error: { message: 'Password minimal 6 karakter' } };
      }

      // Call backend signup
      const result = await authService.signup(
        `${username}@cofind.app`,
        username,
        password,
        fullName
      );

      if (!result.success) {
        return { error: { message: result.error || 'Signup failed' } };
      }

      // Update state
      if (isMountedRef.current) {
        setUser(result.user);
        setProfile(result.user);
      }

      return { data: { user: result.user }, error: null };
    } catch (error) {
      console.error('[Auth] SignUp error:', error);
      return { error: { message: error.message || 'Terjadi kesalahan saat mendaftar' } };
    }
  }, []);

  // Sign in
  const signIn = useCallback(async (username, password) => {
    try {
      console.log('[Auth] Signing in:', { username });

      // Convert username to email if needed
      const email = username.includes('@')
        ? username
        : `${username}@cofind.app`;

      // Call backend login
      const result = await authService.login(email, password);

      if (!result.success) {
        return { error: { message: result.error || 'Login failed' } };
      }

      // Update state
      if (isMountedRef.current) {
        setUser(result.user);
        setProfile(result.user);
      }

      return { data: { user: result.user, session: { user: result.user } }, error: null };
    } catch (error) {
      console.error('[Auth] SignIn error:', error);
      return { error: { message: error.message || 'Terjadi kesalahan saat login' } };
    }
  }, []);

  // Sign out
  const signOut = useCallback(async () => {
    try {
      console.log('[Auth] Signing out...');

      // Call backend logout
      await authService.logout();

      // Clear React state
      if (isMountedRef.current) {
        setUser(null);
        setProfile(null);
      }

      console.log('[Auth] ✅ Signed out');
      return { error: null };
    } catch (error) {
      console.error('[Auth] SignOut error:', error);
      // Clear state anyway
      if (isMountedRef.current) {
        setUser(null);
        setProfile(null);
      }
      return { error };
    }
  }, []);

  // Update profile
  const updateProfile = useCallback(async (updates) => {
    try {
      console.log('[Auth] Updating profile...');

      const result = await authService.updateProfile(updates);

      if (!result.success) {
        return { error: { message: result.error || 'Update failed' } };
      }

      // Update state
      if (isMountedRef.current) {
        setProfile(result.user);
        setUser(result.user);
      }

      return { data: result.user, error: null };
    } catch (error) {
      console.error('[Auth] Update profile error:', error);
      return { error };
    }
  }, []);

  // Update password
  const updatePassword = useCallback(async (newPassword) => {
    try {
      console.log('[Auth] Updating password...');

      const result = await authService.updatePassword(null, newPassword);

      if (!result.success) {
        return { error: { message: result.error || 'Update failed' } };
      }

      return { data: {}, error: null };
    } catch (error) {
      console.error('[Auth] Update password error:', error);
      return { error };
    }
  }, []);

  // Refresh profile (get latest from backend)
  const refreshProfile = useCallback(async () => {
    try {
      const currentUser = await authService.getCurrentUser();
      if (currentUser && isMountedRef.current) {
        setUser(currentUser);
        setProfile(currentUser);
      }
    } catch (error) {
      console.error('[Auth] Refresh profile error:', error);
    }
  }, []);

  // Reset password (placeholder - needs backend implementation)
  const resetPassword = useCallback(async (username) => {
    console.warn('[Auth] Password reset not implemented yet');
    return { error: { message: 'Password reset not available' } };
  }, []);

  // Context value
  const value = {
    user,
    profile,
    loading,
    initialized,
    isAuthenticated: !!user,
    isAdmin: profile?.role === 'admin' || profile?.role === 'superadmin',
    signUp,
    signIn,
    signOut,
    resetPassword,
    updatePassword,
    refreshProfile,
    updateProfile, // Add this new function
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export { AuthProvider };

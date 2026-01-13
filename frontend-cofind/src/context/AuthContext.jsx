import React, { useEffect, useState, useRef, useCallback } from 'react';
import { supabase, isSupabaseConfigured, getUserProfile, validateSession, clearSupabaseSession } from '../lib/supabase';
import { migrateLocalStorageToSupabase } from '../utils/migrateFavorites';
import { AuthContext } from './authContext';

// =====================================================
// AUTH CONTEXT - FINAL STABLE VERSION
// =====================================================
// PERBAIKAN:
// - Fast Refresh compatible (hanya export komponen dan hooks)
// - Race condition prevention dengan refs
// - Error handling yang lebih baik
// - Cleanup yang proper
// =====================================================

// Auth Provider Component
function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [initialized, setInitialized] = useState(false);
  
  // Refs untuk mencegah race condition
  const isMountedRef = useRef(true);
  const isProcessingRef = useRef(false);
  const currentUserIdRef = useRef(null);
  const initAttemptRef = useRef(0);
  const pendingAuthEventRef = useRef(null);

  // Fetch user profile dengan error handling
  const fetchProfile = useCallback(async (userId) => {
    if (!supabase || !userId || !isMountedRef.current) {
      console.log('[Auth] fetchProfile skipped:', { supabase: !!supabase, userId, mounted: isMountedRef.current });
      return null;
    }
    
    try {
      console.log('[Auth] Fetching profile for userId:', userId);
      const profileData = await getUserProfile(userId);
      console.log('[Auth] Profile data:', profileData);
      
      if (!isMountedRef.current) return null;
      
      if (!profileData) {
        // Profile tidak ditemukan, coba buat
        console.log('[Auth] Profile not found, creating new profile');
        const { data: { user: authUser } } = await supabase.auth.getUser();
        
        if (authUser && isMountedRef.current) {
          const username = authUser.user_metadata?.username || 
                          authUser.email?.split('@')[0] || 
                          `user_${userId.substring(0, 8)}`;
          
          const { data: newProfile, error: createError } = await supabase
            .from('profiles')
            .insert({
              id: userId,
              username: username,
              full_name: authUser.user_metadata?.full_name || username,
              role: 'user'
            })
            .select('id, username, role, full_name, avatar_url')
            .single();
          
          if (!createError && newProfile && isMountedRef.current) {
            console.log('[Auth] New profile created:', newProfile);
            setProfile(newProfile);
            return newProfile;
          } else {
            console.error('[Auth] Error creating profile:', createError);
          }
        }
        
        if (isMountedRef.current) {
          setProfile(null);
        }
        return null;
      }
      
      if (isMountedRef.current) {
        console.log('[Auth] Setting existing profile:', profileData);
        setProfile(profileData);
      }
      return profileData;
    } catch (error) {
      console.error('[Auth] Error fetching profile:', error);
      if (isMountedRef.current) {
        setProfile(null);
      }
      return null;
    }
  }, []);

  // Set user dengan update refs
  const setUserSafe = useCallback((newUser) => {
    if (!isMountedRef.current) return;
    
    const newUserId = newUser?.id || null;
    currentUserIdRef.current = newUserId;
    setUser(newUser);
  }, []);

  const handleAuthEvent = useCallback(async (event, session) => {
    if (!isMountedRef.current) return;
    
    console.log('[Auth] Handling auth event:', event, !!session?.user, 'Processing:', isProcessingRef.current);
    
    if (isProcessingRef.current) {
      console.log('[Auth] Queuing auth event (already processing)');
      pendingAuthEventRef.current = { event, session };
      return;
    }
    
    isProcessingRef.current = true;
    try {
      setLoading(false);
      if ((event === 'SIGNED_IN' || event === 'INITIAL_SESSION') && session?.user) {
        console.log('[Auth] Setting user and fetching profile');
        setUserSafe(session.user);
        await fetchProfile(session.user.id);
        console.log('[Auth] Profile fetched');
        migrateLocalStorageToSupabase(session.user.id).catch(() => {});
      } else if (event === 'SIGNED_OUT') {
        setUserSafe(null);
        setProfile(null);
      } else if (event === 'TOKEN_REFRESHED' && session?.user) {
        if (currentUserIdRef.current !== session.user.id) {
          setUserSafe(session.user);
        }
        await fetchProfile(session.user.id);
      } else if (event === 'USER_UPDATED' && session?.user) {
        setUser(session.user);
      }
    } catch {
      void 0;
    } finally {
      isProcessingRef.current = false;
      const pending = pendingAuthEventRef.current;
      pendingAuthEventRef.current = null;
      if (pending && isMountedRef.current) {
        await handleAuthEvent(pending.event, pending.session);
      }
    }
  }, [fetchProfile, setUserSafe]);

  // Initialize auth state
  useEffect(() => {
    if (!isSupabaseConfigured) {
      console.log('[Auth] Supabase tidak dikonfigurasi');
      setLoading(false);
      setInitialized(true);
      return;
    }

    isMountedRef.current = true;
    const currentAttempt = ++initAttemptRef.current;
    
    const initAuth = async () => {
      try {
        // Guard: cek apakah masih valid
        if (!isMountedRef.current || currentAttempt !== initAttemptRef.current) {
          return;
        }
        
        console.log('[Auth] Initializing auth, validating session...');
        
        // Validate session with token expiry check
        const validation = await validateSession();
        
        if (!isMountedRef.current || currentAttempt !== initAttemptRef.current) {
          return;
        }
        
        if (validation.valid && validation.user) {
          console.log('[Auth] Valid session found, user:', validation.user.id);
          setUserSafe(validation.user);
          await fetchProfile(validation.user.id);
        } else {
          console.log('[Auth] No valid session found:', validation.error);
          // Clear any stale session data
          await clearSupabaseSession();
          setUserSafe(null);
          setProfile(null);
        }
      } catch (error) {
        console.error('[Auth] Error initializing:', error);
        if (isMountedRef.current && currentAttempt === initAttemptRef.current) {
          // Clear stale data on error
          await clearSupabaseSession();
          setUserSafe(null);
          setProfile(null);
        }
      } finally {
        if (isMountedRef.current && currentAttempt === initAttemptRef.current) {
          setLoading(false);
          setInitialized(true);
        }
      }
    };

    initAuth();

    // Listen untuk auth state changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event, session) => {
      if (isMountedRef.current) setInitialized(true);
      await handleAuthEvent(event, session);
    });

    const onVisibility = async () => {
      if (!isMountedRef.current) return;
      if (document.visibilityState !== 'visible') return;
      
      console.log('[Auth] Tab became visible, validating session...');
      setLoading(true); // Start loading before validation
      try {
        // Validate session instead of just getting it
        const validation = await validateSession();
        
        if (!isMountedRef.current) return;
        
        if (validation.valid && validation.user) {
          console.log('[Auth] Valid session found, user:', validation.user.id);
          // Only update if user actually changed
          if (currentUserIdRef.current !== validation.user.id) {
            console.log('[Auth] User changed, updating state');
            setUserSafe(validation.user);
            await fetchProfile(validation.user.id);
          } else {
            console.log('[Auth] Same user, just refreshing profile');
            await fetchProfile(validation.user.id);
          }
        } else {
          console.log('[Auth] Session invalid or expired, clearing state');
          // Clear stale session
          await clearSupabaseSession();
          setUserSafe(null);
          setProfile(null);
        }
      } catch (error) {
        console.error('[Auth] Error in visibility change handler:', error);
        // Clear stale data on error
        await clearSupabaseSession();
        setUserSafe(null);
        setProfile(null);
      } finally {
        if (isMountedRef.current) {
          setLoading(false);
          setInitialized(true);
        }
      }
    };

    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      isMountedRef.current = false;
      subscription?.unsubscribe();
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [fetchProfile, setUserSafe, handleAuthEvent]);

  // Helper: Generate email dari username
  const usernameToEmail = useCallback((username) => {
    const normalized = username.toLowerCase().trim().replace(/\s+/g, '').replace(/[^a-z0-9_]/g, '');
    return `${normalized}@cofind.app`;
  }, []);

  // Sign up dengan username dan password
  const signUp = useCallback(async (username, password, metadata = {}) => {
    if (!supabase) return { error: { message: 'Supabase tidak dikonfigurasi' } };
    
    let normalizedUsername = username.toLowerCase().trim().replace(/\s+/g, '');
    
    if (normalizedUsername.includes('@')) {
      normalizedUsername = normalizedUsername.split('@')[0];
    }
    
    if (!normalizedUsername || normalizedUsername.length < 3) {
      return { error: { message: 'Username minimal 3 karakter' } };
    }
    
    try {
      // Cek username sudah digunakan
      const { data: existingProfile } = await supabase
        .from('profiles')
        .select('username')
        .eq('username', normalizedUsername)
        .maybeSingle();
      
      if (existingProfile) {
        return { error: { message: 'Username sudah digunakan' } };
      }
      
      const internalEmail = usernameToEmail(normalizedUsername);
      
      const { data, error } = await supabase.auth.signUp({
        email: internalEmail,
        password,
        options: {
          data: {
            username: normalizedUsername,
            ...metadata
          }
        }
      });

      if (error) {
        if (error.message.includes('already registered') || error.message.includes('already exists')) {
          return { error: { message: 'Username sudah digunakan' } };
        }
        return { error };
      }

      return { data, error: null };
    } catch (err) {
      console.error('[Auth] SignUp error:', err);
      return { error: { message: 'Terjadi kesalahan saat mendaftar' } };
    }
  }, [usernameToEmail]);

  // Sign in dengan username dan password
  const signIn = useCallback(async (username, password) => {
    if (!supabase) return { error: { message: 'Supabase tidak dikonfigurasi' } };
    
    let normalizedUsername = username.toLowerCase().trim().replace(/\s+/g, '');
    
    if (normalizedUsername.includes('@')) {
      normalizedUsername = normalizedUsername.split('@')[0];
    }
    
    const email = usernameToEmail(normalizedUsername);
    
    try {
      const { data, error } = await supabase.auth.signInWithPassword({
        email,
        password
      });

      if (error) {
        // Check if username exists
        const { data: profileCheck } = await supabase
          .from('profiles')
          .select('username')
          .eq('username', normalizedUsername)
          .maybeSingle();
        
        if (!profileCheck && error.message.includes('Invalid login credentials')) {
          return { error: { message: 'Username tidak ditemukan' } };
        }
        
        if (error.message.includes('Invalid login credentials')) {
          return { error: { message: 'Username atau password salah' } };
        }
        
        return { error };
      }

      return { data, error: null };
    } catch (err) {
      console.error('[Auth] SignIn error:', err);
      return { error: { message: 'Terjadi kesalahan saat login' } };
    }
  }, [usernameToEmail]);

  // Sign out - COMPREHENSIVE VERSION with proper session clearing
  const signOut = useCallback(async () => {
    if (!supabase) return { error: { message: 'Supabase tidak dikonfigurasi' } };
    
    console.log('[Auth] Starting comprehensive sign out...');
    
    try {
      // Step 1: Clear React state immediately for responsive UX
      currentUserIdRef.current = null;
      setUser(null);
      setProfile(null);
      console.log('[Auth] ✅ Cleared React state');
      
      // Step 2: Clear Supabase session (sign out + clear tokens)
      console.log('[Auth] Clearing Supabase session...');
      await clearSupabaseSession();
      console.log('[Auth] ✅ Cleared Supabase session');
      
      // Step 3: Clear ALL app-related storage keys
      try {
        const keysToRemove = [];
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i);
          if (key && (
            key.includes('supabase') ||
            key.includes('sb-') ||
            key.startsWith('cofind_') ||
            key.startsWith('cache_') ||
            key.startsWith('favorites_') ||
            key.startsWith('review_') ||
            key === 'SUPABASE_AUTH_TOKEN'
          )) {
            keysToRemove.push(key);
          }
        }
        
        keysToRemove.forEach(key => {
          try {
            localStorage.removeItem(key);
          } catch (e) {
            console.warn(`[Auth] Failed to remove key ${key}:`, e);
          }
        });
        
        console.log(`[Auth] ✅ Cleared ${keysToRemove.length} localStorage keys`);
      } catch (error) {
        console.warn('[Auth] Error clearing localStorage:', error);
      }
      
      // Step 4: Clear sessionStorage
      try {
        sessionStorage.clear();
        console.log('[Auth] ✅ Cleared sessionStorage');
      } catch (error) {
        console.warn('[Auth] Error clearing sessionStorage:', error);
      }
      
      // Step 5: Clear IndexedDB
      if ('indexedDB' in window) {
        try {
          const databases = await indexedDB.databases?.() || [];
          for (const db of databases) {
            if (db.name) {
              indexedDB.deleteDatabase(db.name);
            }
          }
          console.log('[Auth] ✅ Cleared IndexedDB');
        } catch (error) {
          console.warn('[Auth] Error clearing IndexedDB:', error);
        }
      }
      
      console.log('[Auth] ✅ Sign out complete');
      return { error: null };
    } catch (error) {
      console.error('[Auth] Unexpected error during sign out:', error);
      // Even if there's an error, ensure state is cleared
      currentUserIdRef.current = null;
      setUser(null);
      setProfile(null);
      return { error };
    }
  }, []);

  // Reset password
  const resetPassword = useCallback(async (username) => {
    if (!supabase) return { error: { message: 'Supabase tidak dikonfigurasi' } };
    
    let normalizedUsername = username.toLowerCase().trim().replace(/\s+/g, '');
    
    if (normalizedUsername.includes('@')) {
      normalizedUsername = normalizedUsername.split('@')[0];
    }
    
    const email = usernameToEmail(normalizedUsername);
    
    const { data, error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/reset-password`
    });

    return { data, error };
  }, [usernameToEmail]);

  // Update password
  const updatePassword = useCallback(async (newPassword) => {
    if (!supabase) return { error: { message: 'Supabase tidak dikonfigurasi' } };
    
    const { data, error } = await supabase.auth.updateUser({
      password: newPassword
    });

    return { data, error };
  }, []);

  // Refresh profile
  const refreshProfile = useCallback(async () => {
    if (currentUserIdRef.current) {
      await fetchProfile(currentUserIdRef.current);
    }
  }, [fetchProfile]);

  // Context value
  const value = {
    user,
    profile,
    loading,
    initialized,
    isAuthenticated: !!user,
    isAdmin: profile?.role === 'admin',
    isSupabaseConfigured,
    signUp,
    signIn,
    signOut,
    resetPassword,
    updatePassword,
    refreshProfile
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export { AuthProvider };

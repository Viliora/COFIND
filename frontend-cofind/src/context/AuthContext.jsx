import React, { createContext, useContext, useEffect, useState, useRef, useCallback } from 'react';
import { supabase, isSupabaseConfigured, getUserProfile } from '../lib/supabase';
import { migrateLocalStorageToSupabase } from '../utils/migrateFavorites';

// =====================================================
// AUTH CONTEXT - FINAL STABLE VERSION
// =====================================================
// PERBAIKAN:
// - Fast Refresh compatible (hanya export komponen dan hooks)
// - Race condition prevention dengan refs
// - Error handling yang lebih baik
// - Cleanup yang proper
// =====================================================

const AuthContext = createContext(null);

// Hook untuk menggunakan Auth context
// HARUS didefinisikan setelah createContext
function useAuth() {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

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

  // Fetch user profile dengan error handling
  const fetchProfile = useCallback(async (userId) => {
    if (!supabase || !userId || !isMountedRef.current) {
      return null;
    }
    
    try {
      const profileData = await getUserProfile(userId);
      
      if (!isMountedRef.current) return null;
      
      if (!profileData) {
        // Profile tidak ditemukan, coba buat
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
            setProfile(newProfile);
            return newProfile;
          }
        }
        
        if (isMountedRef.current) {
          setProfile(null);
        }
        return null;
      }
      
      if (isMountedRef.current) {
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
        // Cek session yang ada
        const { data: { session }, error } = await supabase.auth.getSession();
        
        // Guard: cek apakah masih valid
        if (!isMountedRef.current || currentAttempt !== initAttemptRef.current) {
          return;
        }
        
        if (error) {
          console.warn('[Auth] Error getting session:', error.message);
        }
        
        if (session?.user) {
          console.log('[Auth] Session ditemukan');
          setUserSafe(session.user);
          await fetchProfile(session.user.id);
        } else {
          console.log('[Auth] Tidak ada session');
          setUserSafe(null);
          setProfile(null);
        }
      } catch (error) {
        console.error('[Auth] Error initializing:', error);
        if (isMountedRef.current && currentAttempt === initAttemptRef.current) {
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
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        // Guard: cek mounted
        if (!isMountedRef.current) return;
        
        // Cegah processing ganda
        if (isProcessingRef.current) {
          return;
        }
        
        isProcessingRef.current = true;
        
        try {
          console.log('[Auth] Event:', event);
          
          if (event === 'SIGNED_IN' && session?.user) {
            // User baru login
            setUserSafe(session.user);
            await fetchProfile(session.user.id);
            
            // Migrate data dari localStorage (non-blocking)
            migrateLocalStorageToSupabase(session.user.id).catch(err => {
              console.warn('[Auth] Migration error:', err);
            });
          } 
          else if (event === 'SIGNED_OUT') {
            setUserSafe(null);
            setProfile(null);
          }
          else if (event === 'TOKEN_REFRESHED' && session?.user) {
            // Token direfresh, update user jika berbeda
            if (currentUserIdRef.current !== session.user.id) {
              setUserSafe(session.user);
              await fetchProfile(session.user.id);
            }
          }
          else if (event === 'INITIAL_SESSION') {
            // Session awal - hanya process jika belum ada user
            if (session?.user && !currentUserIdRef.current) {
              setUserSafe(session.user);
              await fetchProfile(session.user.id);
            }
          }
          else if (event === 'USER_UPDATED' && session?.user) {
            setUser(session.user);
          }
        } catch (error) {
          console.error('[Auth] Error handling event:', error);
        } finally {
          isProcessingRef.current = false;
          if (isMountedRef.current) {
            setLoading(false);
          }
        }
      }
    );

    return () => {
      isMountedRef.current = false;
      subscription?.unsubscribe();
    };
  }, [fetchProfile, setUserSafe]);

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

  // Sign out - STABLE VERSION
  const signOut = useCallback(async () => {
    if (!supabase) return { error: { message: 'Supabase tidak dikonfigurasi' } };
    
    console.log('[Auth] Memulai sign out...');
    
    try {
      // Clear state dulu untuk UX yang responsif
      currentUserIdRef.current = null;
      setUser(null);
      setProfile(null);
      
      // Sign out dari Supabase
      const { error } = await supabase.auth.signOut();
      
      if (error) {
        console.error('[Auth] Sign out error:', error);
      }
      
      // Clear cache yang relevan (non-blocking)
      try {
        const keysToRemove = [];
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i);
          if (key && (
            key.includes('supabase') ||
            key.includes('sb-') ||
            key.startsWith('cofind_favorites_') ||
            key.startsWith('cofind_want_to_visit_') ||
            key.startsWith('cache_')
          )) {
            keysToRemove.push(key);
          }
        }
        
        keysToRemove.forEach(key => {
          try {
            localStorage.removeItem(key);
          } catch (e) {
            // Ignore
          }
        });
        
        console.log('[Auth] Sign out complete');
      } catch (e) {
        // Ignore cache clearing errors
      }
      
      return { error };
    } catch (error) {
      console.error('[Auth] Sign out exception:', error);
      // Tetap clear state
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

// Export named exports only (untuk Fast Refresh compatibility)
export { AuthContext, AuthProvider, useAuth };

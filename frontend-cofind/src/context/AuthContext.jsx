import React, { createContext, useContext, useEffect, useState } from 'react';
import { supabase, isSupabaseConfigured, getUserProfile } from '../lib/supabase';
import { migrateLocalStorageToSupabase } from '../utils/migrateFavorites';

const AuthContext = createContext({});

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [initialized, setInitialized] = useState(false);

  // Fetch user profile
  const fetchProfile = async (userId) => {
    if (!supabase) return null;
    const profileData = await getUserProfile(userId);
    setProfile(profileData);
    return profileData;
  };

  // Initialize auth state
  useEffect(() => {
    if (!isSupabaseConfigured) {
      console.warn('[Auth] Supabase tidak dikonfigurasi. Auth features disabled.');
      setLoading(false);
      setInitialized(true);
      return;
    }

    // Get initial session
    const initAuth = async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (session?.user) {
          setUser(session.user);
          await fetchProfile(session.user.id);
        }
      } catch (error) {
        console.error('[Auth] Error initializing:', error);
      } finally {
        setLoading(false);
        setInitialized(true);
      }
    };

    initAuth();

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        console.log('[Auth] State changed:', event);
        
        if (session?.user) {
          setUser(session.user);
          await fetchProfile(session.user.id);
          
          // Migrate localStorage data on sign in
          if (event === 'SIGNED_IN') {
            migrateLocalStorageToSupabase(session.user.id)
              .then(result => {
                if (result.success && result.results) {
                  console.log('[Auth] Migration complete:', result.results);
                }
              })
              .catch(err => console.error('[Auth] Migration error:', err));
          }
        } else {
          setUser(null);
          setProfile(null);
        }
        setLoading(false);
      }
    );

    return () => {
      subscription?.unsubscribe();
    };
  }, []);

  // Sign up with email and password
  const signUp = async (email, password, metadata = {}) => {
    if (!supabase) return { error: { message: 'Supabase tidak dikonfigurasi' } };
    
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: metadata // username, full_name, etc.
      }
    });

    return { data, error };
  };

  // Sign in with email and password
  const signIn = async (email, password) => {
    if (!supabase) return { error: { message: 'Supabase tidak dikonfigurasi' } };
    
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password
    });

    return { data, error };
  };

  // Sign out
  const signOut = async () => {
    if (!supabase) return { error: { message: 'Supabase tidak dikonfigurasi' } };
    
    const { error } = await supabase.auth.signOut();
    if (!error) {
      setUser(null);
      setProfile(null);
    }
    return { error };
  };

  // Reset password
  const resetPassword = async (email) => {
    if (!supabase) return { error: { message: 'Supabase tidak dikonfigurasi' } };
    
    const { data, error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/reset-password`
    });

    return { data, error };
  };

  // Update password
  const updatePassword = async (newPassword) => {
    if (!supabase) return { error: { message: 'Supabase tidak dikonfigurasi' } };
    
    const { data, error } = await supabase.auth.updateUser({
      password: newPassword
    });

    return { data, error };
  };

  // Refresh profile
  const refreshProfile = async () => {
    if (user) {
      await fetchProfile(user.id);
    }
  };

  const value = {
    user,
    profile,
    loading,
    initialized,
    isAuthenticated: !!user,
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
};

export default AuthContext;

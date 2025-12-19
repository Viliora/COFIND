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
    if (!supabase || !userId) {
      console.warn('[Auth] fetchProfile: Missing supabase or userId');
      setProfile(null);
      return null;
    }
    
    try {
      const profileData = await getUserProfile(userId);
      
      // If profile not found, try to create it (might be missing due to trigger failure)
      if (!profileData) {
        console.warn('[Auth] Profile not found for user:', userId, '- attempting to create profile');
        
        // Get user data from auth
        const { data: { user: authUser } } = await supabase.auth.getUser();
        
        if (authUser) {
          // Try to create profile with username from metadata or email
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
          
          if (createError) {
            console.error('[Auth] Error creating profile:', createError);
            // If creation fails (e.g., RLS issue), don't clear session immediately
            // Let the user stay logged in and try again later
            setProfile(null);
            return null;
          }
          
          if (newProfile) {
            console.log('[Auth] Profile created successfully:', newProfile);
            setProfile(newProfile);
            return newProfile;
          }
        }
        
        // If we can't create profile, don't immediately logout
        // This might be a temporary RLS issue
        console.warn('[Auth] Could not create profile - keeping session but profile is null');
        setProfile(null);
        return null;
      }
      
      // Profile found - set it
      setProfile(profileData);
      return profileData;
    } catch (error) {
      console.error('[Auth] Error fetching profile:', error);
      
      // Check if it's a 401 (RLS issue) vs other error
      if (error?.code === 'PGRST301' || error?.message?.includes('401') || error?.message?.includes('permission denied')) {
        console.warn('[Auth] RLS permission issue - profile might exist but not accessible');
        // Don't clear session for RLS issues - might be temporary
        setProfile(null);
        return null;
      }
      
      // For other errors, also don't clear session immediately
      setProfile(null);
      return null;
    }
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
        // PRIORITY 0: Detect if this is a new browser session (browser was closed)
        // We use sessionStorage as a flag to detect browser close vs tab close
        // sessionStorage is cleared when browser is closed, but persists across tab close
        const isNewBrowserSession = typeof window !== 'undefined' && !sessionStorage.getItem('cofind_browser_session');
        
        if (isNewBrowserSession) {
          // This is a new browser session (browser was closed and reopened)
          // Clear session to ensure user is logged out after browser close
          console.log('[Auth] New browser session detected - clearing session (browser was closed)');
          
          // Clear logout flag first (if exists)
          localStorage.removeItem('cofind_user_logged_out');
          
          // Clear Supabase session
          if (supabase) {
            try {
              await supabase.auth.signOut({ scope: 'global' });
            } catch (signOutError) {
              console.warn('[Auth] Error clearing session on new browser session:', signOutError);
            }
          }
          
          // Clear all Supabase-related storage
          const allKeys = [];
          for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key) {
              if (key.includes('supabase') || 
                  key.includes('sb-') || 
                  key.match(/auth-token/i) ||
                  key.match(/^sb-[a-z0-9-]+-auth-token$/i) ||
                  key.startsWith('supabase.auth.')) {
                allKeys.push(key);
              }
            }
          }
          allKeys.forEach(key => localStorage.removeItem(key));
          
          // Set browser session flag (this will persist across tab close, but clear on browser close)
          sessionStorage.setItem('cofind_browser_session', 'true');
          
          // Set state to guest mode
          setUser(null);
          setProfile(null);
          setLoading(false);
          setInitialized(true);
          console.log('[Auth] Guest mode enforced - browser was closed');
          return; // Exit early, don't restore session
        } else {
          // This is not a new browser session (tab was closed, but browser is still open)
          // Session should persist - continue with normal auth initialization
          console.log('[Auth] Existing browser session - session will persist (tab was closed)');
        }
        
        // PRIORITY 1: Check if user explicitly logged out (flag set by signOut)
        const userLoggedOut = localStorage.getItem('cofind_user_logged_out') === 'true';
        
        if (userLoggedOut) {
          // User explicitly logged out - FORCE clear session and don't restore
          console.log('[Auth] User logged out flag detected - forcing guest mode');
          
          // Aggressively clear Supabase session
          try {
            await supabase.auth.signOut({ scope: 'global' });
          } catch (signOutError) {
            console.warn('[Auth] Error during forced signOut:', signOutError);
          }
          
          // Clear all Supabase-related storage (but preserve logout flag)
          const logoutFlag = 'true';
          const allKeys = [];
          for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && key !== 'cofind_user_logged_out') {
              if (key.includes('supabase') || 
                  key.includes('sb-') || 
                  key.match(/auth-token/i) ||
                  key.match(/^sb-[a-z0-9-]+-auth-token$/i)) {
                allKeys.push(key);
              }
            }
          }
          allKeys.forEach(key => localStorage.removeItem(key));
          sessionStorage.clear();
          
          // Restore logout flag
          localStorage.setItem('cofind_user_logged_out', 'true');
          
          // Set state to guest mode
          setUser(null);
          setProfile(null);
          setLoading(false);
          setInitialized(true);
          console.log('[Auth] Guest mode enforced - session cleared');
          return; // CRITICAL: Exit early, don't check for session
        }
        
        // PRIORITY 2: Check if auto-login should be disabled (for development/testing)
        const disableAutoLogin = import.meta.env.VITE_DISABLE_AUTO_LOGIN === 'true';
        
        if (disableAutoLogin) {
          // Clear session on page load if auto-login is disabled
          console.log('[Auth] Auto-login disabled - clearing session');
          await supabase.auth.signOut();
          setUser(null);
          setProfile(null);
          setLoading(false);
          setInitialized(true);
          return;
        }
        
        // PRIORITY 3: Normal behavior: restore session if exists AND no logout flag
        // CRITICAL: Always try to restore session on page load/refresh
        const { data: { session }, error: sessionError } = await supabase.auth.getSession();
        
        if (sessionError) {
          console.warn('[Auth] Error getting session:', sessionError);
          // Don't clear state on error - might be temporary network issue
        }
        
        if (session?.user) {
          // Double-check logout flag hasn't been set (race condition protection)
          const stillLoggedOut = localStorage.getItem('cofind_user_logged_out') === 'true';
          if (stillLoggedOut) {
            console.log('[Auth] Logout flag detected during session restore - aborting');
            setUser(null);
            setProfile(null);
            setLoading(false);
            setInitialized(true);
            return;
          }
          
          // CRITICAL: Restore session immediately - don't wait for profile fetch
          // This ensures user stays logged in even if profile fetch fails
          console.log('[Auth] Session found - restoring for user:', session.user.id);
          setUser(session.user);
          
          // Verify the session is still valid by checking if user exists
          // But don't block session restoration if profile fetch fails
          try {
            const profileData = await fetchProfile(session.user.id);
            
            if (profileData) {
              console.log('[Auth] Profile restored for user:', session.user.id, 'role:', profileData.role);
            } else {
              // Profile not found or couldn't be created - but don't logout immediately
              // This might be a temporary RLS issue or profile creation delay
              console.warn('[Auth] Profile not available for user:', session.user.id, '- keeping session but profile is null');
              // User is already set above, just profile is null
            }
          } catch (profileError) {
            console.error('[Auth] Error checking profile:', profileError);
            // Don't logout on error - might be temporary
            // User is already set above, just profile is null
          }
        } else {
          // No session found - check if logout flag is set
          const stillLoggedOut = localStorage.getItem('cofind_user_logged_out') === 'true';
          if (!stillLoggedOut) {
            // No logout flag and no session - might be first visit or session expired
            console.log('[Auth] No session found and no logout flag - guest mode');
          } else {
            console.log('[Auth] No session found and logout flag set - guest mode (expected)');
          }
          setUser(null);
          setProfile(null);
        }
      } catch (error) {
        console.error('[Auth] Error initializing:', error);
        setUser(null);
        setProfile(null);
      } finally {
        setLoading(false);
        setInitialized(true);
      }
    };

    initAuth();
    
    // Set browser session flag when component mounts (if not already set)
    // This flag persists across tab close, but is cleared when browser is closed
    // CRITICAL: Set flag AFTER initAuth to ensure it's set for current browser session
    if (typeof window !== 'undefined') {
      // Set flag if not already set (this happens after initAuth checks for new browser session)
      if (!sessionStorage.getItem('cofind_browser_session')) {
        sessionStorage.setItem('cofind_browser_session', 'true');
        console.log('[Auth] Browser session flag set - session will persist across tab close');
      }
    }

    // Listen for auth changes
    let isProcessingAuthChange = false;
    let initAuthCompleted = false;
    
    // Mark initAuth as completed after a short delay to prevent onAuthStateChange from interfering
    setTimeout(() => {
      initAuthCompleted = true;
    }, 1000);
    
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        // Prevent infinite loop
        if (isProcessingAuthChange) {
          console.log('[Auth] Already processing auth change, skipping...');
          return;
        }
        
        // CRITICAL: Don't skip INITIAL_SESSION - it's important for page refresh
        // INITIAL_SESSION is fired when Supabase restores session from storage
        // We need to handle it to ensure session persists after refresh
        // Only skip if we're still in the middle of initAuth (very short window)
        if (event === 'INITIAL_SESSION' && !initAuthCompleted) {
          // Wait a bit and then process INITIAL_SESSION
          setTimeout(() => {
            if (session?.user && !localStorage.getItem('cofind_user_logged_out')) {
              console.log('[Auth] Processing INITIAL_SESSION after delay');
              setUser(session.user);
              fetchProfile(session.user.id).catch(err => {
                console.warn('[Auth] Error fetching profile in delayed INITIAL_SESSION:', err);
              });
            }
          }, 500);
          return; // Skip immediate processing, but schedule delayed processing
        }
        
        isProcessingAuthChange = true;
        console.log('[Auth] State changed:', event, session ? 'has session' : 'no session');
        
        try {
          // PRIORITY: Check if user explicitly logged out FIRST
          const userLoggedOut = localStorage.getItem('cofind_user_logged_out') === 'true';
          
          // If logout flag is set, ONLY allow SIGNED_IN event to clear it
          // All other events (including TOKEN_REFRESHED, INITIAL_SESSION) should be ignored
          if (userLoggedOut) {
            if (event === 'SIGNED_IN') {
              // User explicitly signed in - clear logout flag and restore session
              console.log('[Auth] User signed in - clearing logout flag and restoring session');
              localStorage.removeItem('cofind_user_logged_out');
              
              if (session?.user) {
                // CRITICAL: Try to fetch profile, but don't logout if it fails
                try {
                  const profileData = await fetchProfile(session.user.id);
                  
                  if (profileData) {
                    // Profile exists - restore session
                    console.log('[Auth] Profile found - restoring session for user:', session.user.id, 'role:', profileData.role);
                    setUser(session.user);
                    
                    // Migrate localStorage data on sign in
                    migrateLocalStorageToSupabase(session.user.id)
                      .then(result => {
                        if (result.success && result.results) {
                          console.log('[Auth] Migration complete:', result.results);
                        }
                      })
                      .catch(err => console.error('[Auth] Migration error:', err));
                  } else {
                    // Profile not found or couldn't be created - but keep session
                    // This might be a temporary RLS issue or profile creation delay
                    console.warn('[Auth] Profile not available for user:', session.user.id, '- keeping session but profile is null');
                    setUser(session.user);
                    setProfile(null);
                  }
                } catch (profileCheckError) {
                  console.error('[Auth] Error checking profile in SIGNED_IN event:', profileCheckError);
                  // On error, still restore user session - don't logout
                  // Profile might be available later
                  setUser(session.user);
                  setProfile(null);
                }
              }
            } else {
              // Logout flag is set and event is NOT SIGNED_IN - force guest mode
              // This includes TOKEN_REFRESHED, INITIAL_SESSION, etc.
              console.log('[Auth] Logout flag active - ignoring', event, 'event, forcing guest mode');
              
              // Aggressively clear state
              setUser(null);
              setProfile(null);
              
              // If session exists but logout flag is set, sign out (except for SIGNED_OUT event to avoid loop)
              if (session?.user && event !== 'SIGNED_OUT') {
                console.log('[Auth] Session exists but logout flag is set - signing out');
                try {
                  await supabase.auth.signOut({ scope: 'global' });
                  // Clear storage again after signOut
                  const allKeys = [];
                  for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    if (key && key !== 'cofind_user_logged_out') {
                      if (key.includes('supabase') || 
                          key.includes('sb-') || 
                          key.match(/auth-token/i) ||
                          key.match(/^sb-[a-z0-9-]+-auth-token$/i)) {
                        allKeys.push(key);
                      }
                    }
                  }
                  allKeys.forEach(key => localStorage.removeItem(key));
                  sessionStorage.clear();
                  localStorage.setItem('cofind_user_logged_out', 'true');
                } catch (signOutError) {
                  console.warn('[Auth] Error signing out during auth change:', signOutError);
                }
              }
            }
          } else {
            // No logout flag - normal behavior
            if (event === 'SIGNED_OUT' || !session?.user) {
              // Explicitly handle sign out - ensure guest mode
              console.log('[Auth] User signed out - clearing state');
              setUser(null);
              setProfile(null);
            } else if (session?.user) {
              // CRITICAL: Restore session for ALL events (SIGNED_IN, TOKEN_REFRESHED, INITIAL_SESSION)
              // This ensures session is restored on page refresh
              // INITIAL_SESSION is especially important for page refresh
              
              // Restore user immediately - don't wait for profile fetch
              console.log('[Auth] Restoring session for event:', event, 'user:', session.user.id);
              setUser(session.user);
              
              // Then fetch profile in background (non-blocking)
              try {
                const { data: profileData, error: profileError } = await supabase
                  .from('profiles')
                  .select('id, username, role')
                  .eq('id', session.user.id)
                  .maybeSingle();
                
                // Handle 401 Unauthorized (RLS policy issue)
                if (profileError) {
                  if (profileError.code === 'PGRST301' || profileError.message?.includes('401') || profileError.message?.includes('Unauthorized')) {
                    console.error('[Auth] 401 Unauthorized saat fetch profile - RLS policy issue');
                    console.error('[Auth] Solusi: Pastikan RLS policy "Profiles viewable by everyone" aktif');
                    // Jangan logout - ini masalah RLS, bukan masalah user
                    // User sudah di-set di atas, hanya profile yang null
                    setProfile(null);
                    return; // Exit early, jangan logout
                  }
                  
                  // Error lain - log dan lanjutkan
                  console.error('[Auth] Error checking profile:', profileError);
                  setProfile(null);
                } else if (profileData) {
                  // Profile exists - set it
                  console.log('[Auth] Profile found - user:', session.user.id, 'role:', profileData.role);
                  await fetchProfile(session.user.id);
                  
                  // Migrate localStorage data on sign in (only for SIGNED_IN event)
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
                  // Profile not found - mungkin belum dibuat oleh trigger
                  console.warn('[Auth] Profile not found for user:', session.user.id, '- mungkin belum dibuat oleh trigger');
                  // User sudah di-set di atas, hanya profile yang null
                  setProfile(null);
                  
                  // Coba buat profile jika belum ada (fallback jika trigger tidak jalan)
                  // Only try to create on SIGNED_IN event, not on refresh events
                  if (event === 'SIGNED_IN') {
                    try {
                      const { error: insertError } = await supabase
                        .from('profiles')
                        .insert({
                          id: session.user.id,
                          username: session.user.user_metadata?.username || `user_${session.user.id.slice(0, 8)}`,
                          full_name: session.user.user_metadata?.full_name || null
                        });
                      
                      if (!insertError) {
                        console.log('[Auth] Profile created manually (trigger mungkin tidak jalan)');
                        await fetchProfile(session.user.id);
                      } else {
                        console.warn('[Auth] Failed to create profile manually:', insertError);
                      }
                    } catch (insertErr) {
                      console.warn('[Auth] Error creating profile manually:', insertErr);
                    }
                  }
                }
              } catch (profileCheckError) {
                console.error('[Auth] Error checking profile in onAuthStateChange:', profileCheckError);
                // Jangan langsung logout - mungkin hanya masalah RLS atau network
                // User sudah di-set di atas, hanya profile yang null
                setProfile(null);
              }
            }
          }
        } catch (authError) {
          console.error('[Auth] Error in onAuthStateChange:', authError);
          // CRITICAL: Don't clear user session on error - might be temporary network/RLS issue
          // Only clear if it's a SIGNED_OUT event or explicit logout
          // This prevents user from being logged out unexpectedly
          if (event === 'SIGNED_OUT') {
            setUser(null);
            setProfile(null);
          } else {
            // Keep existing state - don't logout on error
            console.warn('[Auth] Error occurred but keeping existing session state');
          }
        } finally {
          // Only update loading if initAuth has completed
          if (initAuthCompleted) {
            setLoading(false);
          }
          isProcessingAuthChange = false;
        }
      }
    );

    return () => {
      subscription?.unsubscribe();
    };
  }, []);

  // Helper: Generate internal email from username
  // Using .app domain instead of .local because Supabase requires valid email domains
  const usernameToEmail = (username) => {
    // Normalize username (lowercase, remove spaces, special chars)
    const normalized = username.toLowerCase().trim().replace(/\s+/g, '').replace(/[^a-z0-9_]/g, '');
    return `${normalized}@cofind.app`;
  };

  // Sign up with username and password (no email needed)
  const signUp = async (username, password, metadata = {}) => {
    if (!supabase) return { error: { message: 'Supabase tidak dikonfigurasi' } };
    
    // Normalize username - remove domain if user accidentally includes it
    let normalizedUsername = username.toLowerCase().trim().replace(/\s+/g, '');
    
    // Remove @cofind.local or @cofind.app if present (for backward compatibility)
    if (normalizedUsername.includes('@')) {
      normalizedUsername = normalizedUsername.split('@')[0];
    }
    
    // Validate username
    if (!normalizedUsername || normalizedUsername.length < 3) {
      return { error: { message: 'Username minimal 3 karakter' } };
    }
    
    // Check if username already exists in profiles
    const { data: existingProfile } = await supabase
      .from('profiles')
      .select('username')
      .eq('username', normalizedUsername)
      .maybeSingle();
    
    if (existingProfile) {
      return { error: { message: 'Username sudah digunakan' } };
    }
    
    // Generate internal email
    const internalEmail = usernameToEmail(normalizedUsername);
    
    // Check if email already exists (in case username was used before)
    const { data: existingUser } = await supabase.auth.admin?.listUsers();
    // Note: admin API might not be available, so we'll proceed and let Supabase handle duplicate
    
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
      // If email already exists, it means username was used
      if (error.message.includes('already registered') || error.message.includes('already exists')) {
        return { error: { message: 'Username sudah digunakan' } };
      }
    }

    return { data, error };
  };

  // Sign in with username and password (no email needed)
  const signIn = async (username, password) => {
    if (!supabase) return { error: { message: 'Supabase tidak dikonfigurasi' } };
    
    // Normalize username - remove domain if user accidentally includes it
    let normalizedUsername = username.toLowerCase().trim().replace(/\s+/g, '');
    
    // Remove @cofind.local or @cofind.app if present (for backward compatibility)
    if (normalizedUsername.includes('@')) {
      normalizedUsername = normalizedUsername.split('@')[0];
    }
    
    // Generate email from username (same pattern as signup)
    const email = usernameToEmail(normalizedUsername);
    
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password
    });

    if (error) {
      // Check if username exists in profiles (better error message)
      const { data: profile } = await supabase
        .from('profiles')
        .select('username')
        .eq('username', normalizedUsername)
        .maybeSingle();
      
      if (!profile && error.message.includes('Invalid login credentials')) {
        return { error: { message: 'Username tidak ditemukan' } };
      }
      
      if (error.message.includes('Invalid login credentials')) {
        return { error: { message: 'Username atau password salah' } };
      }
    } else {
      // Clear logout flag on successful login
      localStorage.removeItem('cofind_user_logged_out');
      console.log('[Auth] Cleared logout flag on successful login');
    }

    return { data, error };
  };

  // Sign out
  const signOut = async () => {
    if (!supabase) return { error: { message: 'Supabase tidak dikonfigurasi' } };
    
    console.log('[Auth] Starting sign out process...');
    
    try {
      // CRITICAL: Set flag FIRST to prevent any session restore
      localStorage.setItem('cofind_user_logged_out', 'true');
      console.log('[Auth] Set logout flag to prevent session restore');
      
      // Clear state immediately - force guest mode
      setUser(null);
      setProfile(null);
      
      // Sign out from Supabase with global scope
      const { error: signOutError } = await supabase.auth.signOut({ scope: 'global' });
      
      if (signOutError) {
        console.error('[Auth] Supabase signOut error:', signOutError);
      }
      
      // CRITICAL: Aggressively clear ALL Supabase-related storage
      // This ensures no session data remains
      const allKeys = [];
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key !== 'cofind_user_logged_out') {
          // Remove ALL Supabase-related keys
          if (key.includes('supabase') || 
              key.includes('sb-') || 
              key.match(/auth-token/i) ||
              key.match(/^sb-[a-z0-9-]+-auth-token$/i) ||
              key.startsWith('supabase.auth.')) {
            allKeys.push(key);
          }
        }
      }
      
      // Remove all Supabase keys
      allKeys.forEach(key => {
        try {
          localStorage.removeItem(key);
        } catch (e) {
          console.warn('[Auth] Error removing key:', key, e);
        }
      });
      
      // Clear sessionStorage completely
      try {
        sessionStorage.clear();
      } catch (e) {
        console.warn('[Auth] Error clearing sessionStorage:', e);
      }
      
      // CRITICAL: Force clear any remaining Supabase session
      // Try to get session and sign out again if it exists
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (session?.user) {
          console.log('[Auth] Session still exists after signOut - forcing another signOut');
          await supabase.auth.signOut({ scope: 'global' });
        }
      } catch (sessionCheckError) {
        console.warn('[Auth] Error checking session after signOut:', sessionCheckError);
      }
      
      // Restore logout flag (must be last)
      localStorage.setItem('cofind_user_logged_out', 'true');
      
      console.log('[Auth] Sign out complete - flag set, storage cleared, guest mode enforced');
      return { error: signOutError };
    } catch (error) {
      console.error('[Auth] Sign out exception:', error);
      
      // CRITICAL: Even if there's an error, force guest mode
      setUser(null);
      setProfile(null);
      
      // Ensure logout flag is set
      localStorage.setItem('cofind_user_logged_out', 'true');
      
      // Try to clear storage anyway (but preserve logout flag)
      try {
        const logoutFlag = localStorage.getItem('cofind_user_logged_out');
        
        // Clear all Supabase keys
        const allKeys = [];
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i);
          if (key && key !== 'cofind_user_logged_out') {
            if (key.includes('supabase') || 
                key.includes('sb-') || 
                key.match(/auth-token/i) ||
                key.match(/^sb-[a-z0-9-]+-auth-token$/i) ||
                key.startsWith('supabase.auth.')) {
              allKeys.push(key);
            }
          }
        }
        allKeys.forEach(key => localStorage.removeItem(key));
        sessionStorage.clear();
        
        // Restore logout flag
        if (logoutFlag === 'true') {
          localStorage.setItem('cofind_user_logged_out', 'true');
        }
      } catch (e) {
        console.error('[Auth] Error clearing all storage:', e);
        // Still set the flag
        localStorage.setItem('cofind_user_logged_out', 'true');
      }
      
      return { error };
    }
  };

  // Reset password (using username)
  const resetPassword = async (username) => {
    if (!supabase) return { error: { message: 'Supabase tidak dikonfigurasi' } };
    
    // Normalize username - remove domain if user accidentally includes it
    let normalizedUsername = username.toLowerCase().trim().replace(/\s+/g, '');
    
    // Remove @cofind.local or @cofind.app if present (for backward compatibility)
    if (normalizedUsername.includes('@')) {
      normalizedUsername = normalizedUsername.split('@')[0];
    }
    
    const email = usernameToEmail(normalizedUsername);
    
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
};

export default AuthContext;

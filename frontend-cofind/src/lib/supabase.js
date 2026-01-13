import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

// Check if Supabase is configured
export const isSupabaseConfigured = !!(supabaseUrl && supabaseAnonKey && 
  supabaseUrl !== 'https://your-project-id.supabase.co' &&
  supabaseAnonKey !== 'your-anon-key-here');

// Log status di development (hanya sekali)
if (import.meta.env.DEV && !window.__supabaseLogged) {
  window.__supabaseLogged = true;
  console.log('[Supabase]', isSupabaseConfigured ? '✅ Configured' : '⚠️ Not configured');
}

// SINGLETON: Cegah multiple instances saat HMR
// Simpan di window untuk persist across HMR
let supabaseInstance = null;

if (isSupabaseConfigured) {
  // Cek apakah sudah ada instance di window (dari HMR sebelumnya)
  if (typeof window !== 'undefined' && window.__supabaseClient) {
    supabaseInstance = window.__supabaseClient;
  } else {
    // Buat instance baru
    supabaseInstance = createClient(supabaseUrl, supabaseAnonKey, {
      db: {
        schema: 'public',
      },
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
      global: {
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache',
        },
      },
      realtime: {
        params: {
          eventsPerSecond: 10
        }
      }
    });
    
    // Simpan di window untuk HMR
    if (typeof window !== 'undefined') {
      window.__supabaseClient = supabaseInstance;
    }
  }
}

export const supabase = supabaseInstance;

// Helper: Validate if session is still valid (token not expired)
export const validateSession = async () => {
  if (!supabase) return { valid: false, user: null, error: 'Supabase not configured' };
  
  try {
    // Get current session
    const { data: { session }, error: sessionError } = await supabase.auth.getSession();
    
    if (sessionError) {
      console.error('[Supabase] Session validation error:', sessionError);
      return { valid: false, user: null, error: sessionError };
    }
    
    if (!session) {
      console.log('[Supabase] No active session');
      return { valid: false, user: null, error: 'No session' };
    }
    
    // Check if token is about to expire (within 5 minutes)
    const now = Date.now();
    const expiresAt = session.expires_at * 1000; // Convert to milliseconds
    const timeUntilExpiry = expiresAt - now;
    
    if (timeUntilExpiry < 0) {
      console.warn('[Supabase] Session token has expired');
      return { valid: false, user: null, error: 'Token expired' };
    }
    
    if (timeUntilExpiry < 5 * 60 * 1000) {
      console.warn('[Supabase] Session token expiring soon, refreshing...');
      // Try to refresh token
      const { data: { session: refreshedSession }, error: refreshError } = await supabase.auth.refreshSession();
      if (refreshError || !refreshedSession) {
        console.error('[Supabase] Token refresh failed:', refreshError);
        return { valid: false, user: null, error: refreshError };
      }
      return { valid: true, user: refreshedSession.user, session: refreshedSession };
    }
    
    return { valid: true, user: session.user, session };
  } catch (error) {
    console.error('[Supabase] Exception during session validation:', error);
    return { valid: false, user: null, error };
  }
};

// Helper: Get current user
export const getCurrentUser = async () => {
  if (!supabase) return null;
  const validation = await validateSession();
  return validation.valid ? validation.user : null;
};

// Helper: Generate correct photo URL for coffee shop using getPublicUrl
// This ensures we always use the project-specific Supabase domain
export const getCoffeeShopPhotoUrl = (placeId) => {
  if (!supabase || !placeId) {
    console.warn('[Supabase] getCoffeeShopPhotoUrl: Missing supabase or placeId');
    return null;
  }
  
  try {
    const filename = `${placeId}.webp`;
    const { data } = supabase.storage
      .from('coffee_shops')
      .getPublicUrl(filename);
    
    return data?.publicUrl || null;
  } catch (error) {
    console.error('[Supabase] Error generating coffee shop photo URL:', error);
    return null;
  }
};

// Helper: Bulk update all coffee shop URLs in database using getPublicUrl
export const bulkUpdateAllPhotoUrls = async () => {
  if (!supabase || !isSupabaseConfigured) {
    console.error('[Supabase] bulkUpdateAllPhotoUrls: Supabase not configured');
    return { error: 'Supabase not configured', updated: 0 };
  }

  try {
    console.log('[Supabase] Starting bulk update of all photo URLs...');
    
    // Fetch all places
    const { data: places, error: fetchError } = await supabase
      .from('places')
      .select('place_id, name')
      .order('name');
    
    if (fetchError || !places) {
      console.error('[Supabase] Error fetching places:', fetchError);
      return { error: fetchError, updated: 0 };
    }

    console.log(`[Supabase] Found ${places.length} places to update`);

    let updated = 0;
    const BATCH_SIZE = 10;

    // Process in batches to avoid overwhelming Supabase
    for (let i = 0; i < places.length; i += BATCH_SIZE) {
      const batch = places.slice(i, i + BATCH_SIZE);
      
      await Promise.all(
        batch.map(async (place) => {
          try {
            // Generate correct URL using getPublicUrl
            const correctUrl = getCoffeeShopPhotoUrl(place.place_id);
            
            if (correctUrl) {
              const { error: updateError } = await supabase
                .from('places')
                .update({ photo_url: correctUrl })
                .eq('place_id', place.place_id);
              
              if (!updateError) {
                console.log(`✅ Updated: ${place.name} (${place.place_id})`);
                updated++;
              } else {
                console.warn(`⚠️  Failed to update ${place.name}:`, updateError);
              }
            }
          } catch (err) {
            console.error(`❌ Error updating ${place.place_id}:`, err);
          }
        })
      );
    }

    console.log(`[Supabase] Bulk update complete: ${updated}/${places.length} places updated`);
    return { success: true, updated, total: places.length };
  } catch (error) {
    console.error('[Supabase] Exception during bulk update:', error);
    return { error, updated: 0 };
  }
};

// Helper: Get user profile
export const getUserProfile = async (userId) => {
  if (!supabase || !userId) return null;
  
  try {
    const { data, error } = await supabase
      .from('profiles')
      .select('*')
      .eq('id', userId)
      .maybeSingle();
    
    if (error) {
      console.error('[Supabase] Error fetching profile:', error.message);
      return null;
    }
    
    return data;
  } catch (err) {
    console.error('[Supabase] Exception:', err);
    return null;
  }
};

// Helper: Update user profile
export const updateUserProfile = async (userId, updates) => {
  if (!supabase) return { error: 'Supabase not configured' };
  
  const { data, error } = await supabase
    .from('profiles')
    .update(updates)
    .eq('id', userId)
    .select()
    .single();
  
  return { data, error };
};

// Helper: Clear all Supabase session data
export const clearSupabaseSession = async () => {
  if (!supabase) return;
  
  try {
    // Sign out from Supabase
    const { error } = await supabase.auth.signOut({ scope: 'local' });
    if (error) {
      console.warn('[Supabase] Sign out error:', error);
    }
  } catch (error) {
    console.error('[Supabase] Exception during sign out:', error);
  }
  
  // Clear ALL Supabase-related localStorage keys
  try {
    const keysToRemove = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && (
        key.startsWith('sb-') || // Supabase session tokens
        key.includes('supabase') || // Any supabase-related key
        key === 'SUPABASE_AUTH_TOKEN' // Legacy tokens
      )) {
        keysToRemove.push(key);
      }
    }
    
    keysToRemove.forEach(key => {
      try {
        localStorage.removeItem(key);
        console.log(`[Supabase] Cleared localStorage key: ${key}`);
      } catch (e) {
        console.warn(`[Supabase] Failed to clear localStorage key: ${key}`, e);
      }
    });
  } catch (error) {
    console.error('[Supabase] Error clearing localStorage:', error);
  }
};

// Helper: Upload avatar
export const uploadAvatar = async (userId, file) => {
  if (!supabase) return { error: 'Supabase not configured' };
  
  try {
    const fileExt = file.name.split('.').pop();
    const fileName = `${Date.now()}.${fileExt}`;
    const filePath = `avatars/${userId}/${fileName}`;

    const { error: uploadError } = await supabase.storage
      .from('review-photos')
      .upload(filePath, file, {
        cacheControl: '3600',
        upsert: false
      });

    if (uploadError) {
      return { error: uploadError };
    }

    const { data: { publicUrl } } = supabase.storage
      .from('review-photos')
      .getPublicUrl(filePath);

    return { url: publicUrl };
  } catch (error) {
    return { error };
  }
};

// Load console helper functions untuk bulk photo updates (development)
if (import.meta.env.DEV) {
  try {
    import('../utils/consolePhotoUpdate.js');
    import('../utils/consolePhotoUpdate_v2.js'); // Load v2 with getPublicUrl approach
  } catch {
    console.log('[Supabase] Console helpers not available');
  }
}
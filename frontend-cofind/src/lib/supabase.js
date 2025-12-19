import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

// Debug logging untuk verifikasi env variables ter-load
if (import.meta.env.DEV) {
  console.log('[Supabase Config] Environment variables check:', {
    hasUrl: !!supabaseUrl,
    hasKey: !!supabaseAnonKey,
    urlValue: supabaseUrl ? `${supabaseUrl.substring(0, 30)}...` : 'undefined',
    keyValue: supabaseAnonKey ? `${supabaseAnonKey.substring(0, 20)}...` : 'undefined',
    urlIsDefault: supabaseUrl === 'https://your-project-id.supabase.co',
    keyIsDefault: supabaseAnonKey === 'your-anon-key-here'
  });
}

// Check if Supabase is configured
export const isSupabaseConfigured = !!(supabaseUrl && supabaseAnonKey && 
  supabaseUrl !== 'https://your-project-id.supabase.co' &&
  supabaseAnonKey !== 'your-anon-key-here');

// Log configuration status
if (import.meta.env.DEV) {
  console.log('[Supabase Config] isSupabaseConfigured:', isSupabaseConfigured);
  if (!isSupabaseConfigured) {
    console.warn('[Supabase Config] ⚠️ Supabase tidak dikonfigurasi!');
    console.warn('[Supabase Config] Pastikan file .env ada di folder frontend-cofind/');
    console.warn('[Supabase Config] Pastikan dev server di-restart setelah membuat/mengubah .env');
    console.warn('[Supabase Config] Cek: VITE_SUPABASE_URL dan VITE_SUPABASE_ANON_KEY');
  } else {
    console.log('[Supabase Config] ✅ Supabase dikonfigurasi dengan benar');
  }
}

// Create Supabase client (or null if not configured)
// Configure with cache-busting to prevent browser caching
// CRITICAL: persistSession: true ensures session persists in localStorage
// This means session will remain after tab close, but will be cleared when browser is closed
// (localStorage persists across tabs but is cleared when browser is closed)
export const supabase = isSupabaseConfigured 
  ? createClient(supabaseUrl, supabaseAnonKey, {
      db: {
        schema: 'public',
      },
      auth: {
        persistSession: true, // CRITICAL: Session persists in localStorage (survives tab close)
        autoRefreshToken: true, // Auto-refresh token to keep session alive
        detectSessionInUrl: true, // Detect session from URL (for OAuth callbacks)
        storage: typeof window !== 'undefined' ? window.localStorage : undefined, // Explicitly use localStorage
        storageKey: 'sb-auth-token', // Default storage key (can be customized)
      },
      global: {
        // Custom fetch function to force no-cache
        // CRITICAL: Preserve all existing headers (especially apikey and Authorization)
        fetch: (url, options = {}) => {
          // Convert Headers object to plain object if needed
          let existingHeaders = {};
          if (options.headers) {
            if (options.headers instanceof Headers) {
              // Convert Headers object to plain object
              options.headers.forEach((value, key) => {
                existingHeaders[key] = value;
              });
            } else if (typeof options.headers === 'object') {
              // Already a plain object
              existingHeaders = { ...options.headers };
            }
          }
          
          // CRITICAL: Jangan tambahkan query parameter cache-busting di URL Supabase
          // PostgREST akan menginterpretasikan semua query params sebagai filter
          // Ini menyebabkan error "failed to parse filter" jika kita tambahkan _t=timestamp
          // Gunakan hanya headers untuk cache-busting, bukan query parameter
          
          // Merge headers: preserve existing (especially apikey, Authorization) + add cache headers
          const mergedHeaders = {
            ...existingHeaders, // CRITICAL: Preserve Supabase headers (apikey, Authorization, etc.)
            'Cache-Control': 'no-cache, no-store, must-revalidate, max-age=0',
            'Pragma': 'no-cache',
            'Expires': '0',
            'If-Modified-Since': '0', // Prevent 304 responses
            // Add timestamp untuk cache-busting di header (bukan query param)
            'X-Request-Time': existingHeaders['X-Request-Time'] || Date.now().toString()
          };
          
          // Force no-cache untuk semua Supabase requests
          // JANGAN modifikasi URL - biarkan Supabase client handle query params dengan benar
          const noCacheOptions = {
            ...options,
            cache: 'no-store', // Force no cache
            headers: mergedHeaders
          };
          
          console.log('[Supabase] Fetching (NO CACHE):', url);
          return fetch(url, noCacheOptions);
        }
      }
    })
  : null;

// Helper function to check if user is authenticated
export const getCurrentUser = async () => {
  if (!supabase) return null;
  const { data: { user } } = await supabase.auth.getUser();
  return user;
};

// Helper function to get user profile
export const getUserProfile = async (userId) => {
  if (!supabase) return null;
  
  try {
    const { data, error } = await supabase
      .from('profiles')
      .select('*')
      .eq('id', userId)
      .maybeSingle(); // Use maybeSingle() instead of single() to handle missing profiles gracefully
    
    if (error) {
      // Log error details untuk debugging
      console.error('[getUserProfile] Error fetching profile:', {
        code: error.code,
        message: error.message,
        details: error.details,
        hint: error.hint,
        userId: userId
      });
      
      // 401 Unauthorized biasanya berarti RLS policy issue
      if (error.code === 'PGRST301' || error.message?.includes('401') || error.message?.includes('Unauthorized')) {
        console.error('[getUserProfile] 401 Unauthorized - RLS policy mungkin tidak mengizinkan akses. Cek RLS policy untuk profiles table.');
        // Jangan return null untuk 401, throw error agar bisa di-handle berbeda
        throw new Error('RLS_POLICY_ERROR: User tidak bisa mengakses profile mereka sendiri. Cek RLS policy.');
      }
      
      // PGRST116 = not found (profile tidak ada)
      if (error.code === 'PGRST116') {
        console.warn('[getUserProfile] Profile not found (PGRST116) - profile mungkin belum dibuat oleh trigger');
        return null; // Profile tidak ada, tapi ini normal untuk user baru
      }
      
      // Error lain
      return null;
    }
    
    return data; // Will be null if profile doesn't exist
  } catch (err) {
    console.error('[getUserProfile] Exception:', err);
    // Jika RLS error, throw lagi agar bisa di-handle
    if (err.message?.includes('RLS_POLICY_ERROR')) {
      throw err;
    }
    return null;
  }
};

// Helper function to update user profile
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

// Helper to upload avatar
export const uploadAvatar = async (userId, file) => {
  if (!supabase) return { error: 'Supabase not configured' };
  
  const fileExt = file.name.split('.').pop();
  const fileName = `${userId}-${Date.now()}.${fileExt}`;
  const filePath = `avatars/${fileName}`;

  const { error: uploadError } = await supabase.storage
    .from('review-photos')
    .upload(filePath, file);

  if (uploadError) {
    return { error: uploadError };
  }

  const { data: { publicUrl } } = supabase.storage
    .from('review-photos')
    .getPublicUrl(filePath);

  return { url: publicUrl };
};

export default supabase;

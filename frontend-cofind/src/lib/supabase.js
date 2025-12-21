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
        // CRITICAL: Wrap localStorage access in try-catch to handle cleared site data
        storage: (() => {
          if (typeof window === 'undefined') return undefined;
          try {
            // Test if localStorage is accessible
            const test = '__localStorage_test__';
            localStorage.setItem(test, '1');
            localStorage.removeItem(test);
            return window.localStorage;
          } catch (e) {
            console.warn('[Supabase] localStorage not accessible (might be cleared), using memory storage:', e);
            // Return a simple memory-based storage as fallback
            const memoryStorage = {
              getItem: () => null,
              setItem: () => {},
              removeItem: () => {},
              clear: () => {},
            };
            return memoryStorage;
          }
        })(),
        storageKey: 'sb-auth-token', // Default storage key (can be customized)
      },
      global: {
        // Custom fetch function dengan timeout handling dan no-cache
        // CRITICAL: Preserve all existing headers (especially apikey and Authorization)
        // OPTIMIZED: Add timeout handling untuk prevent hanging requests
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
          
          // DEBUG: Check if apikey exists in headers
          if (!existingHeaders['apikey'] && !existingHeaders['Authorization']) {
            console.error('[Supabase] ⚠️ WARNING: No apikey or Authorization header found!', {
              url: url.split('?')[0],
              headers: Object.keys(existingHeaders)
            });
          }
          
          // CRITICAL: Jangan tambahkan query parameter cache-busting di URL Supabase
          // PostgREST akan menginterpretasikan semua query params sebagai filter
          // Ini menyebabkan error "failed to parse filter" jika kita tambahkan _t=timestamp
          // Gunakan hanya headers untuk cache-busting, bukan query parameter
          
          // Merge headers: preserve existing (especially apikey, Authorization) + add cache headers
          // CRITICAL: Put cache headers BEFORE existing headers to ensure apikey is not overwritten
          const mergedHeaders = {
            'Cache-Control': 'no-cache, no-store, must-revalidate, max-age=0',
            'Pragma': 'no-cache',
            'Expires': '0',
            'If-Modified-Since': '0', // Prevent 304 responses
            'X-Request-Time': Date.now().toString(),
            ...existingHeaders // CRITICAL: Preserve Supabase headers (apikey, Authorization, etc.) - MUST BE LAST!
          };
          
          // OPTIMIZED: Add timeout handling dengan AbortController
          // Default timeout: 30 detik (lebih panjang dari query-level timeout 15s untuk handle network delay)
          // Jika request sudah memiliki signal (untuk query-level timeout), gunakan itu
          // Jika tidak, buat signal baru untuk client-level timeout
          const requestTimeout = 30000; // 30 detik - client-level timeout untuk handle slow queries
          const controller = new AbortController();
          let timeoutId = null;
          
          // Check if options already has a signal (from query-level timeout)
          const existingSignal = options.signal;
          const finalSignal = existingSignal || controller.signal;
          
          // Set timeout hanya jika tidak ada existing signal
          // (query-level timeout sudah handle timeout untuk specific queries)
          if (!existingSignal) {
            timeoutId = setTimeout(() => {
              console.warn(`[Supabase] ⏱️ Request timeout after ${requestTimeout}ms:`, url);
              controller.abort();
            }, requestTimeout);
          }
          
          // Force no-cache untuk semua Supabase requests
          // JANGAN modifikasi URL - biarkan Supabase client handle query params dengan benar
          const noCacheOptions = {
            ...options,
            cache: 'no-store', // Force no cache
            headers: mergedHeaders,
            signal: finalSignal // Use final signal (existing or new)
          };
          
          const startTime = Date.now();
          
          // DEBUG: Log request info
          if (import.meta.env.DEV) {
            console.log('[Supabase] Fetching:', {
              url: url.split('?')[0],
              hasApiKey: !!mergedHeaders['apikey'],
              hasAuth: !!mergedHeaders['Authorization'],
              headers: Object.keys(mergedHeaders).filter(k => !k.startsWith('X-'))
            });
          }
          
          // Return fetch dengan proper cleanup
          return fetch(url, noCacheOptions)
            .then((response) => {
              // Clear timeout on success
              if (timeoutId) {
                clearTimeout(timeoutId);
              }
              const duration = Date.now() - startTime;
              if (duration > 5000) {
                console.warn(`[Supabase] ⚠️ Slow request: ${duration}ms for`, url);
              }
              return response;
            })
            .catch((error) => {
              // Clear timeout on error
              if (timeoutId) {
                clearTimeout(timeoutId);
              }
              const duration = Date.now() - startTime;
              
              // Check if it's a timeout or abort error
              if (error.name === 'AbortError' || error.message?.includes('aborted')) {
                // Abort is often intentional (component unmount, navigation, etc.)
                // Log as info instead of error to reduce console noise
                if (duration < 100) {
                  // Very quick abort (< 100ms) is usually intentional cleanup
                  console.log(`[Supabase] 🛑 Request aborted after ${duration}ms (likely component unmount):`, url.split('?')[0]);
                } else {
                  console.warn(`[Supabase] ⏱️ Request aborted after ${duration}ms:`, url.split('?')[0]);
                }
                throw new Error(`Request aborted after ${duration}ms`);
              }
              
              console.error(`[Supabase] ❌ Request error after ${duration}ms:`, error);
              throw error;
            });
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
  
  try {
    const fileExt = file.name.split('.').pop();
    const fileName = `${Date.now()}.${fileExt}`;
    // CRITICAL: Path structure must be: avatars/{userId}/{filename}
    // This matches the RLS policy that checks (storage.foldername(name))[2] = userId
    const filePath = `avatars/${userId}/${fileName}`;

    console.log('[uploadAvatar] Uploading to path:', filePath);

    // OPTIMIZED: Add upsert option to replace old avatar if exists
    const { data: uploadData, error: uploadError } = await supabase.storage
      .from('review-photos')
      .upload(filePath, file, {
        cacheControl: '3600',
        upsert: false // Don't replace, use unique filenames
      });

    if (uploadError) {
      console.error('[uploadAvatar] Upload error:', uploadError);
      return { error: uploadError };
    }

    console.log('[uploadAvatar] Upload successful:', uploadData);

    // Get public URL
    const { data: { publicUrl } } = supabase.storage
      .from('review-photos')
      .getPublicUrl(filePath);

    console.log('[uploadAvatar] Public URL:', publicUrl);

    return { url: publicUrl };
  } catch (error) {
    console.error('[uploadAvatar] Exception:', error);
    return { error: error };
  }
};

export default supabase;

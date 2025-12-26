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

// Helper: Get current user
export const getCurrentUser = async () => {
  if (!supabase) return null;
  const { data: { user } } = await supabase.auth.getUser();
  return user;
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

// Helper: Upload avatar
export const uploadAvatar = async (userId, file) => {
  if (!supabase) return { error: 'Supabase not configured' };
  
  try {
    const fileExt = file.name.split('.').pop();
    const fileName = `${Date.now()}.${fileExt}`;
    const filePath = `avatars/${userId}/${fileName}`;

    const { data: uploadData, error: uploadError } = await supabase.storage
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

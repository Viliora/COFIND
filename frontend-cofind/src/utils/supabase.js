import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseKey =
  import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY ||
  import.meta.env.VITE_SUPABASE_ANON_KEY;

let client = null;

/**
 * Supabase browser client (Framework / @supabase/supabase-js).
 * Data aplikasi utama tetap lewat Flask API; client ini untuk fitur Supabase langsung
 * (auth, storage, realtime) bila RLS & kebijakan sudah diset.
 */
export function getSupabaseClient() {
  if (!supabaseUrl || !supabaseKey) {
    if (import.meta.env.DEV) {
      console.warn(
        '[supabase] VITE_SUPABASE_URL dan VITE_SUPABASE_PUBLISHABLE_KEY (atau VITE_SUPABASE_ANON_KEY) belum diset.',
      );
    }
    return null;
  }
  if (!client) {
    client = createClient(supabaseUrl, supabaseKey);
  }
  return client;
}

/** @deprecated Prefer getSupabaseClient() agar env kosong tidak crash saat import. */
export const supabase = getSupabaseClient();

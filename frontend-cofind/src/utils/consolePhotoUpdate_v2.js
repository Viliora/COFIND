/**
 * Console helper to update all coffee shop photo URLs in Supabase database
 * Using getPublicUrl() to generate correct project-specific URLs
 * 
 * Usage in browser console:
 * window.updateAllPhotoUrlsV2()
 */

import { supabase, isSupabaseConfigured, bulkUpdateAllPhotoUrls } from '../lib/supabase';

// Expose to window for easy console access
if (typeof window !== 'undefined') {
  window.updateAllPhotoUrlsV2 = async () => {
    console.log('🔄 [Console] Starting photo URL update...');
    
    if (!isSupabaseConfigured || !supabase) {
      console.error('❌ Supabase not configured');
      return;
    }
    
    const result = await bulkUpdateAllPhotoUrls();
    
    if (result.success) {
      console.log(`✅ Successfully updated ${result.updated}/${result.total} coffee shops`);
      console.log('🔄 Refresh page to see updated photos');
    } else {
      console.error('❌ Update failed:', result.error);
    }
  };

  console.log('[Console Photo Update V2] Available: window.updateAllPhotoUrlsV2()');
}

export { bulkUpdateAllPhotoUrls };

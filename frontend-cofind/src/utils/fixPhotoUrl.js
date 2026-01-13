/**
 * Auto-fix untuk photo URL yang salah format
 * Script untuk mengoreksi dan update semua photo_url ke format yang benar
 */

import { supabase, isSupabaseConfigured } from '../lib/supabase';
import { generateCorrectPhotoUrl } from './diagnosticPhotoUrl';

/**
 * Fix single photo URL
 * @param {string} placeId - Place ID
 * @param {string} currentUrl - Current URL (mungkin salah format)
 * @returns {object} - { success: boolean, oldUrl: string, newUrl: string, error?: string }
 */
export const fixSinglePhotoUrl = async (placeId, currentUrl) => {
  if (!isSupabaseConfigured || !supabase) {
    throw new Error('Supabase not configured');
  }

  try {
    const newUrl = generateCorrectPhotoUrl(placeId);

    const { error } = await supabase
      .from('places')
      .update({ photo_url: newUrl })
      .eq('place_id', placeId);

    if (error) {
      return {
        success: false,
        placeId,
        oldUrl: currentUrl,
        newUrl,
        error: error.message,
      };
    }

    return {
      success: true,
      placeId,
      oldUrl: currentUrl,
      newUrl,
    };
  } catch (err) {
    return {
      success: false,
      placeId,
      oldUrl: currentUrl,
      error: err.message,
    };
  }
};

/**
 * Fix all photo URLs
 * @returns {object} - Statistics
 */
export const fixAllPhotoUrls = async () => {
  if (!isSupabaseConfigured || !supabase) {
    throw new Error('Supabase not configured');
  }

  try {
    console.log('🔧 [FIX] Starting to fix all photo URLs...');

    // Get all places
    const { data: places, error: fetchError } = await supabase
      .from('places')
      .select('place_id, name, photo_url')
      .order('name');

    if (fetchError) {
      console.error('[FIX] Fetch error:', fetchError);
      throw fetchError;
    }

    if (!places || places.length === 0) {
      console.warn('[FIX] No places found');
      return { total: 0, fixed: 0, skipped: 0, errors: [] };
    }

    const stats = {
      total: places.length,
      fixed: 0,
      skipped: 0,
      errors: [],
    };

    console.log(`[FIX] Found ${places.length} places. Processing...`);

    // Process in batches to avoid rate limiting
    const batchSize = 5;
    for (let i = 0; i < places.length; i += batchSize) {
      const batch = places.slice(i, i + batchSize);

      const promises = batch.map(async (place) => {
        const { place_id, name, photo_url } = place;

        // Skip if already has correct format
        if (
          photo_url &&
          (photo_url.includes('cpnzglvpqyugtacodwtr.supabase.co') || photo_url.includes('storage.supabase.co')) &&
          photo_url.includes('/storage/v1/object/public/coffee_shops/')
        ) {
          console.log(`⏭️  Skipped: ${name} (already correct format)`);
          stats.skipped++;
          return;
        }

        console.log(`🔧 Fixing: ${name} (${place_id})`);
        const result = await fixSinglePhotoUrl(place_id, photo_url);

        if (result.success) {
          console.log(`   ✅ Fixed`);
          stats.fixed++;
        } else {
          console.error(`   ❌ Error: ${result.error}`);
          stats.errors.push({
            placeId: place_id,
            name,
            error: result.error,
          });
        }
      });

      await Promise.all(promises);
    }

    console.log('\n✅ [FIX] Completed!');
    console.log(`   ✅ Fixed: ${stats.fixed}/${stats.total}`);
    console.log(`   ⏭️  Skipped: ${stats.skipped}/${stats.total}`);
    if (stats.errors.length > 0) {
      console.log(`   ❌ Errors: ${stats.errors.length}`);
      stats.errors.forEach((err) => {
        console.log(`      - ${err.name}: ${err.error}`);
      });
    }

    return stats;
  } catch (err) {
    console.error('[FIX] Error:', err);
    throw err;
  }
};

/**
 * Batch update using SQL-like approach
 * Updates all NULL or incorrectly formatted URLs in one operation
 */
export const fixAllPhotoUrlsBulk = async () => {
  if (!isSupabaseConfigured || !supabase) {
    throw new Error('Supabase not configured');
  }

  try {
    console.log('🔧 [BULK FIX] Starting bulk fix operation...');

    // Get all places with missing or invalid URLs
    const { data: places, error: fetchError } = await supabase
      .from('places')
      .select('place_id, name, photo_url')
      .order('name');

    if (fetchError) {
      throw fetchError;
    }

    if (!places || places.length === 0) {
      console.warn('[BULK FIX] No places found');
      return;
    }

    // Filter places yang perlu difix
    const needsFix = places.filter(
      (p) =>
        !p.photo_url ||
        (!p.photo_url.includes('cpnzglvpqyugtacodwtr.supabase.co') && !p.photo_url.includes('storage.supabase.co')) ||
        !p.photo_url.includes('/storage/v1/object/public/coffee_shops/')
    );

    console.log(`[BULK FIX] Found ${needsFix.length} places to fix`);

    let fixed = 0;
    for (const place of needsFix) {
      const newUrl = generateCorrectPhotoUrl(place.place_id);

      const { error } = await supabase
        .from('places')
        .update({ photo_url: newUrl })
        .eq('place_id', place.place_id);

      if (!error) {
        fixed++;
        console.log(`✅ Fixed: ${place.name}`);
      } else {
        console.error(`❌ Failed: ${place.name} - ${error.message}`);
      }
    }

    console.log(`\n✅ [BULK FIX] Completed! Fixed ${fixed}/${needsFix.length} places`);

    return {
      total: places.length,
      fixed,
      remaining: needsFix.length - fixed,
    };
  } catch (err) {
    console.error('[BULK FIX] Error:', err);
    throw err;
  }
};

// Export untuk console usage
window.fixPhotoUrl = {
  fixSinglePhotoUrl,
  fixAllPhotoUrls,
  fixAllPhotoUrlsBulk,
};

console.log('✅ Photo URL fix functions loaded. Use window.fixPhotoUrl.fixAllPhotoUrls() in console to fix all URLs');

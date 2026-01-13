import { supabase, isSupabaseConfigured } from '../lib/supabase';

/**
 * Bulk update photo URLs untuk semua coffee shops
 * Setiap place_id akan mendapat photo_url dengan template:
 * https://cpnzglvpqyugtacodwtr.supabase.co/storage/v1/object/public/coffee_shops/{place_id}.webp
 */
export const bulkUpdatePhotoUrls = async () => {
  if (!isSupabaseConfigured || !supabase) {
    throw new Error('Supabase not configured');
  }

  try {
    console.log('[bulkUpdatePhotoUrls] Starting bulk update...');

    // Get all places
    const { data: places, error: fetchError } = await supabase
      .from('places')
      .select('place_id, name, photo_url');

    if (fetchError) {
      console.error('[bulkUpdatePhotoUrls] Fetch error:', fetchError);
      throw fetchError;
    }

    if (!places || places.length === 0) {
      console.warn('[bulkUpdatePhotoUrls] No places found');
      return { total: 0, updated: 0, skipped: 0 };
    }

    console.log(`[bulkUpdatePhotoUrls] Found ${places.length} places`);

    const PHOTO_URL_TEMPLATE = 'https://cpnzglvpqyugtacodwtr.supabase.co/storage/v1/object/public/coffee_shops/{place_id}.webp';
    let updated = 0;
    let skipped = 0;

    // Process each place
    for (const place of places) {
      const placeId = place.place_id;
      const currentPhotoUrl = place.photo_url;

      // Generate new photo URL
      const newPhotoUrl = PHOTO_URL_TEMPLATE.replace('{place_id}', placeId);

      // Skip if already has Supabase URL
      if (currentPhotoUrl && (currentPhotoUrl.includes('cpnzglvpqyugtacodwtr.supabase.co') || currentPhotoUrl.includes('storage.supabase.co'))) {
        console.log(`⏭️  Skipped: ${place.name}`);
        skipped++;
        continue;
      }

      // Update photo_url
      console.log(`📤 Updating: ${place.name}`);
      const { error: updateError } = await supabase
        .from('places')
        .update({ photo_url: newPhotoUrl })
        .eq('place_id', placeId);

      if (updateError) {
        console.error(`❌ Update failed for ${place.name}:`, updateError);
        continue;
      }

      console.log(`✅ Updated: ${place.name}`);
      updated++;
    }

    console.log(`\n📊 Bulk update completed:`);
    console.log(`   ✅ Updated: ${updated}`);
    console.log(`   ⏭️  Skipped: ${skipped}`);
    console.log(`   📝 Total: ${places.length}`);

    return {
      total: places.length,
      updated,
      skipped,
    };
  } catch (err) {
    console.error('[bulkUpdatePhotoUrls] Failed:', err);
    throw err;
  }
};

/**
 * Verify photo URLs - check apakah semua places punya valid photo_url
 */
export const verifyPhotoUrls = async () => {
  if (!isSupabaseConfigured || !supabase) {
    throw new Error('Supabase not configured');
  }

  try {
    console.log('[verifyPhotoUrls] Starting verification...');

    const { data: places, error } = await supabase
      .from('places')
      .select('place_id, name, photo_url');

    if (error) throw error;

    const results = {
      total: places.length,
      withUrl: 0,
      withoutUrl: 0,
      invalidUrl: 0,
      validSupabaseUrl: 0,
      details: [],
    };

    for (const place of places) {
      const { place_id, name, photo_url } = place;

      if (!photo_url) {
        results.withoutUrl++;
        results.details.push({ place_id, name, status: 'MISSING' });
      } else if (!photo_url.includes('cpnzglvpqyugtacodwtr.supabase.co') && !photo_url.includes('storage.supabase.co')) {
        results.invalidUrl++;
        results.details.push({ place_id, name, status: 'INVALID', url: photo_url });
      } else if (photo_url.includes('{place_id}')) {
        results.invalidUrl++;
        results.details.push({ place_id, name, status: 'UNRESOLVED_TEMPLATE', url: photo_url });
      } else {
        results.validSupabaseUrl++;
        results.details.push({ place_id, name, status: 'VALID' });
      }
    }

    results.withUrl = results.validSupabaseUrl + results.invalidUrl;

    console.log('\n📊 Verification results:');
    console.log(`   ✅ Valid Supabase URLs: ${results.validSupabaseUrl}`);
    console.log(`   ⚠️  Invalid URLs: ${results.invalidUrl}`);
    console.log(`   ❌ Missing URLs: ${results.withoutUrl}`);
    console.log(`   📝 Total: ${results.total}`);

    return results;
  } catch (err) {
    console.error('[verifyPhotoUrls] Failed:', err);
    throw err;
  }
};

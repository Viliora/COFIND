// Load console helper functions untuk bulk photo updates (development)
window.updatePhotoUrls = async () => {
  try {
    console.log('📤 Starting bulk photo URL update...');
    
    // Use Supabase client that's already exposed to window
    const supabase = window.__supabaseClient;
    if (!supabase) {
      throw new Error('Supabase client not available. App may not be fully loaded.');
    }
    
    // Get all places
    const { data: places, error: fetchError } = await supabase
      .from('places')
      .select('place_id, name, photo_url');

    if (fetchError) {
      console.error('❌ Fetch error:', fetchError);
      return;
    }

    if (!places || places.length === 0) {
      console.warn('⚠️ No places found');
      return;
    }

    console.log(`📊 Found ${places.length} places`);

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

    console.log(`\n📊 Update completed:`);
    console.log(`   ✅ Updated: ${updated}`);
    console.log(`   ⏭️  Skipped: ${skipped}`);
    console.log(`   📝 Total: ${places.length}`);

    return { updated, skipped, total: places.length };
  } catch (err) {
    console.error('❌ Error:', err);
  }
};

// Also expose verify function
window.verifyPhotoUrls = async () => {
  try {
    console.log('🔍 Starting photo URL verification...');
    
    const supabase = window.__supabaseClient;
    if (!supabase) {
      throw new Error('Supabase client not available.');
    }
    
    const { data: places, error } = await supabase
      .from('places')
      .select('place_id, name, photo_url');

    if (error) {
      console.error('❌ Error:', error);
      return;
    }

    const results = {
      total: places.length,
      validSupabaseUrl: 0,
      invalidUrl: 0,
      withoutUrl: 0,
    };

    const issues = [];

    for (const place of places) {
      const { place_id, name, photo_url } = place;

      if (!photo_url) {
        results.withoutUrl++;
        issues.push(`[MISSING] ${name} (${place_id})`);
      } else if (!photo_url.includes('cpnzglvpqyugtacodwtr.supabase.co') && !photo_url.includes('storage.supabase.co')) {
        results.invalidUrl++;
        issues.push(`[INVALID] ${name}: ${photo_url}`);
      } else if (photo_url.includes('{place_id}')) {
        results.invalidUrl++;
        issues.push(`[UNRESOLVED] ${name}: ${photo_url}`);
      } else {
        results.validSupabaseUrl++;
      }
    }

    console.log(`\n📊 Verification results:`);
    console.log(`   ✅ Valid: ${results.validSupabaseUrl}`);
    console.log(`   ⚠️  Invalid: ${results.invalidUrl}`);
    console.log(`   ❌ Missing: ${results.withoutUrl}`);
    console.log(`   📝 Total: ${results.total}`);

    if (issues.length > 0) {
      console.log(`\n❌ Issues found:`);
      issues.forEach(issue => console.log('   ' + issue));
    }

    return results;
  } catch (err) {
    console.error('❌ Error:', err);
  }
};

console.log('✅ Photo update functions loaded');
console.log('Use: window.updatePhotoUrls() to update all photos');
console.log('Use: window.verifyPhotoUrls() to verify photos');

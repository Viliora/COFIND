import { supabase, isSupabaseConfigured } from '../lib/supabase';

/**
 * Upload coffee shop photo to Supabase Storage
 * @param {string} placeId - Coffee shop place_id
 * @param {File} file - Image file to upload
 * @returns {Promise<string>} Public URL of uploaded image
 */
export const uploadCoffeeShopPhoto = async (placeId, file) => {
  if (!isSupabaseConfigured || !supabase) {
    throw new Error('Supabase not configured');
  }

  try {
    const bucket = 'coffee_shops';
    const fileName = `${placeId}.webp`; // Use place_id as filename for consistency
    
    console.log(`[uploadCoffeeShopPhoto] Uploading photo for ${placeId}...`);

    // Upload to Supabase Storage
    const { data, error: uploadError } = await supabase.storage
      .from(bucket)
      .upload(fileName, file, {
        cacheControl: '3600',
        upsert: true, // Replace if exists
      });

    if (uploadError) {
      console.error('[uploadCoffeeShopPhoto] Upload error:', uploadError);
      throw uploadError;
    }

    // Get public URL
    const { data: publicUrlData } = supabase.storage
      .from(bucket)
      .getPublicUrl(fileName);

    const photoUrl = publicUrlData?.publicUrl;
    console.log('[uploadCoffeeShopPhoto] Upload success:', photoUrl);

    return photoUrl;
  } catch (err) {
    console.error('[uploadCoffeeShopPhoto] Failed:', err);
    throw err;
  }
};

/**
 * Update places table with photo URL
 * @param {string} placeId - Coffee shop place_id
 * @param {string} photoUrl - Public URL from Supabase Storage
 */
export const updateCoffeeShopPhotoUrl = async (placeId, photoUrl) => {
  if (!isSupabaseConfigured || !supabase) {
    throw new Error('Supabase not configured');
  }

  try {
    console.log(`[updateCoffeeShopPhotoUrl] Updating ${placeId} with photo_url...`);

    const { error } = await supabase
      .from('places')
      .update({ photo_url: photoUrl })
      .eq('place_id', placeId);

    if (error) {
      console.error('[updateCoffeeShopPhotoUrl] Update error:', error);
      throw error;
    }

    console.log('[updateCoffeeShopPhotoUrl] Updated successfully');
  } catch (err) {
    console.error('[updateCoffeeShopPhotoUrl] Failed:', err);
    throw err;
  }
};

/**
 * Upload and update coffee shop photo in one operation
 * @param {string} placeId - Coffee shop place_id
 * @param {File} file - Image file
 */
export const uploadAndUpdateCoffeeShopPhoto = async (placeId, file) => {
  const photoUrl = await uploadCoffeeShopPhoto(placeId, file);
  await updateCoffeeShopPhotoUrl(placeId, photoUrl);
  return photoUrl;
};

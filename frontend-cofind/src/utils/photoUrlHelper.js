/**
 * Helper untuk build valid photo URL dari Supabase
 * Menggunakan Supabase getPublicUrl() untuk generate URL dengan project-specific domain
 * 
 * Format URL yang dihasilkan:
 * https://<project-ref>.supabase.co/storage/v1/object/public/coffee_shops/{place_id}.webp
 */

import { supabase, getCoffeeShopPhotoUrl } from '../lib/supabase';

// Correct format template (fallback jika getPublicUrl tidak tersedia)
const SUPABASE_PHOTO_URL_TEMPLATE = 'https://cpnzglvpqyugtacodwtr.supabase.co/storage/v1/object/public/coffee_shops/{place_id}.webp';

export const getValidPhotoUrl = (photoUrl, placeId) => {
  if (!placeId) {
    return null;
  }

  // Prioritize generating correct URL from place_id using Supabase getPublicUrl
  // This is more reliable than depending on database photo_url
  if (supabase) {
    const dynamicUrl = getCoffeeShopPhotoUrl(placeId);
    if (dynamicUrl) {
      console.log(`[getValidPhotoUrl] Generated URL via getPublicUrl for ${placeId}`);
      return dynamicUrl;
    }
  }

  // Only use database photo_url if it's valid
  if (photoUrl) {
    // Jika photo_url berisi template {place_id}, replace dengan actual place_id
    if (photoUrl.includes('{place_id}')) {
      const url = photoUrl.replace('{place_id}', placeId);
      console.log(`[getValidPhotoUrl] Using template-replaced URL for ${placeId}`);
      return url;
    }

    // Jika sudah valid URL, return as-is
    if (photoUrl.includes('http') && photoUrl.includes('storage.supabase') && 
        photoUrl.includes('/storage/v1/object/public/coffee_shops/')) {
      console.log(`[getValidPhotoUrl] Using existing valid URL for ${placeId}`);
      return photoUrl;
    }
  }

  // Last resort fallback: Generate from template
  console.log(`[getValidPhotoUrl] Using template fallback for ${placeId}`);
  return SUPABASE_PHOTO_URL_TEMPLATE.replace('{place_id}', placeId);
};

/**
 * Validate jika URL valid untuk di-load
 */
export const isValidPhotoUrl = (photoUrl) => {
  if (!photoUrl || typeof photoUrl !== 'string') {
    return false;
  }

  // Check if URL contains unresolved placeholders
  if (photoUrl.includes('%7Bplace_id%7D') || photoUrl.includes('{place_id}')) {
    return false;
  }

  // Check if it's a valid Supabase URL dengan format yang benar
  const isValidSupabaseUrl = (photoUrl.includes('storage.supabase.co') || photoUrl.includes('cpnzglvpqyugtacodwtr.supabase.co') || 
                              photoUrl.includes('supabase.co/storage')) && 
                             photoUrl.includes('/storage/v1/object/public/coffee_shops/') &&
                             photoUrl.includes('http');
  
  if (!isValidSupabaseUrl) {
    console.warn(`[isValidPhotoUrl] Invalid URL format: ${photoUrl}`);
    return false;
  }

  return true;
};

/**
 * Generate correct photo URL dari place_id
 * Menggunakan Supabase getPublicUrl() untuk generate URL dinamis dengan project domain yang benar
 * Fallback ke template jika getPublicUrl tidak tersedia
 */
export const generateCorrectPhotoUrl = (placeId) => {
  if (!placeId) {
    console.error('[generateCorrectPhotoUrl] placeId is required');
    return null;
  }
  
  // Prioritas 1: Gunakan getCoffeeShopPhotoUrl dari Supabase client untuk URL yang paling akurat
  if (supabase) {
    const dynamicUrl = getCoffeeShopPhotoUrl(placeId);
    if (dynamicUrl) {
      console.log(`[generateCorrectPhotoUrl] Generated URL using getPublicUrl: ${placeId}`);
      return dynamicUrl;
    }
  }
  
  // Fallback: Gunakan template jika Supabase tidak tersedia
  console.log(`[generateCorrectPhotoUrl] Using template fallback for: ${placeId}`);
  return SUPABASE_PHOTO_URL_TEMPLATE.replace('{place_id}', placeId);
};

// Export template untuk external usage
export { SUPABASE_PHOTO_URL_TEMPLATE };

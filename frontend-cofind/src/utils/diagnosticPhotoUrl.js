/**
 * Diagnostic untuk verify dan fix photo URL format
 * Memastikan semua photo_url di database memiliki format yang benar:
 * https://cpnzglvpqyugtacodwtr.supabase.co/storage/v1/object/public/coffee_shops/{place_id}.webp
 */

import { supabase, isSupabaseConfigured, getCoffeeShopPhotoUrl } from '../lib/supabase';

// Format URL yang benar untuk Supabase Storage
export const CORRECT_PHOTO_URL_FORMAT = 'https://cpnzglvpqyugtacodwtr.supabase.co/storage/v1/object/public/coffee_shops/{place_id}.webp';

/**
 * Verify format photo URL
 * @param {string} url - URL yang akan diverifikasi
 * @returns {object} - { isValid: boolean, format: string, issue: string }
 */
export const verifyPhotoUrlFormat = (url) => {
  if (!url) {
    return { isValid: false, format: 'MISSING', issue: 'URL is empty or null' };
  }

  const urlLower = url.toLowerCase();

  // Check 1: Must start with https://cpnzglvpqyugtacodwtr.supabase.co
  if (!urlLower.startsWith('https://cpnzglvpqyugtacodwtr.supabase.co')) {
    return { 
      isValid: false, 
      format: 'WRONG_DOMAIN', 
      issue: `Domain harus 'cpnzglvpqyugtacodwtr.supabase.co', tapi dapat: ${new URL(url).hostname}` 
    };
  }

  // Check 2: Must contain path /storage/v1/object/public/coffee_shops/
  if (!urlLower.includes('/storage/v1/object/public/coffee_shops/')) {
    return { 
      isValid: false, 
      format: 'WRONG_PATH', 
      issue: `Path harus '/storage/v1/object/public/coffee_shops/', tapi dapat: ${new URL(url).pathname}` 
    };
  }

  // Check 3: Must end with .webp or contain {place_id}
  if (!url.endsWith('.webp') && !url.includes('{place_id}')) {
    return { 
      isValid: false, 
      format: 'WRONG_EXTENSION', 
      issue: `File harus berakhir dengan .webp, tapi dapat: ${url.substring(url.lastIndexOf('.'))}` 
    };
  }

  // Check 4: Must contain place_id in filename (as template or actual ID)
  const afterLastSlash = url.substring(url.lastIndexOf('/') + 1);
  if (!afterLastSlash.includes('place_id') && !afterLastSlash.startsWith('ChIJ')) {
    return { 
      isValid: false, 
      format: 'MISSING_PLACE_ID', 
      issue: `Filename harus berisi place_id atau dimulai dengan 'ChIJ', tapi dapat: ${afterLastSlash}` 
    };
  }

  return { isValid: true, format: 'CORRECT', issue: null };
};

/**
 * Diagnose all photo URLs di database
 * @returns {object} - Statistics dan issues yang ditemukan
 */
export const diagnosePhotoUrls = async () => {
  if (!isSupabaseConfigured || !supabase) {
    throw new Error('Supabase not configured');
  }

  try {
    console.log('🔍 [DIAGNOSTIC] Starting photo URL diagnosis...');

    // Fetch all places
    const { data: places, error: fetchError } = await supabase
      .from('places')
      .select('place_id, name, photo_url')
      .order('name');

    if (fetchError) {
      console.error('[DIAGNOSTIC] Fetch error:', fetchError);
      throw fetchError;
    }

    if (!places || places.length === 0) {
      console.warn('[DIAGNOSTIC] No places found');
      return { total: 0, issues: [] };
    }

    const stats = {
      total: places.length,
      missing: 0,
      invalidFormat: [],
      correctFormat: 0,
    };

    const details = [];

    for (const place of places) {
      const { place_id, name, photo_url } = place;

      if (!photo_url) {
        stats.missing++;
        details.push({
          place_id,
          name,
          status: 'MISSING',
          currentUrl: null,
          issue: 'photo_url column is NULL',
        });
        continue;
      }

      const verification = verifyPhotoUrlFormat(photo_url);

      if (!verification.isValid) {
        stats.invalidFormat.push({
          place_id,
          name,
          status: verification.format,
          currentUrl: photo_url,
          issue: verification.issue,
        });
        details.push({
          place_id,
          name,
          status: verification.format,
          currentUrl: photo_url,
          issue: verification.issue,
        });
      } else {
        stats.correctFormat++;
        details.push({
          place_id,
          name,
          status: 'VALID',
          currentUrl: photo_url,
          issue: null,
        });
      }
    }

    // Log hasil
    console.log('\n📊 [DIAGNOSTIC] Results:');
    console.log(`   ✅ Valid format: ${stats.correctFormat}/${stats.total}`);
    console.log(`   ❌ Invalid format: ${stats.invalidFormat.length}/${stats.total}`);
    console.log(`   ⚠️  Missing URL: ${stats.missing}/${stats.total}`);

    if (stats.invalidFormat.length > 0) {
      console.log('\n❌ [DIAGNOSTIC] Invalid URLs found:');
      stats.invalidFormat.forEach((item) => {
        console.log(`   • ${item.name} (${item.place_id})`);
        console.log(`     Status: ${item.status}`);
        console.log(`     Current: ${item.currentUrl}`);
        console.log(`     Issue: ${item.issue}`);
      });
    }

    if (stats.missing > 0) {
      console.log(`\n⚠️  [DIAGNOSTIC] ${stats.missing} places without photo_url`);
    }

    return {
      stats,
      details,
      summary: {
        healthPercentage: Math.round((stats.correctFormat / stats.total) * 100),
        needsFixing: stats.missing + stats.invalidFormat.length,
      },
    };
  } catch (err) {
    console.error('[DIAGNOSTIC] Error:', err);
    throw err;
  }
};

/**
 * Generate correct photo URL untuk place_id
 * Menggunakan Supabase getPublicUrl() untuk generate URL dengan project-specific domain
 * @param {string} placeId - Place ID
 * @returns {string} - Correct photo URL
 */
export const generateCorrectPhotoUrl = (placeId) => {
  if (!placeId) {
    throw new Error('placeId is required');
  }
  
  // Gunakan getCoffeeShopPhotoUrl dari Supabase untuk URL yang akurat
  if (isSupabaseConfigured && getCoffeeShopPhotoUrl) {
    const dynamicUrl = getCoffeeShopPhotoUrl(placeId);
    if (dynamicUrl) {
      console.log(`[generateCorrectPhotoUrl] Generated URL using getPublicUrl for: ${placeId}`);
      return dynamicUrl;
    }
  }
  
  // Fallback ke template jika Supabase tidak tersedia
  console.log(`[generateCorrectPhotoUrl] Using template fallback for: ${placeId}`);
  return CORRECT_PHOTO_URL_FORMAT.replace('{place_id}', placeId);
};

// Export untuk console usage
window.diagnosticPhotoUrl = {
  diagnosePhotoUrls,
  verifyPhotoUrlFormat,
  generateCorrectPhotoUrl,
  CORRECT_PHOTO_URL_FORMAT,
};

console.log('✅ Diagnostic photo URL functions loaded. Use window.diagnosticPhotoUrl.diagnosePhotoUrls() in console');

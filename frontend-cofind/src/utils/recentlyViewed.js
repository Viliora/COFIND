/**
 * Utility untuk mengelola recently viewed coffee shops
 * Menyimpan di localStorage dengan format: { place_id, name, viewedAt }
 */

const STORAGE_KEY = 'recently_viewed_shops';
const MAX_RECENT_ITEMS = 10; // Maksimal 10 coffee shop yang disimpan

/**
 * Tambahkan coffee shop ke recently viewed
 * @param {Object} shop - Coffee shop object dengan place_id dan name
 */
export function addToRecentlyViewed(shop) {
  if (!shop || !shop.place_id || !shop.name) {
    console.warn('[RecentlyViewed] Invalid shop data:', shop);
    return;
  }

  try {
    // Ambil data yang sudah ada
    const existing = getRecentlyViewed();
    
    // Hapus jika sudah ada (untuk update timestamp)
    const filtered = existing.filter(item => item.place_id !== shop.place_id);
    
    // Tambahkan yang baru di depan dengan timestamp
    const updated = [
      {
        place_id: shop.place_id,
        name: shop.name,
        address: shop.address || '',
        rating: shop.rating || 0,
        user_ratings_total: shop.user_ratings_total || 0,
        location: shop.location || null,
        viewedAt: new Date().toISOString(),
      },
      ...filtered
    ].slice(0, MAX_RECENT_ITEMS); // Batasi maksimal 10 items
    
    // Simpan ke localStorage
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    console.log('[RecentlyViewed] Added:', shop.name, 'Total:', updated.length);
  } catch (error) {
    console.error('[RecentlyViewed] Error saving to localStorage:', error);
  }
}

/**
 * Ambil daftar recently viewed coffee shops
 * @returns {Array} Array of recently viewed shops
 */
export function getRecentlyViewed() {
  try {
    const data = localStorage.getItem(STORAGE_KEY);
    if (!data) return [];
    
    const parsed = JSON.parse(data);
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    console.error('[RecentlyViewed] Error reading from localStorage:', error);
    return [];
  }
}

/**
 * Hapus semua recently viewed
 */
export function clearRecentlyViewed() {
  try {
    localStorage.removeItem(STORAGE_KEY);
    console.log('[RecentlyViewed] Cleared all');
  } catch (error) {
    console.error('[RecentlyViewed] Error clearing:', error);
  }
}

/**
 * Hapus satu item dari recently viewed
 * @param {string} placeId - Place ID yang akan dihapus
 */
export function removeFromRecentlyViewed(placeId) {
  try {
    const existing = getRecentlyViewed();
    const filtered = existing.filter(item => item.place_id !== placeId);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered));
    console.log('[RecentlyViewed] Removed:', placeId);
  } catch (error) {
    console.error('[RecentlyViewed] Error removing item:', error);
  }
}

/**
 * Ambil recently viewed dengan data lengkap dari coffee shops list
 * @param {Array} allShops - Array semua coffee shops untuk lookup data lengkap
 * @returns {Array} Array of recently viewed shops dengan data lengkap
 */
export function getRecentlyViewedWithDetails(allShops) {
  const recent = getRecentlyViewed();
  if (!allShops || allShops.length === 0) return [];
  
  // Map recently viewed dengan data lengkap dari allShops
  return recent
    .map(recentItem => {
      const fullData = allShops.find(shop => shop.place_id === recentItem.place_id);
      if (fullData) {
        return {
          ...fullData,
          viewedAt: recentItem.viewedAt, // Keep timestamp
        };
      }
      return null;
    })
    .filter(Boolean); // Remove null items (shop tidak ditemukan di allShops)
}


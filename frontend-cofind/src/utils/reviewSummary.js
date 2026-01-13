// Utility untuk fetch dan cache review summary
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';
const CACHE_KEY_PREFIX = 'review_summary_';
const CACHE_VERSION = 'v3'; // Increment untuk clear cache lama saat ada perubahan format
const CACHE_DURATION = 7 * 24 * 60 * 60 * 1000; // 7 hari dalam milliseconds

/**
 * Mendapatkan review summary untuk coffee shop berdasarkan place_id
 * Menggunakan cache untuk menghindari request berulang
 * 
 * @param {string} placeId - Place ID coffee shop
 * @param {string} shopName - Nama coffee shop (optional, untuk fallback)
 * @returns {Promise<string|null>} - Review summary atau null jika error
 */
export async function getReviewSummary(placeId, shopName = 'Coffee Shop') {
  if (!placeId) {
    return null;
  }
  void shopName;

  // Cek cache dulu
  const cacheKey = `${CACHE_KEY_PREFIX}${placeId}`;
  const cached = localStorage.getItem(cacheKey);
  
  if (cached) {
    try {
      const cachedData = JSON.parse(cached);
      const now = Date.now();
      
      // Cek versi cache - jika versi berbeda, hapus cache lama
      if (cachedData.version !== CACHE_VERSION) {
        console.log(`[ReviewSummary] Cache version mismatch, clearing old cache for ${placeId}`);
        localStorage.removeItem(cacheKey);
      }
      // Jika cache masih valid (kurang dari 7 hari) dan versi sama
      else if (cachedData.timestamp && (now - cachedData.timestamp) < CACHE_DURATION) {
        // Cache masih valid, akan dicek reviews_hash saat fetch dari API
        console.log(`[ReviewSummary] Cache found for ${placeId}, will validate with server`);
      } else {
        // Cache expired, hapus
        localStorage.removeItem(cacheKey);
      }
    } catch (e) {
      console.warn('[ReviewSummary] Error reading cache:', e);
      localStorage.removeItem(cacheKey);
    }
  }

  // Cek apakah LLM service disabled (untuk menghindari request yang tidak perlu)
  if (localStorage.getItem('review_summary_service_disabled') === 'true') {
    return null;
  }

  // Fetch dari API
//   try {
//     const response = await fetch(`${API_BASE}/api/llm/summarize-review`, {
//       method: 'POST',
//       headers: {
//         'Content-Type': 'application/json',
//       },
//       body: JSON.stringify({
//         place_id: placeId,
//         shop_name: shopName,
//       }),
//     });

//     const data = await response.json();

//     if (!response.ok) {
//       // Handle error 402 (Payment Required) atau 500 (LLM service unavailable)
//       const isPaymentError = data.message && (
//         data.message.includes('402') || 
//         data.message.includes('Payment Required') ||
//         data.message.includes('exceeded') ||
//         data.message.includes('credits')
//       );
      
//       if (isPaymentError) {
//         // Disable service untuk menghindari request berulang
//         localStorage.setItem('review_summary_service_disabled', 'true');
//         // Log sekali saja untuk payment error, tidak spam console
//         if (!localStorage.getItem('review_summary_payment_error_logged')) {
//           console.warn('[ReviewSummary] LLM service unavailable (quota exceeded). Review summaries will be disabled. Clear localStorage to re-enable.');
//           localStorage.setItem('review_summary_payment_error_logged', 'true');
//         }
//       } else {
//         // Log error lainnya hanya sekali per session
//         console.error('[ReviewSummary] API error:', data.message);
//       }
//       return null;
//     }

//     if (data.status === 'success' && data.summary) {
//       // Cek apakah reviews_hash berubah (reviews.json berubah)
//       const reviewsHash = data.reviews_hash;
//       const cached = localStorage.getItem(cacheKey);
//       let shouldUseCache = false;
      
//       if (cached && reviewsHash) {
//         try {
//           const cachedData = JSON.parse(cached);
//           // Jika reviews_hash sama dan cache masih valid, gunakan cache
//           if (cachedData.reviews_hash === reviewsHash && 
//               cachedData.version === CACHE_VERSION &&
//               cachedData.timestamp && 
//               (Date.now() - cachedData.timestamp) < CACHE_DURATION) {
//             console.log(`[ReviewSummary] Using cached summary (reviews unchanged) for ${placeId}`);
//             shouldUseCache = true;
//             return cachedData.summary;
//           }
//         } catch (e) {
//           console.warn('[ReviewSummary] Error checking cache hash:', e);
//         }
//       }
      
//       // Post-processing: Hapus frasa pembuka yang tidak diinginkan di frontend juga (backup)
//       let cleanedSummary = data.summary.trim();
      
//       // Hapus nama coffee shop di awal jika ada
//       const shopNameLower = shopName.toLowerCase();
//       if (cleanedSummary.toLowerCase().startsWith(shopNameLower)) {
//         cleanedSummary = cleanedSummary.substring(shopName.length).trim();
//         cleanedSummary = cleanedSummary.replace(/^[.,;:\s]+/, ''); // Hapus tanda baca di awal
//       }
      
//       // Hapus frasa pembuka yang tidak diinginkan
//       const unwantedPrefixes = [
//         'menawarkan suasana',
//         'menawarkan',
//         'memiliki suasana',
//         'memiliki',
//         'dengan suasana',
//         'coffee shop ini menawarkan',
//         'coffee shop ini memiliki',
//         'tempat ini menawarkan',
//         'tempat ini memiliki',
//         'berlokasi di',
//       ];
      
//       for (const prefix of unwantedPrefixes) {
//         if (cleanedSummary.toLowerCase().startsWith(prefix.toLowerCase())) {
//           cleanedSummary = cleanedSummary.substring(prefix.length).trim();
//           cleanedSummary = cleanedSummary.replace(/^[.,;:\s]+/, ''); // Hapus tanda baca di awal
//           break;
//         }
//       }
      
//       // Capitalize huruf pertama
//       if (cleanedSummary) {
//         cleanedSummary = cleanedSummary.charAt(0).toUpperCase() + cleanedSummary.slice(1);
//       }
      
//       // Simpan ke cache dengan versi dan reviews_hash
//       const cacheData = {
//         summary: cleanedSummary,
//         timestamp: Date.now(),
//         place_id: placeId,
//         version: CACHE_VERSION,
//         reviews_hash: reviewsHash, // Hash untuk detect perubahan reviews.json
//       };
//       localStorage.setItem(cacheKey, JSON.stringify(cacheData));
//       console.log(`[ReviewSummary] Summary cached for ${placeId} (hash: ${reviewsHash})`);
      
//       return cleanedSummary;
//     }

//     return null;
//   } catch (error) {
//     console.error('[ReviewSummary] Error fetching summary:', error);
//     return null;
//   }
// }

/**
 * Clear cache untuk review summary tertentu
 * @param {string} placeId - Place ID coffee shop
 */
// export function clearReviewSummaryCache(placeId) {
//   if (placeId) {
//     const cacheKey = `${CACHE_KEY_PREFIX}${placeId}`;
//     localStorage.removeItem(cacheKey);
//     console.log(`[ReviewSummary] Cache cleared for ${placeId}`);
//   }
// }

/**
 * Clear semua review summary cache
 */
// export function clearAllReviewSummaryCache() {
//   const keys = Object.keys(localStorage);
//   keys.forEach(key => {
//     if (key.startsWith(CACHE_KEY_PREFIX)) {
//       localStorage.removeItem(key);
//     }
//   });
//   // Clear service disabled flag juga
//   localStorage.removeItem('review_summary_service_disabled');
//   localStorage.removeItem('review_summary_payment_error_logged');
//   console.log('[ReviewSummary] All caches cleared and service re-enabled');
}

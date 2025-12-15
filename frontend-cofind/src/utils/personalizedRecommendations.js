/**
 * Utility untuk Personalized Recommendations berdasarkan history favorit user
 * TIDAK PERLU LLM - menggunakan rule-based content filtering
 */

import localReviewsData from '../data/reviews.json';
import { filterStopWords, normalizeWord } from './keywordMapping';

/**
 * Ekstrak konteks review (full text) untuk similarity matching
 * @param {Array} reviews - Array of reviews
 * @returns {string} Combined review text (lowercase, cleaned)
 */
function extractReviewContext(reviews) {
  if (!reviews || reviews.length === 0) return '';
  
  // Gabungkan semua review text
  const allTexts = reviews
    .map(r => (r.text || '').trim())
    .filter(text => text.length >= 20) // Minimal 20 karakter
    .map(text => text.toLowerCase());
  
  return allTexts.join(' ');
}

/**
 * Ekstrak keywords penting dari review context
 * @param {string} reviewContext - Combined review text
 * @returns {Set} Set of important keywords
 */
function extractImportantKeywords(reviewContext) {
  if (!reviewContext) return new Set();
  
  // Split menjadi words, filter stop words, normalisasi, ambil yang panjangnya >= 3
  const words = reviewContext
    .split(/\s+/)
    .map(word => word.replace(/[^\w]/g, '')) // Remove punctuation
    .filter(word => word.length >= 3);
  
  // Filter stop words dan normalisasi menggunakan utility
  const filteredWords = filterStopWords(words)
    .map(word => normalizeWord(word))
    .filter(word => word.length >= 3);
  
  return new Set(filteredWords);
}

/**
 * Hitung similarity berdasarkan konteks review (text similarity)
 * @param {string} context1 - Review context dari shop 1
 * @param {string} context2 - Review context dari shop 2
 * @returns {number} Similarity score (0-1)
 */
function calculateContextSimilarity(context1, context2) {
  if (!context1 || !context2) return 0;
  
  // Ekstrak keywords dari kedua context
  const keywords1 = extractImportantKeywords(context1);
  const keywords2 = extractImportantKeywords(context2);
  
  if (keywords1.size === 0 || keywords2.size === 0) return 0;
  
  // Hitung intersection (keywords yang sama)
  const intersection = new Set([...keywords1].filter(k => keywords2.has(k)));
  const union = new Set([...keywords1, ...keywords2]);
  
  // Jaccard similarity: intersection / union
  const jaccardSimilarity = intersection.size / union.size;
  
  // Hitung phrase similarity (common phrases)
  const phrases1 = extractPhrases(context1);
  const phrases2 = extractPhrases(context2);
  const commonPhrases = phrases1.filter(p => phrases2.includes(p));
  const phraseSimilarity = phrases1.length > 0 
    ? commonPhrases.length / Math.max(phrases1.length, phrases2.length)
    : 0;
  
  // Combine: 70% jaccard, 30% phrase
  return (jaccardSimilarity * 0.7) + (phraseSimilarity * 0.3);
}

/**
 * Ekstrak phrases (2-3 words) dari text
 * @param {string} text - Review text
 * @returns {Array} Array of phrases
 */
function extractPhrases(text) {
  if (!text) return [];
  
  // Split menjadi words
  const words = text
    .split(/\s+/)
    .map(w => w.replace(/[^\w]/g, '').toLowerCase())
    .filter(w => w.length >= 3);
  
  // Filter stop words dan normalisasi menggunakan utility
  const filteredWords = filterStopWords(words)
    .map(word => normalizeWord(word))
    .filter(word => word.length >= 3);
  
  if (filteredWords.length < 2) return [];
  
  const phrases = [];
  
  // 2-word phrases
  for (let i = 0; i < filteredWords.length - 1; i++) {
    phrases.push(`${filteredWords[i]} ${filteredWords[i + 1]}`);
  }
  
  // 3-word phrases (hanya jika ada cukup words)
  if (filteredWords.length >= 3) {
    for (let i = 0; i < filteredWords.length - 2; i++) {
      phrases.push(`${filteredWords[i]} ${filteredWords[i + 1]} ${filteredWords[i + 2]}`);
    }
  }
  
  return phrases;
}


/**
 * Hitung location similarity (jarak antara dua lokasi)
 * @param {Object} loc1 - Location 1 {lat, lng}
 * @param {Object} loc2 - Location 2 {lat, lng}
 * @returns {number} Distance in km (0 jika sama lokasi)
 */
function calculateDistance(loc1, loc2) {
  if (!loc1 || !loc2 || !loc1.lat || !loc1.lng || !loc2.lat || !loc2.lng) {
    return Infinity; // Tidak bisa hitung jika tidak ada lokasi
  }
  
  const R = 6371; // Radius bumi dalam km
  const dLat = (loc2.lat - loc1.lat) * Math.PI / 180;
  const dLon = (loc2.lng - loc1.lng) * Math.PI / 180;
  const a = 
    Math.sin(dLat/2) * Math.sin(dLat/2) +
    Math.cos(loc1.lat * Math.PI / 180) * Math.cos(loc2.lat * Math.PI / 180) *
    Math.sin(dLon/2) * Math.sin(dLon/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return R * c;
}

/**
 * Generate personalized recommendations berdasarkan favorit user
 * @param {Array} favoriteShops - Array of favorite coffee shops (dari localStorage)
 * @param {Array} allShops - Array semua coffee shops
 * @param {Object} options - Options untuk recommendations
 * @returns {Array} Array of recommended coffee shops dengan score
 */
export function getPersonalizedRecommendations(favoriteShops, allShops, options = {}) {
  const {
    maxResults = 10,
    minRating = 4.0,
    excludeFavorites = true,
    weightFeatures = 0.7, // Lebih fokus pada context similarity (70%)
    weightRating = 0.2,
    weightLocation = 0.1,
  } = options;
  
  if (!favoriteShops || favoriteShops.length === 0) {
    return [];
  }
  
  if (!allShops || allShops.length === 0) {
    return [];
  }
  
  const reviewsByPlaceId = localReviewsData?.reviews_by_place_id || {};
  
  // Ekstrak konteks review dari semua favorit (gabungkan semua review text)
  const favoriteReviewContexts = [];
  const favoriteLocations = [];
  
  favoriteShops.forEach(fav => {
    const reviews = reviewsByPlaceId[fav.place_id] || [];
    const context = extractReviewContext(reviews);
    
    if (context) {
      favoriteReviewContexts.push(context);
    }
    
    // Collect locations
    if (fav.location) {
      favoriteLocations.push(fav.location);
    }
  });
  
  // Gabungkan semua review context dari favorit menjadi satu
  const combinedFavoriteContext = favoriteReviewContexts.join(' ');
  
  // Calculate average location (centroid)
  const avgLocation = favoriteLocations.length > 0 ? {
    lat: favoriteLocations.reduce((sum, loc) => sum + loc.lat, 0) / favoriteLocations.length,
    lng: favoriteLocations.reduce((sum, loc) => sum + loc.lng, 0) / favoriteLocations.length,
  } : null;
  
  // Filter dan score semua coffee shops
  const favoritePlaceIds = new Set(favoriteShops.map(f => f.place_id));
  
  const scoredShops = allShops
    .filter(shop => {
      // Exclude favorites jika excludeFavorites = true
      if (excludeFavorites && favoritePlaceIds.has(shop.place_id)) {
        return false;
      }
      
      // Filter minimal rating
      const rating = parseFloat(shop.rating) || 0;
      if (rating < minRating) {
        return false;
      }
      
      return true;
    })
    .map(shop => {
      const reviews = reviewsByPlaceId[shop.place_id] || [];
      const shopContext = extractReviewContext(reviews);
      
      // Calculate similarity score berdasarkan konteks review
      const contextSimilarity = calculateContextSimilarity(combinedFavoriteContext, shopContext);
      
      // Calculate rating score (normalized)
      const rating = parseFloat(shop.rating) || 0;
      const ratingScore = rating / 5.0; // Normalize to 0-1
      
      // Calculate location score (closer = better)
      let locationScore = 0.5; // Default jika tidak ada lokasi
      if (avgLocation && shop.location) {
        const distance = calculateDistance(avgLocation, shop.location);
        // Normalize: 0-5km = 1.0, 5-10km = 0.8, 10-15km = 0.6, >15km = 0.4
        if (distance <= 5) locationScore = 1.0;
        else if (distance <= 10) locationScore = 0.8;
        else if (distance <= 15) locationScore = 0.6;
        else locationScore = 0.4;
      }
      
      // Calculate total score - lebih fokus pada context similarity
      const totalScore = 
        (contextSimilarity * weightFeatures) +
        (ratingScore * weightRating) +
        (locationScore * weightLocation);
      
      return {
        ...shop,
        recommendationScore: totalScore,
        contextSimilarity,
        ratingScore,
        locationScore,
      };
    })
    .sort((a, b) => b.recommendationScore - a.recommendationScore)
    .slice(0, maxResults);
  
  return scoredShops;
}

/**
 * Get recommendations dengan penjelasan mengapa direkomendasikan
 * @param {Array} favoriteShops - Array of favorite coffee shops
 * @param {Array} allShops - Array semua coffee shops
 * @param {Object} options - Options
 * @returns {Array} Array dengan reason untuk setiap recommendation
 */
export function getPersonalizedRecommendationsWithReasons(favoriteShops, allShops, options = {}) {
  const recommendations = getPersonalizedRecommendations(favoriteShops, allShops, options);
  
  return recommendations.map(shop => {
    const reasons = [];
    
    if (shop.contextSimilarity > 0.3) {
      reasons.push('Review memiliki konteks yang mirip dengan favorit Anda');
    }
    
    if (shop.ratingScore > 0.8) {
      reasons.push('Rating tinggi');
    }
    
    if (shop.locationScore > 0.7) {
      reasons.push('Lokasi dekat dengan favorit Anda');
    }
    
    return {
      ...shop,
      reasons: reasons.length > 0 ? reasons : ['Rekomendasi berdasarkan preferensi Anda'],
    };
  });
}


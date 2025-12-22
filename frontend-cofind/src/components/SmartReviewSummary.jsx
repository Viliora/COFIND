// src/components/SmartReviewSummary.jsx
import React, { useState, useEffect } from 'react';
import { supabase, isSupabaseConfigured } from '../lib/supabase';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';

// Cache status LLM di memory (shared across components)
let llmStatusCache = null;
let llmStatusPromise = null; // Untuk mencegah race condition

/**
 * SmartReviewSummary Component
 * Menggunakan LLM untuk analisis sentimen dan merangkum reviews
 * dengan pemahaman konteks yang lebih baik (mengenali negasi, dll)
 * + Fallback ke client-side extraction jika LLM gagal
 */
const SmartReviewSummary = ({ shopName, placeId, reviews: propReviews }) => {
  // 🛑 DISABLED: LLM Analysis temporarily disabled to save tokens
  // TODO: Re-enable when needed by removing this early return
  return null;
  
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isExpanded, setIsExpanded] = useState(true);
  const [cacheInfo, setCacheInfo] = useState(null); // Info tentang cache
  const [reviews, setReviews] = useState(propReviews || []); // Reviews dari props atau fetch dari Supabase

  // Fetch reviews dari Supabase jika tidak ada di props
  useEffect(() => {
    if (!placeId || !isSupabaseConfigured || !supabase) {
      return;
    }

    // Jika reviews sudah ada di props, gunakan itu
    if (propReviews && propReviews.length > 0) {
      setReviews(propReviews);
      return;
    }

    // Fetch reviews dari Supabase
    const fetchReviews = async () => {
      try {
        const { data, error } = await supabase
          .from('reviews')
          .select('text, rating')
          .eq('place_id', placeId)
          .order('created_at', { ascending: false })
          .limit(10);

        if (error) {
          console.warn('[SmartReviewSummary] Error fetching reviews:', error);
          return;
        }

        if (data && data.length > 0) {
          setReviews(data);
        }
      } catch (err) {
        console.warn('[SmartReviewSummary] Exception fetching reviews:', err);
      }
    };

    fetchReviews();
  }, [placeId, propReviews, isSupabaseConfigured]);

  // Fallback: Client-side keyword extraction (digunakan jika LLM gagal)
  const extractInsightsLocally = (reviewsList) => {
    if (!reviewsList || reviewsList.length === 0) return null;

    const allReviewText = reviewsList.map(r => (r.text || '').toLowerCase()).join(' ');

    const PATTERNS = {
      positif: {
        'WiFi kencang': ['wifi kencang', 'wifi cepat', 'wifi stabil', 'internet cepat'],
        'Suasana nyaman': ['nyaman', 'cozy', 'comfortable', 'homey'],
        'Kopi enak': ['kopi enak', 'kopinya enak', 'espresso enak'],
        'Pelayanan ramah': ['pelayanan ramah', 'staff ramah', 'ramah'],
        'Tempat aesthetic': ['aesthetic', 'instagramable', 'fotogenic'],
        'Suasana tenang': ['tenang', 'quiet', 'sunyi'],
        'Tempat luas': ['luas', 'spacious', 'besar'],
      },
      negatif: {
        'Parkir terbatas': ['parkir sempit', 'parkir susah', 'susah parkir'],
        'Ramai di jam tertentu': ['ramai', 'penuh', 'crowded'],
        'Harga mahal': ['mahal', 'pricey', 'harga tinggi'],
      },
      fasilitas: {
        'WiFi': ['wifi', 'wi-fi'],
        'Colokan': ['colokan', 'stopkontak', 'charger'],
        'AC': ['ac', 'dingin'],
        'Parkir': ['parkir'],
        'Musholla': ['musholla', 'mushola', 'sholat'],
        'Toilet': ['toilet', 'wc'],
      },
      cocokUntuk: {
        'Kerja/WFC': ['wfc', 'kerja', 'working', 'remote'],
        'Belajar': ['belajar', 'study', 'tugas'],
        'Meeting': ['meeting', 'rapat'],
        'Nongkrong': ['nongkrong', 'hangout', 'kumpul'],
      }
    };

    const result = { positif: [], negatif: [], fasilitas: [], cocokUntuk: [], ringkasan: '' };

    for (const [label, keywords] of Object.entries(PATTERNS.positif)) {
      if (keywords.some(kw => allReviewText.includes(kw))) result.positif.push(label);
    }
    for (const [label, keywords] of Object.entries(PATTERNS.negatif)) {
      if (keywords.some(kw => allReviewText.includes(kw))) result.negatif.push(label);
    }
    for (const [label, keywords] of Object.entries(PATTERNS.fasilitas)) {
      if (keywords.some(kw => allReviewText.includes(kw))) result.fasilitas.push(label);
    }
    for (const [label, keywords] of Object.entries(PATTERNS.cocokUntuk)) {
      if (keywords.some(kw => allReviewText.includes(kw))) result.cocokUntuk.push(label);
    }

    // Generate simple summary
    if (result.positif.length > 0) {
      result.ringkasan = `Coffee shop dengan ${result.positif.slice(0, 2).join(' dan ').toLowerCase()}${result.cocokUntuk.length > 0 ? `, cocok untuk ${result.cocokUntuk[0].toLowerCase()}` : ''}.`;
    }

    return result;
  };

  useEffect(() => {
    let isMounted = true; // Prevent state updates after unmount

    const checkLLMStatus = async () => {
      // Jika sudah diketahui, return langsung
      if (llmStatusCache !== null) return llmStatusCache;
      
      // Jika sedang dalam proses cek, tunggu promise yang sama
      if (llmStatusPromise) return llmStatusPromise;
      
      // Buat promise baru untuk cek status
      llmStatusPromise = (async () => {
        try {
          const res = await fetch(`${API_BASE}/api/llm/status`);
          const data = await res.json();
          llmStatusCache = data.available === true;
        } catch {
          llmStatusCache = false;
        }
        return llmStatusCache;
      })();
      
      return llmStatusPromise;
    };

    const fetchSentimentAnalysis = async () => {
      // Minimal 3 reviews untuk generate summary yang bermakna
      if (!reviews || reviews.length < 3) {
        return;
      }

      setLoading(true);
      setError(null);

      // Tunggu status LLM diketahui (tanpa race condition)
      const isLLMAvailable = await checkLLMStatus();

      // Jika LLM tidak tersedia, langsung gunakan fallback (tanpa request = tanpa error di console)
      if (!isLLMAvailable) {
        const fallbackResult = extractInsightsLocally(reviews);
        if (isMounted && fallbackResult && (fallbackResult.positif.length > 0 || fallbackResult.fasilitas.length > 0)) {
          setSummary(fallbackResult);
        }
        if (isMounted) setLoading(false);
        return;
      }

      // LLM tersedia, coba request dengan timeout untuk prevent hanging
      try {
        // Add timeout untuk prevent hanging (10 seconds)
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000);
        
        const response = await fetch(`${API_BASE}/api/llm/analyze-sentiment`, {
          signal: controller.signal,
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            place_id: placeId,
            shop_name: shopName,
            reviews: reviews.slice(0, 10).map(r => ({
              text: r.text,
              rating: r.rating
            }))
          }),
        });
        
        clearTimeout(timeoutId); // Clear timeout jika request berhasil

        // Jika 402 (kuota habis/payment required), 500, atau 503 (LLM tidak tersedia), gunakan fallback
        // 402 adalah expected error (quota habis), jangan log sebagai error
        if (response.status === 402 || response.status === 500 || response.status === 503) {
          if (response.status === 402) {
            // 402 adalah expected - quota habis atau payment required, gunakan fallback tanpa error
            console.log('[SmartReviewSummary] LLM quota exceeded or payment required (402) - using fallback');
          }
          llmStatusCache = false; // Mark LLM as unavailable
          const fallbackResult = extractInsightsLocally(reviews);
          if (isMounted && fallbackResult && (fallbackResult.positif.length > 0 || fallbackResult.fasilitas.length > 0)) {
            setSummary(fallbackResult);
          }
          if (isMounted) setLoading(false);
          return;
        }

        const data = await response.json();

        if (response.ok && (data.status === 'success' || data.status === 'partial')) {
          const result = data.data;
          
          // Validasi hasil
          if (isMounted && result && (
            (result.positif && result.positif.length > 0) ||
            (result.fasilitas && result.fasilitas.length > 0) ||
            result.ringkasan
          )) {
            setSummary({
              positif: result.positif || [],
              negatif: result.negatif || [],
              fasilitas: result.fasilitas || [],
              cocokUntuk: result.cocok_untuk || [],
              ringkasan: result.ringkasan || '',
            });
            
            setCacheInfo({
              fromCache: data.from_cache || false,
              cacheAgeDays: data.cache_age_days || 0
            });
            
            setLoading(false);
            return; // Success
          }
        }
        
        // Response tidak valid, gunakan fallback
      } catch (error) {
        // Handle timeout atau network error dengan graceful fallback
        if (error.name === 'AbortError') {
          console.log('[SmartReviewSummary] Request timeout - using fallback');
        } else {
          console.warn('[SmartReviewSummary] Error:', error.message || error);
        }
        // Network error, gunakan fallback
      }
      
      // Fallback ke client-side extraction
      const fallbackResult = extractInsightsLocally(reviews);
      if (isMounted && fallbackResult && (fallbackResult.positif.length > 0 || fallbackResult.fasilitas.length > 0)) {
        setSummary(fallbackResult);
      }
      if (isMounted) setLoading(false);
    };

    fetchSentimentAnalysis();

    return () => {
      isMounted = false; // Cleanup
    };
  }, [shopName, placeId, reviews]);
  
  // Update reviews jika propReviews berubah
  useEffect(() => {
    if (propReviews && propReviews.length > 0) {
      setReviews(propReviews);
    }
  }, [propReviews]);

  // Jika reviews kurang dari 3, tampilkan pesan
  if (!reviews || reviews.length < 3) {
    return null;
  }

  // Loading state
  if (loading) {
    return (
      <div className="bg-gradient-to-br from-indigo-50 to-purple-50 dark:from-indigo-900/20 dark:to-purple-900/20 p-4 sm:p-6 rounded-xl border border-indigo-100 dark:border-indigo-800">
        <div className="flex items-center gap-3">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-indigo-600"></div>
          <span className="text-sm text-indigo-700 dark:text-indigo-300">
            AI sedang menganalisis {reviews.length} review...
          </span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="bg-red-50 dark:bg-red-900/20 p-4 rounded-xl border border-red-100 dark:border-red-800">
        <p className="text-sm text-red-700 dark:text-red-300">
          ⚠️ Tidak dapat menganalisis review: {error}
        </p>
      </div>
    );
  }

  // No summary available
  if (!summary) {
    return null;
  }

  return (
    <div className="bg-gradient-to-br from-indigo-50 via-purple-50 to-pink-50 dark:from-indigo-900/20 dark:via-purple-900/20 dark:to-pink-900/20 p-4 sm:p-6 rounded-xl border border-indigo-100 dark:border-indigo-800 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-indigo-100 dark:bg-indigo-800 rounded-lg">
            <svg className="w-5 h-5 text-indigo-600 dark:text-indigo-300" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path>
            </svg>
          </div>
          <div>
            <h3 className="text-lg font-bold text-gray-900 dark:text-white">
              Ringkasan AI
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Berdasarkan {reviews.length} review pengunjung
            </p>
          </div>
        </div>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="p-2 hover:bg-white/50 dark:hover:bg-zinc-700/50 rounded-lg transition-colors"
        >
          <svg 
            className={`w-5 h-5 text-gray-500 transition-transform ${isExpanded ? 'rotate-180' : ''}`} 
            fill="none" 
            strokeLinecap="round" 
            strokeLinejoin="round" 
            strokeWidth="2" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path d="M19 9l-7 7-7-7"></path>
          </svg>
        </button>
      </div>

      {isExpanded && (
        <div className="space-y-4">
          {/* Ringkasan */}
          {summary.ringkasan && (
            <div className="p-3 bg-white/60 dark:bg-zinc-800/60 rounded-lg">
              <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                "{summary.ringkasan}"
              </p>
            </div>
          )}

          {/* Grid untuk Positif, Negatif, Fasilitas, Cocok Untuk */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Positif */}
            {summary.positif.length > 0 && (
              <div className="p-3 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-100 dark:border-green-800">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-green-500">✅</span>
                  <span className="text-sm font-semibold text-green-700 dark:text-green-300">
                    Yang Disukai
                  </span>
                </div>
                <ul className="space-y-1">
                  {summary.positif.map((item, idx) => (
                    <li key={idx} className="text-sm text-green-800 dark:text-green-200 flex items-start gap-2">
                      <span className="text-green-400 mt-1">•</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Negatif */}
            {summary.negatif.length > 0 && (
              <div className="p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-100 dark:border-amber-800">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-amber-500">⚠️</span>
                  <span className="text-sm font-semibold text-amber-700 dark:text-amber-300">
                    Perlu Diperhatikan
                  </span>
                </div>
                <ul className="space-y-1">
                  {summary.negatif.map((item, idx) => (
                    <li key={idx} className="text-sm text-amber-800 dark:text-amber-200 flex items-start gap-2">
                      <span className="text-amber-400 mt-1">•</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Fasilitas */}
            {summary.fasilitas.length > 0 && (
              <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-100 dark:border-blue-800">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-blue-500">🏪</span>
                  <span className="text-sm font-semibold text-blue-700 dark:text-blue-300">
                    Fasilitas
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {summary.fasilitas.map((item, idx) => (
                    <span 
                      key={idx} 
                      className="px-2 py-1 text-xs font-medium bg-blue-100 dark:bg-blue-800 text-blue-700 dark:text-blue-200 rounded-full"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Cocok Untuk */}
            {summary.cocokUntuk.length > 0 && (
              <div className="p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg border border-purple-100 dark:border-purple-800">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-purple-500">🎯</span>
                  <span className="text-sm font-semibold text-purple-700 dark:text-purple-300">
                    Cocok Untuk
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {summary.cocokUntuk.map((item, idx) => (
                    <span 
                      key={idx} 
                      className="px-2 py-1 text-xs font-medium bg-purple-100 dark:bg-purple-800 text-purple-700 dark:text-purple-200 rounded-full"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="pt-2 border-t border-indigo-100 dark:border-indigo-800">
            <div className="flex items-center justify-between">
              <p className="text-xs text-gray-400 dark:text-gray-500 flex items-center gap-1">
                <svg className="w-3 h-3" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
                  <path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                Ringkasan AI berdasarkan {reviews.length} review
              </p>
              {cacheInfo && cacheInfo.fromCache && (
                <span className="text-xs text-gray-400 dark:text-gray-500 flex items-center gap-1">
                  <svg className="w-3 h-3" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
                    <path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                  </svg>
                  {cacheInfo.cacheAgeDays < 1 ? 'Hari ini' : `${Math.floor(cacheInfo.cacheAgeDays)} hari lalu`}
                </span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SmartReviewSummary;


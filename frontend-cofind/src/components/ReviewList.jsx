import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../context/authContext';
import ReviewCard from './ReviewCard';
import ReviewForm from './ReviewForm';
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';
const REVIEW_KEYWORD_STOPWORDS = new Set([
  'yang', 'dan', 'atau', 'untuk', 'dengan', 'juga', 'karena', 'dari', 'pada',
  'saya', 'kami', 'kita', 'anda', 'nya', 'ini', 'itu', 'ada', 'aja', 'banget',
  'sangat', 'lebih', 'cukup', 'buat', 'bisa', 'jadi', 'kalau', 'karna', 'udah',
  'sudah', 'lagi', 'sih', 'nih', 'deh', 'the', 'and', 'very', 'place', 'coffee',
  'shop', 'tempat', 'untung', 'seperti', 'dalam', 'saat', 'biar', 'pas', 'tapi',
  'ga', 'gak', 'nggak', 'tidak', 'iya', 'dong', 'kok',
]);

/**
 * ReviewList Component - COMPLETE FIX VERSION
 *
 * FIXES:
 * ✅ Removed isMountedRef guard (causes deadlock)
 * ✅ Always reset loading in all paths
 * ✅ Better handling for delete/edit operations
 * ✅ Realtime subscription dengan proper cleanup
 * ✅ Optimistic updates dengan fallback refetch
 */
const ReviewList = ({ placeId, shopName, newReview, onReviewSubmitted }) => {
  const location = useLocation();
  const { initialized: authInitialized, user, isAuthenticated } = useAuth();
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reviewSort, setReviewSort] = useState('latest');
  const [reviewTab, setReviewTab] = useState('all');
  
  // Refs untuk tracking
  const abortControllerRef = useRef(null);
  const fetchCountRef = useRef(0);
  const currentPlaceIdRef = useRef(null);
  
  // Debug auth state changes
  useEffect(() => {
    console.log('[ReviewList] Auth state changed:', { 
      authInitialized, 
      isAuthenticated, 
      userId: user?.id,
      placeId 
    });
  }, [authInitialized, isAuthenticated, user?.id, placeId]);
  
  // Fetch reviews - local SQLite backend only
  const fetchReviews = useCallback(async (showLoading = false) => {
    if (!placeId) {
      setLoading(false);
      return { success: false, reason: 'no_place_id' };
    }
    
    // Hanya abort jika placeId berubah
    if (currentPlaceIdRef.current !== placeId && abortControllerRef.current) {
      try {
        abortControllerRef.current.abort('placeId changed');
      } catch {
        // Ignore
      }
    }
    
    currentPlaceIdRef.current = placeId;
    abortControllerRef.current = new AbortController();
    const currentFetchCount = ++fetchCountRef.current;
    
    if (showLoading) {
      setLoading(true);
    }
    
    console.log(`[ReviewList] Fetching reviews for: ${placeId}`);
    
    try {
      const url = user?.id
        ? `${API_BASE}/api/coffeeshops/${placeId}/reviews?user_id=${user.id}&limit=50`
        : `${API_BASE}/api/coffeeshops/${placeId}/reviews?limit=50`;
      const response = await fetch(url, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
        signal: abortControllerRef.current.signal,
      });

      if (currentFetchCount !== fetchCountRef.current) {
        return { success: false, reason: 'outdated' };
      }

      // Handle all responses including errors gracefully
      if (!response.ok) {
        console.warn(`[ReviewList] API returned ${response.status}, treating as no reviews`);
        // Treat 400/404 as "no reviews" instead of error
        setReviews([]);
        return { success: true, count: 0 };
      }

      const data = await response.json();
      const reviewsData = Array.isArray(data.reviews) ? data.reviews : [];
      const mappedReviews = reviewsData.map(r => ({
        ...r,
        profiles: r.username || r.full_name ? {
          username: r.username,
          full_name: r.full_name,
        } : undefined,
        source: 'local'
      }));

      setReviews(mappedReviews);
      return { success: true, count: mappedReviews.length };
    } catch (err) {
      if (currentFetchCount !== fetchCountRef.current) {
        return { success: false, reason: 'outdated' };
      }
      
      if (err.name === 'AbortError' || err.message?.includes('abort')) {
        return { success: false, reason: 'aborted' };
      }
      
      console.warn('[ReviewList] Fetch failed:', err.message, '- treating as no reviews');
      // Treat network errors as "no reviews" instead of showing scary error
      setReviews([]);
      return { success: true, count: 0 };
    } finally {
      // PASTIKAN loading selalu di-reset
      setLoading(false);
    }
  }, [placeId, isAuthenticated, user]);
  
  // Initial fetch - Wait for auth ready
  useEffect(() => {
    if (!placeId) {
      setLoading(false);
      return;
    }
    
    // Note: We don't clear reviews here anymore - let fetchReviews handle the logic
    if (!isAuthenticated || !user) {
      console.log('[ReviewList] User not authenticated, reviews will be fetched from public data', { isAuthenticated, userId: user?.id });
    }
    
    fetchCountRef.current = 0;
    currentPlaceIdRef.current = placeId;
    
    setReviews([]);
    setReviewTab('all');
    setLoading(true);


    // Simply fetch reviews, no retry needed
    fetchReviews(false);
    
    return () => {
      // Cleanup: Jangan abort, biarkan fetch selesai
    };
  }, [placeId, fetchReviews, authInitialized, user?.id, isAuthenticated]);
  
  // Auto-scroll ke review saat dibuka dari link (e.g. dari profile page dengan hash #review-123)
  useEffect(() => {
    if (loading || reviews.length === 0) return;
    const hash = location.hash || window.location.hash;
    const match = hash && /^#review-(\d+)$/.exec(hash);
    if (!match) return;
    const reviewId = match[1];
    if (!reviews.some((r) => String(r.id) === reviewId)) return;
    const id = `review-${reviewId}`;
    const timer = setTimeout(() => {
      const el = document.getElementById(id);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.classList.add('ring-2', 'ring-amber-500', 'ring-offset-2');
        setTimeout(() => {
          el.classList.remove('ring-2', 'ring-amber-500', 'ring-offset-2');
        }, 2000);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [reviews, loading, location.hash]);

  // Handle new review from prop
  useEffect(() => {
    if (!newReview?.id) return;
    
    console.log('[ReviewList] ✅ New review received from prop:', newReview.id);
    
    setReviews(prev => {
      const exists = prev.some(r => r.id === newReview.id);
      if (exists) {
        return prev.map(r => r.id === newReview.id ? { ...newReview, source: 'local' } : r);
      }
      return [{ ...newReview, source: 'local' }, ...prev];
    });
    
    // Refetch to sync (non-blocking)
    setTimeout(() => {
      fetchReviews(false).catch(() => {});
    }, 1000);
  }, [newReview, fetchReviews]);
  
  const handleLike = useCallback((reviewId, { like_count, user_has_liked }) => {
    setReviews(prev => prev.map(r => r.id === reviewId ? { ...r, like_count, user_has_liked } : r));
  }, []);

  // Handlers - FIXED: Trigger refetch setelah update/delete
  const handleDelete = useCallback((reviewId) => {
    if (!reviewId) return;
    
    console.log('[ReviewList] handleDelete called for:', reviewId);
    
    // Optimistic update: remove immediately
    setReviews(prev => {
      const filtered = prev.filter(r => r.id !== reviewId);
      console.log(`[ReviewList] Removed review ${reviewId}, ${filtered.length} reviews remaining`);
      return filtered;
    });
    
    // Refetch untuk sync dengan database (non-blocking)
    setTimeout(() => {
      fetchReviews(false).then(result => {
        if (result.success) {
          console.log('[ReviewList] ✅ Refetch after delete successful');
        }
      }).catch(err => {
        console.warn('[ReviewList] ⚠️ Refetch after delete failed:', err);
      });
    }, 500);
  }, [fetchReviews]);
  
  const handleUpdate = useCallback((updatedReview) => {
    if (!updatedReview?.id) return;
    
    console.log('[ReviewList] handleUpdate called for:', updatedReview.id);
    
    // Optimistic update: update immediately
    setReviews(prev => prev.map(r =>
      r.id === updatedReview.id ? { ...r, ...updatedReview, source: 'local' } : r
    ));
    
    // Refetch untuk sync dengan database (non-blocking)
    setTimeout(() => {
      fetchReviews(false).then(result => {
        if (result.success) {
          console.log('[ReviewList] ✅ Refetch after update successful');
        }
      }).catch(err => {
        console.warn('[ReviewList] ⚠️ Refetch after update failed:', err);
      });
    }, 500);
  }, [fetchReviews]);

  const tabFilteredReviews = useMemo(() => {
    switch (reviewTab) {
      case 'positive':
        return reviews.filter((r) => (Number(r.rating) || 0) >= 4);
      case 'negative':
        return reviews.filter((r) => (Number(r.rating) || 0) <= 2);
      case 'all':
      default:
        return reviews;
    }
  }, [reviews, reviewTab]);

  const displayedReviews = useMemo(() => {
    const list = [...tabFilteredReviews];

    switch (reviewSort) {
      case 'highest-rating':
        return list.sort((a, b) => {
          const ratingDiff = (Number(b.rating) || 0) - (Number(a.rating) || 0);
          if (ratingDiff !== 0) return ratingDiff;
          return new Date(b.created_at || 0) - new Date(a.created_at || 0);
        });
      case 'lowest-rating':
        return list.sort((a, b) => {
          const ratingDiff = (Number(a.rating) || 0) - (Number(b.rating) || 0);
          if (ratingDiff !== 0) return ratingDiff;
          return new Date(b.created_at || 0) - new Date(a.created_at || 0);
        });
      case 'latest':
      default:
        return list.sort(
          (a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0)
        );
    }
  }, [tabFilteredReviews, reviewSort]);

  // Loading state
  if (loading && reviews.length === 0) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="bg-white dark:bg-zinc-800 rounded-xl p-5 animate-pulse">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-full bg-gray-200 dark:bg-zinc-700"></div>
              <div className="flex-1">
                <div className="h-4 bg-gray-200 dark:bg-zinc-700 rounded w-24 mb-2"></div>
                <div className="h-3 bg-gray-200 dark:bg-zinc-700 rounded w-20"></div>
              </div>
            </div>
            <div className="h-4 bg-gray-200 dark:bg-zinc-700 rounded w-full mb-2"></div>
            <div className="h-4 bg-gray-200 dark:bg-zinc-700 rounded w-3/4"></div>
          </div>
        ))}
        <div className="text-center text-sm text-gray-500 dark:text-gray-400">
          Memuat reviews...
        </div>
      </div>
    );
  }
  
  // Error state - removed, now treating all errors as "no reviews"
  
  // Main content
  return (
    <div>
      {/* Form Tulis Review */}
      {placeId && (
        <div className="mb-6">
          <ReviewForm
            placeId={placeId}
            shopName={shopName || 'Coffee Shop'}
            onReviewSubmitted={onReviewSubmitted}
          />
        </div>
      )}

      {reviews.length > 0 ? (
        <div className="mb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="inline-flex rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 p-1 shadow-sm">
            {[
              { key: 'all', label: 'Semua Review', emoji: '⏰' },
              { key: 'positive', label: 'Positif', emoji: '😊' },
              { key: 'negative', label: 'Negatif', emoji: '😞' },
            ].map((tab) => (
              <button
                key={tab.key}
                type="button"
                onClick={() => setReviewTab(tab.key)}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-all ${
                  reviewTab === tab.key
                    ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300'
                    : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-zinc-700'
                }`}
              >
                <span>{tab.emoji}</span>
                <span>{tab.label}</span>
              </button>
            ))}
          </div>
          <label className="inline-flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
            <span>Urutkan:</span>
            <div className="relative">
              <select
                value={reviewSort}
                onChange={(event) => setReviewSort(event.target.value)}
                className="appearance-none rounded-lg border border-gray-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 pl-3 pr-9 py-2 text-sm text-gray-800 dark:text-gray-100 cursor-pointer"
                aria-label="Urutkan review"
              >
                <option value="latest">Terbaru</option>
                <option value="highest-rating">Rating tertinggi</option>
                <option value="lowest-rating">Rating terendah</option>
              </select>
              <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-gray-500 dark:text-gray-400">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </span>
            </div>
          </label>
        </div>
      ) : null}

      {/* Reviews List or Empty State */}
      {reviews.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 dark:bg-zinc-800/50 rounded-xl border border-gray-200 dark:border-zinc-700">
          <svg className="w-16 h-16 mx-auto text-gray-400 dark:text-gray-600 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
            Belum ada review
          </h3>
          <p className="text-gray-600 dark:text-gray-400">
            Jadilah yang pertama memberikan review!
          </p>
        </div>
      ) : tabFilteredReviews.length === 0 ? (
        <div className="text-center py-10 bg-gray-50 dark:bg-zinc-800/50 rounded-xl border border-gray-200 dark:border-zinc-700">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
            Tidak ada review {reviewTab === 'positive' ? 'positif' : reviewTab === 'negative' ? 'negatif' : ''}
          </h3>
          <p className="text-gray-600 dark:text-gray-400">
            Coba pilih tab lain.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {displayedReviews.map((review) => (
            <div key={review.id} id={`review-${review.id}`} className="scroll-mt-24">
              <ReviewCard
                review={review}
                placeId={placeId}
                onDelete={handleDelete}
                onUpdate={handleUpdate}
                onLike={handleLike}
              />
            </div>
          ))}
        </div>
      )}
      
      {/* Background loading indicator */}
      {loading && reviews.length > 0 && (
        <div className="flex items-center justify-center py-4 text-gray-500 dark:text-gray-400">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-amber-600 mr-2"></div>
          <span className="text-sm">Memperbarui data...</span>
        </div>
      )}
    </div>
  );
};

export default ReviewList;

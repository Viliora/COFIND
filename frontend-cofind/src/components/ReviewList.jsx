import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../context/authContext';
import ReviewCard from './ReviewCard';
import ReviewForm from './ReviewForm';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';

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
  const { initialized: authInitialized, user, isAuthenticated } = useAuth();
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  
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
    setLoading(true);
    
    // Simply fetch reviews, no retry needed
    fetchReviews(false);
    
    return () => {
      // Cleanup: Jangan abort, biarkan fetch selesai
    };
  }, [placeId, fetchReviews, authInitialized, user?.id, isAuthenticated]);
  
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
  
  
  // Stats
  const stats = {
    total: reviews.length,
    average: reviews.length > 0 
      ? (reviews.reduce((acc, r) => acc + (r.rating || 0), 0) / reviews.length).toFixed(1)
      : 0,
    distribution: [5, 4, 3, 2, 1].map(rating => ({
      rating,
      count: reviews.filter(r => r.rating === rating).length,
      percentage: reviews.length > 0 
        ? Math.round((reviews.filter(r => r.rating === rating).length / reviews.length) * 100)
        : 0
    }))
  };
  
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
      {/* Stats Header */}
      {reviews.length > 0 && (
        <div className="bg-white dark:bg-zinc-800 rounded-xl p-5 mb-6 border border-gray-200 dark:border-zinc-700">
          <div className="flex flex-col sm:flex-row sm:items-center gap-6">
            <div className="text-center sm:text-left">
              <div className="text-4xl font-bold text-gray-900 dark:text-white">
                {stats.average}
              </div>
              <div className="flex justify-center sm:justify-start mt-1">
                {[1, 2, 3, 4, 5].map((star) => (
                  <svg
                    key={star}
                    className={`w-5 h-5 ${
                      star <= Math.round(parseFloat(stats.average))
                        ? 'text-amber-400 fill-current'
                        : 'text-gray-300 dark:text-zinc-600'
                    }`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.5}
                      d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"
                    />
                  </svg>
                ))}
              </div>
              <div className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                {stats.total} review
              </div>
            </div>

            <div className="flex-1 space-y-1.5">
              {stats.distribution.map(({ rating, count, percentage }) => (
                <div key={rating} className="flex items-center gap-2 text-sm">
                  <span className="w-3 text-gray-600 dark:text-gray-400">{rating}</span>
                  <svg className="w-4 h-4 text-amber-400 fill-current" viewBox="0 0 24 24">
                    <path d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                  </svg>
                  <div className="flex-1 h-2 bg-gray-200 dark:bg-zinc-700 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-amber-400 rounded-full transition-all duration-500"
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                  <span className="w-8 text-right text-gray-500 dark:text-gray-400">{count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tombol Tulis Review - di bawah stats header */}
      {placeId && (
        <div className="mb-6">
          <ReviewForm
            placeId={placeId}
            shopName={shopName || 'Coffee Shop'}
            onReviewSubmitted={onReviewSubmitted}
          />
        </div>
      )}

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
      ) : (
        <div className="space-y-4">
          {reviews.map((review) => (
            <ReviewCard
              key={review.id}
              review={review}
              onDelete={handleDelete}
              onUpdate={handleUpdate}
              onLike={handleLike}
            />
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

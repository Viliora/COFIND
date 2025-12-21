import React, { useState, useEffect, useRef, useCallback } from 'react';
import { supabase, isSupabaseConfigured } from '../lib/supabase';
import ReviewCard from './ReviewCard';
import { trackError } from '../utils/errorTracker';

const ReviewList = ({ placeId, newReview }) => {
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load reviews - ALWAYS FETCH FRESH (no cache)
  // Re-fetch on: placeId change, component mount
  // NOTE: visibilitychange dihapus karena terlalu agresif dan menyebabkan review hilang
  // Request deduplication - prevent multiple simultaneous requests
  // Use ref instead of state to avoid race conditions
  const pendingRequestRef = useRef(false);
  const abortControllerRef = useRef(null);
  const lastFetchTimeRef = useRef(0);
  const reviewsLengthRef = useRef(0);
  
  // Force refresh mechanism - increment untuk trigger re-fetch
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  
  // Update reviewsLengthRef whenever reviews change
  useEffect(() => {
    reviewsLengthRef.current = reviews.length;
  }, [reviews.length]);
  
  // Real-time subscription untuk auto-update saat ada perubahan di Supabase
  useEffect(() => {
    if (!isSupabaseConfigured || !supabase || !placeId) return;
    
    console.log('[ReviewList] Setting up real-time subscriptions for place_id:', placeId);
    
    // Subscribe to changes in reviews table
    const reviewsChannel = supabase
      .channel(`reviews:${placeId}`)
      .on(
        'postgres_changes',
        {
          event: '*', // Listen to all events (INSERT, UPDATE, DELETE)
          schema: 'public',
          table: 'reviews',
          filter: `place_id=eq.${placeId}`
        },
        (payload) => {
          console.log('[ReviewList] 🔔 Real-time review update:', payload.eventType, payload.new?.id || payload.old?.id);
          
          // Handle different event types
          if (payload.eventType === 'INSERT' && payload.new) {
            // New review added - optimistic update + smart refetch
            console.log('[ReviewList] New review detected via real-time');
            setTimeout(() => {
              pendingRequestRef.current = false;
              setRefreshTrigger(prev => prev + 1);
            }, 200); // Reduced delay untuk faster update
          } else if (payload.eventType === 'UPDATE' && payload.new) {
            // Review updated - update local state immediately
            console.log('[ReviewList] Review updated via real-time');
            setReviews(prev => prev.map(r => 
              r.id === payload.new.id ? { ...r, ...payload.new } : r
            ));
            // Optional: trigger refetch untuk sync
            setTimeout(() => {
              pendingRequestRef.current = false;
              setRefreshTrigger(prev => prev + 1);
            }, 200);
          } else if (payload.eventType === 'DELETE' && payload.old) {
            // Review deleted - remove from local state immediately
            console.log('[ReviewList] Review deleted via real-time');
            setReviews(prev => prev.filter(r => r.id !== payload.old.id));
          }
        }
      )
      .subscribe((status) => {
        console.log('[ReviewList] Reviews subscription status:', status);
      });
    
    // Subscribe to changes in review_replies table (untuk reply updates)
    // CRITICAL: Subscribe to replies untuk detect reply baru tanpa perlu refetch semua reviews
    const repliesChannel = supabase
      .channel(`replies:${placeId}`)
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'review_replies',
          // Filter by review_id yang ada di current reviews
          // Note: Supabase doesn't support complex filters, so we'll handle filtering in callback
        },
        (payload) => {
          console.log('[ReviewList] 🔔 Real-time reply update:', payload.eventType, payload.new?.review_id || payload.old?.review_id);
          
          // Update local state untuk reply yang baru ditambahkan/diupdate
          if (payload.eventType === 'INSERT' && payload.new) {
            // New reply added - update review yang sesuai
            setReviews(prev => prev.map(review => {
              if (review.id === payload.new.review_id) {
                // Add new reply to existing replies
                const updatedReplies = [...(review.replies || []), payload.new];
                return { ...review, replies: updatedReplies };
              }
              return review;
            }));
          } else if (payload.eventType === 'UPDATE' && payload.new) {
            // Reply updated - update reply di review
            setReviews(prev => prev.map(review => {
              if (review.id === payload.new.review_id) {
                const updatedReplies = (review.replies || []).map(reply =>
                  reply.id === payload.new.id ? payload.new : reply
                );
                return { ...review, replies: updatedReplies };
              }
              return review;
            }));
          } else if (payload.eventType === 'DELETE' && payload.old) {
            // Reply deleted - remove from review
            setReviews(prev => prev.map(review => {
              if (review.id === payload.old.review_id) {
                const updatedReplies = (review.replies || []).filter(reply => reply.id !== payload.old.id);
                return { ...review, replies: updatedReplies };
              }
              return review;
            }));
          }
        }
      )
      .subscribe((status) => {
        console.log('[ReviewList] Replies subscription status:', status);
      });
    
    // Cleanup subscriptions on unmount or placeId change
    return () => {
      console.log('[ReviewList] Cleaning up real-time subscriptions');
      if (supabase) {
        supabase.removeChannel(reviewsChannel);
        supabase.removeChannel(repliesChannel);
      }
    };
  }, [placeId]);
  
  // ============================================
  // MOVE loadReviews KELUAR dari useEffect untuk performance
  // Function ini dipanggil dari useEffect, tapi didefinisikan di luar
  // Wrapped dengan useCallback untuk mencegah re-creation
  // ============================================
  const loadReviews = useCallback(async (preserveExisting = false, forceRefresh = false) => {
    // CRITICAL: Prevent duplicate requests
    if (pendingRequestRef.current && !forceRefresh) {
      console.log('[ReviewList] ⏸️ Request already in progress, skipping duplicate request');
      return;
    }
    if (!placeId) {
      console.warn('[ReviewList] ⚠️ No placeId provided');
      setLoading(false);
      return;
    }
    
    console.log('[ReviewList] 🔄 loadReviews called:', { placeId, preserveExisting, forceRefresh, pending: pendingRequestRef.current });
    
    // SIMPLIFIED COOLDOWN: Only 500ms untuk prevent spam, no complex logic
    // SKIP cooldown check if this is first load (lastFetchTimeRef === 0)
    const now = Date.now();
    const timeSinceLastFetch = now - lastFetchTimeRef.current;
    const cooldownTime = 500; // 0.5 detik - cukup untuk prevent spam tapi tetap fast
    const isFirstLoad = lastFetchTimeRef.current === 0;
    
    if (!forceRefresh && !isFirstLoad && timeSinceLastFetch < cooldownTime) {
      console.log(`[ReviewList] Cooldown active (${timeSinceLastFetch}ms < ${cooldownTime}ms)`);
      return;
    }
    
    if (isFirstLoad) {
      console.log('[ReviewList] First load detected - skipping cooldown check');
    }
    
    console.log('[ReviewList] 🚀 Fetching reviews for place_id:', placeId, 'Timestamp:', new Date().toISOString());
    
    // OPTIMISTIC UI: Only set loading if we don't have reviews yet
    if (reviewsLengthRef.current === 0) {
      setLoading(true);
    } else {
      console.log('[ReviewList] Background refresh - keeping existing reviews visible');
    }
    
    setError(null);
    pendingRequestRef.current = true;
    
    // CRITICAL: Create ONE AbortController for this entire loadReviews call
    // This controller will be used for ALL retry attempts
    // Only component unmount should abort this controller, not retry logic
    const loadReviewsController = new AbortController();
    abortControllerRef.current = loadReviewsController;
    
    console.log('[ReviewList] ✨ Created AbortController for loadReviews call');
    
    // ============================================
    // RETRY LOGIC: Auto-retry untuk handle network hiccups
    // Use SAME controller for all attempts - don't create new ones!
    // ============================================
    const maxRetries = 2; // Total 3 attempts (0, 1, 2)
    let data = null;
    
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        // Check if controller was aborted (e.g. component unmount)
        if (loadReviewsController.signal.aborted) {
          console.log('[ReviewList] 🛑 Controller already aborted, stopping retry loop');
          return; // Exit silently if aborted
        }
        
        const startTime = Date.now();
        console.log(`[ReviewList] 🚀 Attempt ${attempt + 1}/${maxRetries + 1}: Fetching main reviews for place:`, placeId);
        
        const result = await supabase
          .from('reviews')
          .select('id, user_id, place_id, rating, text, created_at, updated_at')
          .eq('place_id', placeId)
          .order('created_at', { ascending: false })
          .limit(25)
          .abortSignal(loadReviewsController.signal);
        
        const queryDuration = Date.now() - startTime;
        console.log(`[ReviewList] ✅ Query completed in ${queryDuration}ms`);
        
        if (result.error) {
          const errorMsg = result.error.message || result.error.toString() || 'Unknown error';
          console.warn(`[ReviewList] ⚠️ Attempt ${attempt + 1}/${maxRetries + 1} failed:`, errorMsg);
          
          // Check if it's an abort error (component unmount)
          const isAbortError = errorMsg.includes('aborted') || errorMsg.includes('abort');
          
          // If abort error, don't retry and return silently
          if (isAbortError) {
            console.log(`[ReviewList] 🛑 Request aborted (likely component unmount or navigation)`);
            return; // Return silently, no error message
          }
          
          // Retry untuk network/timeout/fetch errors ONLY (not abort)
          const isRetryable = errorMsg.includes('network') || 
                              errorMsg.includes('timeout') ||
                              errorMsg.includes('fetch');
          
          if (isRetryable && attempt < maxRetries) {
            const retryDelay = 1000 * (attempt + 1); // 1s, 2s exponential backoff
            console.log(`[ReviewList] ⏳ Will retry in ${retryDelay}ms... (${maxRetries - attempt} attempts left)`);
            await new Promise(resolve => setTimeout(resolve, retryDelay));
            continue; // Try again
          }
          
          // Not retryable or last attempt - fail
          console.error(`[ReviewList] ❌ All ${attempt + 1} attempts failed. Final error:`, result.error);
          setError('Gagal memuat reviews');
          if (!preserveExisting) setReviews([]);
          return;
        }
        
        // SUCCESS!
        data = result.data;
        
        if (!data || data.length === 0) {
          console.log('[ReviewList] No reviews found for place_id:', placeId);
          setReviews([]);
          return;
        }
        
        console.log(`[ReviewList] ✅ SUCCESS on attempt ${attempt + 1}! Found ${data.length} reviews`);
        break; // Exit retry loop on success
        
      } catch (err) {
        const errMsg = err.message || err.toString() || 'Unknown exception';
        const errName = err.name || 'UnknownError';
        
        // Log detailed error info
        console.warn(`[ReviewList] ⚠️ Attempt ${attempt + 1}/${maxRetries + 1} exception:`, {
          name: errName,
          message: errMsg,
          isAbortError: errName === 'AbortError',
          stack: err.stack
        });
        
        // Check if error is retryable (network, timeout, abort)
        // BUT: Don't retry if it's our own intentional abort (from cleanup or new attempt)
        const isAbortError = errName === 'AbortError' || errMsg.includes('aborted');
        const isTimeoutError = errMsg.includes('timeout');
        const isNetworkError = errMsg.includes('network') || errMsg.includes('fetch');
        
        const isRetryable = isTimeoutError || isNetworkError;
        
        // Log reason
        if (isAbortError && !isRetryable) {
          console.log(`[ReviewList] 🛑 Request aborted (likely component unmount or navigation)`);
          // Don't log as error, don't show error to user, just return silently
          return;
        }
        
        if (isRetryable && attempt < maxRetries) {
          const retryDelay = 1000 * (attempt + 1); // 1s, 2s
          console.log(`[ReviewList] ⏳ Will retry in ${retryDelay}ms... (${maxRetries - attempt} attempts left)`);
          await new Promise(resolve => setTimeout(resolve, retryDelay));
          continue; // Try again
        }
        
        // Last attempt failed - only log if not abort error
        if (!isAbortError) {
          console.error(`[ReviewList] ❌ All ${attempt + 1} attempts failed. Final exception:`, err);
          trackError(err, { placeId, action: 'loadReviews', attempts: attempt + 1 });
          setError('Gagal memuat reviews');
        }
        
        if (!preserveExisting) setReviews([]);
        return;
      }
    }
    
    // At this point, data should be loaded successfully
    if (!data) {
      console.error('[ReviewList] ❌ No data after all retries');
      setError('Gagal memuat reviews');
      if (!preserveExisting) setReviews([]);
      return;
    }
    
    try {
      const totalStartTime = Date.now(); // Track total time for logging
      
      // Check if aborted before batch queries
      if (loadReviewsController.signal.aborted) {
        console.log('[ReviewList] 🛑 Aborted before batch queries, stopping');
        return;
      }
      
      // ============================================
      // STEP 2: Fetch related data in PARALLEL
      // ============================================
      const userIds = [...new Set(data.map(r => r.user_id))];
      const reviewIds = data.map(r => r.id);
      
      console.log('[ReviewList] Step 2: Fetching profiles, photos, replies in parallel...');
      const batchStartTime = Date.now();
      
      // CRITICAL: Use the same abort controller for batch queries
      const currentSignal = loadReviewsController.signal;
      
      const [profilesResult, photosResult, repliesResult] = await Promise.all([
        supabase
          .from('profiles')
          .select('id, username, avatar_url, full_name')
          .in('id', userIds)
          .abortSignal(currentSignal),
        
        supabase
          .from('review_photos')
          .select('id, review_id, photo_url')
          .in('review_id', reviewIds)
          .abortSignal(currentSignal),
        
        supabase
          .from('review_replies')
          .select('id, review_id, user_id, text, created_at, profiles:user_id(username, avatar_url, full_name)')
          .in('review_id', reviewIds)
          .order('created_at', { ascending: true })
          .abortSignal(currentSignal)
      ]);
      
      const batchDuration = Date.now() - batchStartTime;
      console.log(`[ReviewList] ✅ Batch queries completed in ${batchDuration}ms`);
      
      // ============================================
      // STEP 3: Map results efficiently
      // ============================================
      const profilesMap = (profilesResult.data || []).reduce((acc, p) => {
        acc[p.id] = p;
        return acc;
      }, {});
      
      const photosMap = (photosResult.data || []).reduce((acc, p) => {
        if (!acc[p.review_id]) acc[p.review_id] = [];
        acc[p.review_id].push(p);
        return acc;
      }, {});
      
      const repliesMap = (repliesResult.data || []).reduce((acc, r) => {
        if (!acc[r.review_id]) acc[r.review_id] = [];
        acc[r.review_id].push(r);
        return acc;
      }, {});
      
      // ============================================
      // STEP 4: Combine all data
      // ============================================
      const mappedReviews = data.map(r => ({
        ...r,
        profiles: profilesMap[r.user_id] || null,
        photos: photosMap[r.id] || [],
        replies: repliesMap[r.id] || [],
        source: 'supabase'
      }));
      
      const totalDuration = Date.now() - totalStartTime;
      console.log(`[ReviewList] ✅ TOTAL fetch completed in ${totalDuration}ms - Setting ${mappedReviews.length} reviews to state`);
      
      setReviews(mappedReviews);
      
    } catch (err) {
      // CRITICAL: Error di batch queries (profiles, photos, replies) adalah NON-CRITICAL
      // Reviews sudah berhasil di-fetch, hanya accessory data yang gagal
      // Jadi tampilkan reviews tanpa profiles/photos/replies, JANGAN tampilkan error
      
      const errorMessage = err?.message || err?.toString() || 'Unknown error';
      console.warn('[ReviewList] ⚠️ Non-critical error during batch fetch (reviews will still display):', {
        message: errorMessage,
        error: err,
        placeId: placeId
      });
      
      // Track error untuk monitoring, tapi JANGAN set error state
      trackError(err, { placeId, action: 'loadReviews_batch', severity: 'warning' });
      
      // Fallback: Tampilkan reviews tanpa profiles/photos/replies
      if (data && data.length > 0) {
        const basicReviews = data.map(r => ({
          ...r,
          profiles: null,
          photos: [],
          replies: [],
          source: 'supabase'
        }));
        setReviews(basicReviews);
        console.log('[ReviewList] ✅ Displaying reviews without accessory data (fallback mode)');
      } else if (!preserveExisting) {
        setReviews([]);
      }
    } finally {
      pendingRequestRef.current = false;
      setLoading(false);
      lastFetchTimeRef.current = Date.now();
      abortControllerRef.current = null;
    }
  }, [placeId]); // Include placeId as dependency
  
  // ============================================
  // useEffect: Trigger loadReviews on mount/change
  // ============================================
  useEffect(() => {
    if (!placeId) {
      console.warn('[ReviewList] No placeId, skipping load');
      setLoading(false);
      return;
    }
    
    // Track if component is mounted to prevent state updates after unmount
    let isMounted = true;
    
    console.log('[ReviewList] 🚀 Starting initial load for placeId:', placeId, 'refreshTrigger:', refreshTrigger);
    
    // CRITICAL: Call loadReviews WITHOUT forceRefresh untuk respect guard
    // forceRefresh=true bypasses pendingRequestRef check, causing multiple simultaneous calls
    // Guard will naturally allow first call to proceed, and block subsequent calls
    
    // Wrap loadReviews call to check isMounted
    const safeLoadReviews = async () => {
      if (isMounted) {
        await loadReviews(false, false);
      }
    };
    
    safeLoadReviews();
    
    // Cleanup on unmount
    return () => {
      console.log('[ReviewList] 🧹 useEffect cleanup - component unmounting');
      isMounted = false; // Mark as unmounted
      
      if (abortControllerRef.current) {
        try {
          console.log('[ReviewList] 🛑 Aborting pending request due to unmount');
          abortControllerRef.current.abort();
        } catch {
          // Silently catch abort errors during cleanup
          console.log('[ReviewList] Cleanup abort (expected during unmount)');
        }
        abortControllerRef.current = null;
      }
      pendingRequestRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [placeId, refreshTrigger]); // Intentionally omit loadReviews to prevent dependency loop

  // Handle new review added - OPTIMISTIC UI UPDATE
  useEffect(() => {
    if (newReview && newReview.id) {
      // Ensure review has profile data and source
      const newReviewWithSource = {
        ...newReview,
        source: 'supabase',
        photos: newReview.photos || [],
        replies: newReview.replies || [],
        // Ensure author_name untuk backward compatibility
        author_name: newReview.profiles?.username || newReview.profiles?.full_name || 'Anonim'
      };
      
      console.log('[ReviewList] ✅ New review added (optimistic update):', {
        id: newReviewWithSource.id,
        username: newReviewWithSource.profiles?.username || 'No username',
        hasProfile: !!newReviewWithSource.profiles,
        user_id: newReviewWithSource.user_id
      });
      
      // OPTIMISTIC UI: Add review immediately to UI (instant feedback)
      setLoading(false);
      
      // Check if review already exists (prevent duplicates)
      setReviews(prev => {
        const exists = prev.some(r => r.id === newReviewWithSource.id);
        if (exists) {
          console.log('[ReviewList] Review already exists, updating instead');
          // Update existing review instead of adding duplicate
          return prev.map(r => r.id === newReviewWithSource.id ? newReviewWithSource : r);
        }
        // Add new review to the top of the list
        console.log('[ReviewList] Adding new review to list. Total before:', prev.length);
        const updated = [newReviewWithSource, ...prev];
        console.log('[ReviewList] Total after:', updated.length);
        return updated;
      });
      
      // Smart refetch: Wait a bit for Supabase to commit, then refresh to sync
      // This ensures we have the latest data from database
      setTimeout(() => {
        console.log('[ReviewList] Triggering smart refetch after new review (500ms delay)');
        pendingRequestRef.current = false;
        if (abortControllerRef.current) {
          try {
            abortControllerRef.current.abort();
          } catch (e) {
            console.warn('[ReviewList] Error aborting before refetch:', e);
          }
          abortControllerRef.current = null;
        }
        setRefreshTrigger(prev => prev + 1);
      }, 500); // 500ms delay untuk memastikan Supabase sudah commit transaction
    }
  }, [newReview]);
  
  // Handle review delete
  const handleDelete = (reviewId) => {
    setReviews(prev => prev.filter(r => r.id !== reviewId));
  };

  // Handle review update - force refresh setelah edit
  const handleUpdate = (updatedReview) => {
    console.log('[ReviewList] Review updated, refreshing data...', updatedReview.id);
    
    // OPTIMISTIC UI: Update local state immediately untuk instant feedback
    setReviews(prev => prev.map(r => 
      r.id === updatedReview.id ? { ...r, ...updatedReview } : r
    ));
    
    // CRITICAL: Reset pending request flag sebelum trigger refresh
    // Ini memastikan refresh bisa berjalan meskipun ada request sebelumnya
    pendingRequestRef.current = false;
    
    // Abort any pending request sebelum refresh
    if (abortControllerRef.current) {
      try {
        abortControllerRef.current.abort();
      } catch (e) {
        console.warn('[ReviewList] Error aborting before refresh:', e);
      }
      abortControllerRef.current = null;
    }
    
    // Smart refetch: Wait a bit for Supabase to commit the transaction
    // Then trigger refresh to get latest data from database
    setTimeout(() => {
      console.log('[ReviewList] Triggering smart refetch after update (500ms delay for DB commit)');
      setRefreshTrigger(prev => prev + 1);
    }, 500); // 500ms delay untuk memastikan Supabase sudah commit transaction
    
    console.log('[ReviewList] ✅ Optimistic update applied, refresh scheduled');
  };

  // Calculate stats (always use all reviews, not filtered)
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

  // OPTIMISTIC UI: Tampilkan reviews yang sudah ada meski sedang loading
  // Ini mencegah skeleton muncul jika reviews sudah ada di state
  const shouldShowSkeleton = loading && reviews.length === 0;
  
  if (shouldShowSkeleton) {
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
      </div>
    );
  }

  return (
    <div>

      {/* Stats Header */}
      {reviews.length > 0 && (
        <div className="bg-white dark:bg-zinc-800 rounded-xl p-5 mb-6 border border-gray-200 dark:border-zinc-700">
          <div className="flex flex-col sm:flex-row sm:items-center gap-6">
            {/* Average Rating */}
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

            {/* Rating Distribution */}
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

      {/* Reviews List */}
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
              showSourceBadge={false}
            />
          ))}
        </div>
      )}

      {/* Error Message */}
      {/* Error message dengan solusi debugging */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-6 mb-6">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 w-10 h-10 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center">
              <svg className="w-6 h-6 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-red-900 dark:text-red-300 mb-2">
                {error}
              </h3>
              {error.includes('timeout') && (
                <div className="space-y-3 text-sm text-red-800 dark:text-red-400 mt-3">
                  <div className="bg-red-100 dark:bg-red-900/40 p-4 rounded-lg">
                    <p className="font-bold mb-2">🔍 Langkah Debugging:</p>
                    
                    <div className="space-y-3">
                      <div>
                        <p className="font-semibold mb-1">1️⃣ Verifikasi Index</p>
                        <p className="text-xs mb-1">Jalankan di Supabase SQL Editor:</p>
                        <pre className="bg-white dark:bg-red-950 p-2 rounded text-xs overflow-x-auto font-mono">
{`SELECT indexname FROM pg_indexes 
WHERE tablename = 'reviews';`}
                        </pre>
                        <p className="text-xs mt-1 italic">✅ Harus ada: <code className="bg-white dark:bg-red-950 px-1 rounded">idx_reviews_place_created</code></p>
                      </div>

                      <div>
                        <p className="font-semibold mb-1">2️⃣ Test Performa Query</p>
                        <p className="text-xs mb-1">Jalankan di Supabase SQL Editor:</p>
                        <pre className="bg-white dark:bg-red-950 p-2 rounded text-xs overflow-x-auto font-mono">
{`EXPLAIN ANALYZE
SELECT * FROM reviews 
WHERE place_id = '${placeId}' 
ORDER BY created_at DESC LIMIT 25;`}
                        </pre>
                        <p className="text-xs mt-1 italic">✅ Execution Time harus &lt; 100ms</p>
                        <p className="text-xs italic">✅ Harus pakai "Index Scan", BUKAN "Seq Scan"</p>
                      </div>

                      <div>
                        <p className="font-semibold mb-1">3️⃣ Cek RLS Policy</p>
                        <p className="text-xs mb-1">Jalankan di Supabase SQL Editor:</p>
                        <pre className="bg-white dark:bg-red-950 p-2 rounded text-xs overflow-x-auto font-mono">
{`SELECT policyname, qual 
FROM pg_policies 
WHERE tablename = 'reviews';`}
                        </pre>
                        <p className="text-xs mt-1 italic">✅ Policy SELECT harus simple: <code className="bg-white dark:bg-red-950 px-1 rounded">USING (true)</code></p>
                      </div>

                      <div className="border-t border-red-300 dark:border-red-700 pt-2 mt-2">
                        <p className="font-semibold mb-1">🔧 Jika Masih Timeout:</p>
                        <ul className="text-xs space-y-1 ml-4 list-disc">
                          <li>Cek koneksi internet (gunakan WiFi/4G yang stabil)</li>
                          <li>Buka Supabase Dashboard → Database → Performance</li>
                          <li>Cek CPU/Memory usage (jika tinggi, restart project)</li>
                          <li>Lihat file <code className="bg-white dark:bg-red-950 px-1 rounded">VERIFY_INDEX.sql</code> dan <code className="bg-white dark:bg-red-950 px-1 rounded">FIX_RLS_POLICY.sql</code></li>
                        </ul>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              <div className="flex gap-2 mt-4">
                <button
                  onClick={() => {
                    setError(null);
                    setRefreshTrigger(prev => prev + 1);
                  }}
                  className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white font-medium rounded-lg transition-colors inline-flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Coba Lagi
                </button>
                <button
                  onClick={() => {
                    window.open('https://supabase.com/dashboard/project/_/sql/new', '_blank');
                  }}
                  className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white font-medium rounded-lg transition-colors inline-flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                  Buka SQL Editor
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReviewList;

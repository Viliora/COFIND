import React, { useState, useEffect } from 'react';
import { supabase, isSupabaseConfigured } from '../lib/supabase';
import ReviewCard from './ReviewCard';

const ReviewList = ({ placeId, newReview }) => {
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load reviews - ALWAYS FETCH FRESH (no cache)
  // Re-fetch on: placeId change, component mount
  // NOTE: visibilitychange dihapus karena terlalu agresif dan menyebabkan review hilang
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [lastFetchTime, setLastFetchTime] = useState(0);
  
  useEffect(() => {
    const loadReviews = async (preserveExisting = false) => {
      if (!placeId) {
        console.warn('[ReviewList] No placeId provided');
        setLoading(false);
        return;
      }
      
      // Prevent re-fetch terlalu sering (minimal 2 detik antara fetch)
      const now = Date.now();
      if (!preserveExisting && now - lastFetchTime < 2000) {
        console.log('[ReviewList] Skipping fetch - too soon after last fetch');
        return;
      }
      
      console.log('[ReviewList] Loading reviews for place_id:', placeId, 'Timestamp:', new Date().toISOString(), 'Preserve existing:', preserveExisting);
      
      // OPTIMISTIC UI: Only set loading if we don't have reviews yet
      // If we have reviews, keep showing them while fetching in background
      if (reviews.length === 0) {
        setLoading(true);
      } else {
        // We have reviews - fetch in background without showing skeleton
        setLoading(false);
      }
      setError(null);
      
      // Only clear reviews on initial load or placeId change
      // Don't clear if we're just refreshing (preserve existing reviews)
      if (!preserveExisting) {
        setReviews([]);
        setLoading(true); // Only show skeleton if clearing reviews
      }

      try {
        let supabaseReviews = [];

        // Load from Supabase if configured
        if (isSupabaseConfigured && supabase) {
          try {
            // Force fresh fetch dengan cache-busting timestamp
            const cacheBuster = Date.now();
            console.log('[ReviewList] Fetching reviews from Supabase (fresh fetch, no cache):', placeId, 'Cache buster:', cacheBuster);
            
            // ULTRA-OPTIMIZED QUERY: Fetch reviews tanpa join untuk prevent timeout
            // Profiles akan di-fetch terpisah jika diperlukan (lazy load)
            const fetchPromise = supabase
              .from('reviews')
              .select(`
                id,
                user_id,
                place_id,
                rating,
                text,
                created_at,
                updated_at
              `)
              .eq('place_id', placeId)
              .order('created_at', { ascending: false })
              .limit(50); // Reduce limit untuk faster query
            
            // Reduce timeout to 10 seconds karena query lebih sederhana
            const timeoutPromise = new Promise((_, reject) => {
              setTimeout(() => {
                reject(new Error('Supabase request timeout after 10 seconds'));
              }, 10000);
            });
            
            let data = null;
            let fetchError = null;
            
            try {
              const result = await Promise.race([fetchPromise, timeoutPromise]);
              data = result.data;
              fetchError = result.error;
              
              // Step 2: Fetch photos dan replies secara terpisah jika diperlukan (lazy load)
              // Untuk sekarang, kita skip photos dan replies untuk prevent timeout
              // Bisa ditambahkan nanti jika diperlukan dengan separate queries
            } catch (raceError) {
              // Extract error message dengan lebih baik
              const timeoutMessage = raceError?.message || raceError?.toString() || 'Request timeout or failed';
              
              // Log as warning instead of error (timeout is expected in some cases)
              console.warn('[ReviewList] Supabase request failed or timed out:', {
                message: timeoutMessage,
                error: raceError,
                placeId: placeId
              });
              fetchError = raceError;
              // Don't block - continue without reviews
            }
            
            // Log hasil fetch untuk debugging
            console.log('[ReviewList] Supabase fetch result:', {
              dataCount: data?.length || 0,
              hasError: !!fetchError,
              error: fetchError?.message || fetchError?.toString(),
              errorCode: fetchError?.code,
              errorDetails: fetchError?.details
            });

            if (fetchError) {
              // Extract error message dengan lebih baik
              const errorMessage = fetchError.message || fetchError.toString() || 'Unknown error';
              const errorCode = fetchError.code || 'NO_CODE';
              const errorDetails = fetchError.details || null;
              const errorHint = fetchError.hint || null;
              
              // Log error dengan detail untuk debugging RLS issues
              console.error('[ReviewList] Error fetching from Supabase:', {
                message: errorMessage,
                code: errorCode,
                details: errorDetails,
                hint: errorHint,
                placeId: placeId,
                fullError: fetchError // Include full error untuk debugging
              });
              
              // Check if it's RLS error (401/403)
              if (errorCode === 'PGRST301' || errorMessage.includes('401') || errorMessage.includes('403')) {
                console.error('[ReviewList] ⚠️ RLS POLICY ERROR - Guest mungkin tidak bisa membaca reviews. Cek RLS policy di Supabase!');
                console.error('[ReviewList] Pastikan policy "Reviews viewable by everyone" menggunakan USING (true)');
              }
              
              // Check if it's timeout error
              if (errorMessage.includes('timeout')) {
                console.warn('[ReviewList] ⚠️ TIMEOUT ERROR - Query terlalu lambat. Consider simplify query atau increase timeout.');
              }
              
              // Don't throw - continue without reviews
            } else if (data) {
              // Fetch profiles separately untuk reviews yang berhasil di-fetch
              // Ini lebih cepat daripada join di query utama
              const userIds = [...new Set(data.map(r => r.user_id).filter(Boolean))];
              let profilesMap = {};
              
              if (userIds.length > 0) {
                try {
                  // Fetch profiles in batch (lebih cepat daripada join)
                  const { data: profilesData } = await supabase
                    .from('profiles')
                    .select('id, username, avatar_url, full_name')
                    .in('id', userIds);
                  
                  if (profilesData) {
                    profilesMap = profilesData.reduce((acc, p) => {
                      acc[p.id] = p;
                      return acc;
                    }, {});
                  }
                } catch (profileError) {
                  console.warn('[ReviewList] Error fetching profiles (non-critical):', profileError);
                  // Continue without profiles - reviews tetap bisa ditampilkan
                }
              }
              
              // Map reviews dengan format yang konsisten
              const mappedReviews = data.map(r => {
                const profile = profilesMap[r.user_id] || null;
                return {
                  ...r,
                  source: 'supabase',
                  // Ensure photos and replies are arrays (empty for now, bisa di-fetch terpisah nanti)
                  photos: r.photos || [],
                  replies: r.replies || [],
                  // Map profile data
                  profiles: profile,
                  // Ensure author_name untuk backward compatibility
                  author_name: profile?.username || profile?.full_name || 'Anonim'
                };
              });
              supabaseReviews = mappedReviews;
              
              // Merge dengan existing reviews jika preserveExisting = true
              if (preserveExisting) {
                setReviews(prev => {
                  // Merge: keep existing reviews yang tidak ada di fetch baru, add new ones
                  const existingIds = new Set(prev.map(r => r.id));
                  const newReviews = mappedReviews.filter(r => !existingIds.has(r.id));
                  const updatedReviews = prev.map(existing => {
                    const updated = mappedReviews.find(r => r.id === existing.id);
                    return updated || existing; // Use updated version if exists, otherwise keep existing
                  });
                  return [...newReviews, ...updatedReviews].sort((a, b) => {
                    // Sort by created_at descending
                    const dateA = new Date(a.created_at || 0);
                    const dateB = new Date(b.created_at || 0);
                    return dateB - dateA;
                  });
                });
              } else {
                setReviews(mappedReviews);
              }
              
              setLastFetchTime(Date.now());
              console.log('[ReviewList] Set reviews from Supabase:', mappedReviews.length, 'Preserve existing:', preserveExisting);
              console.log('[ReviewList] Sample review:', mappedReviews[0] ? {
                id: mappedReviews[0].id,
                text: mappedReviews[0].text?.substring(0, 50),
                username: mappedReviews[0].profiles?.username,
                rating: mappedReviews[0].rating
              } : 'No reviews');
            } else {
              console.warn('[ReviewList] Supabase returned no data and no error');
              // Don't clear reviews if preserveExisting = true
              if (!preserveExisting) {
                setReviews([]);
              }
            }
          } catch (supabaseError) {
            console.error('[ReviewList] Supabase fetch exception:', supabaseError);
            setReviews([]);
          }
        } else {
          console.log('[ReviewList] Supabase not configured or not available');
          setReviews([]);
        }
        
        // Ensure we have data before setting loading to false
        if (supabaseReviews.length === 0) {
          console.log('[ReviewList] No reviews found for place_id:', placeId);
        }

      } catch (err) {
        // Extract error message dengan lebih baik
        const errorMessage = err?.message || err?.toString() || 'Unknown error';
        const errorStack = err?.stack || null;
        
        console.error('[ReviewList] Error loading reviews:', {
          message: errorMessage,
          stack: errorStack,
          error: err,
          placeId: placeId
        });
        setError('Gagal memuat review');
        // CRITICAL: Don't clear reviews on error if preserveExisting = true
        // Keep existing reviews even if load fails
        if (!preserveExisting) {
          setReviews([]);
        }
      } finally {
        setLoading(false);
        setIsInitialLoad(false);
        // Use setTimeout to log after state update
        setTimeout(() => {
          console.log('[ReviewList] Loading completed. Total reviews in state:', reviews.length);
        }, 100);
      }
    };

    // Initial load - clear reviews
    loadReviews(false);
    
    // NOTE: visibilitychange listener dihapus karena terlalu agresif
    // Ini menyebabkan review hilang saat user tidak melakukan apa-apa
    // Jika perlu refresh, user bisa manual refresh page

    // Cleanup
    return () => {
      // No cleanup needed - visibilitychange listener sudah dihapus
    };
  }, [placeId]); // Only re-fetch when placeId changes

  // Handle new review added
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
      
      console.log('[ReviewList] New review added:', {
        id: newReviewWithSource.id,
        username: newReviewWithSource.profiles?.username || 'No username',
        hasProfile: !!newReviewWithSource.profiles,
        user_id: newReviewWithSource.user_id
      });
      
      // CRITICAL: Prevent race condition dengan loadReviews
      // Set loading to false jika sedang loading (untuk prevent skeleton)
      setLoading(false);
      
      // Check if review already exists (prevent duplicates)
      setReviews(prev => {
        const exists = prev.some(r => r.id === newReviewWithSource.id);
        if (exists) {
          console.log('[ReviewList] Review already exists, skipping');
          return prev;
        }
        // Add new review to the top of the list
        console.log('[ReviewList] Adding new review to list. Total before:', prev.length);
        const updated = [newReviewWithSource, ...prev];
        console.log('[ReviewList] Total after:', updated.length);
        return updated;
      });
    }
  }, [newReview]);

  // Handle review delete
  const handleDelete = (reviewId) => {
    setReviews(prev => prev.filter(r => r.id !== reviewId));
  };

  // Handle review update
  const handleUpdate = (updatedReview) => {
    setReviews(prev => prev.map(r => 
      r.id === updatedReview.id ? { ...r, ...updatedReview } : r
    ));
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
      {error && (
        <div className="mt-4 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
          <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
        </div>
      )}
    </div>
  );
};

export default ReviewList;

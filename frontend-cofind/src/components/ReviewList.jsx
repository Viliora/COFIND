import React, { useState, useEffect } from 'react';
import { supabase, isSupabaseConfigured } from '../lib/supabase';
import ReviewCard from './ReviewCard';
import reviewsData from '../data/reviews.json';

const ReviewList = ({ placeId, newReview }) => {
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load reviews
  useEffect(() => {
    const loadReviews = async () => {
      setLoading(true);
      setError(null);

      try {
        let supabaseReviews = [];
        let legacyReviews = [];

        // Load from Supabase if configured
        if (isSupabaseConfigured && supabase) {
          const { data, error: fetchError } = await supabase
            .from('reviews')
            .select(`
              *,
              profiles:user_id (username, avatar_url, full_name),
              photos:review_photos (id, photo_url),
              replies:review_replies (
                id,
                text,
                created_at,
                profiles:user_id (username, avatar_url)
              )
            `)
            .eq('place_id', placeId)
            .order('created_at', { ascending: false });

          if (fetchError) {
            console.error('Error fetching reviews:', fetchError);
          } else if (data) {
            supabaseReviews = data.map(r => ({
              ...r,
              source: 'supabase'
            }));
          }
        }

        // Load from local JSON (legacy reviews)
        const localReviews = reviewsData.reviews_by_place_id?.[placeId] || [];
        legacyReviews = localReviews.map((r, index) => ({
          id: `legacy-${placeId}-${index}`,
          text: r.text,
          rating: r.rating,
          author_name: r.author_name,
          created_at: r.relative_time_description,
          source: 'legacy',
          relative_time: r.relative_time_description
        }));

        // Combine: Supabase reviews first, then legacy
        const allReviews = [...supabaseReviews, ...legacyReviews];
        setReviews(allReviews);

      } catch (err) {
        console.error('Error loading reviews:', err);
        setError('Gagal memuat review');
        
        // Fallback to legacy reviews only
        const localReviews = reviewsData.reviews_by_place_id?.[placeId] || [];
        setReviews(localReviews.map((r, index) => ({
          id: `legacy-${placeId}-${index}`,
          text: r.text,
          rating: r.rating,
          author_name: r.author_name,
          created_at: r.relative_time_description,
          source: 'legacy',
          relative_time: r.relative_time_description
        })));
      } finally {
        setLoading(false);
      }
    };

    loadReviews();
  }, [placeId]);

  // Handle new review added
  useEffect(() => {
    if (newReview) {
      setReviews(prev => [{
        ...newReview,
        source: 'supabase',
        photos: [],
        replies: []
      }, ...prev]);
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

  // Calculate stats
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

  if (loading) {
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

import React, { useState } from 'react';
import { useAuth } from '../context/authContext';
import { supabase } from '../lib/supabase';
import { Link } from 'react-router-dom';

const ReviewForm = ({ placeId, shopName, onReviewSubmitted }) => {
  const { user, isAuthenticated, isSupabaseConfigured } = useAuth();
  const [rating, setRating] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Submit review - FIXED dengan error handling yang lebih baik
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    // Validasi user masih terautentikasi
    if (!user?.id) {
      setError('Sesi Anda telah berakhir. Silakan login kembali.');
      return;
    }

    if (!rating) {
      setError('Silakan beri rating');
      return;
    }

    if (!text.trim()) {
      setError('Silakan tulis review');
      return;
    }

    if (!placeId) {
      setError('ID tempat tidak valid');
      return;
    }

    setLoading(true);

    try {
      console.log(`[ReviewForm] Starting review submission for user ${user.id} at place ${placeId}`);
      
      // Check jumlah reviews user untuk coffee shop ini
      const { count, error: countError } = await supabase
        .from('reviews')
        .select('*', { count: 'exact', head: true })
        .eq('user_id', user.id)
        .eq('place_id', placeId);

      if (countError) {
        console.error('[ReviewForm] Error checking review count:', countError);
        setError('Gagal memeriksa jumlah review. Silakan coba lagi.');
        setLoading(false);
        return;
      }

      console.log(`[ReviewForm] User has ${count || 0} existing reviews for this place`);

      // Check if user sudah mencapai limit 3 reviews
      if (count && count >= 3) {
        setError(`Anda sudah mencapai batas maksimal 3 review untuk ${shopName}. Silakan edit atau hapus review lama jika ingin membuat review baru.`);
        setLoading(false);
        return;
      }

      // Insert review
      console.log('[ReviewForm] Inserting review...');
      const { data: reviewData, error: reviewError } = await supabase
        .from('reviews')
        .insert({
          user_id: user.id,
          place_id: placeId,
          rating,
          text: text.trim()
        })
        .select(`
          id,
          user_id,
          place_id,
          rating,
          text,
          created_at,
          updated_at,
          profiles:user_id (username, avatar_url, full_name)
        `)
        .single();

      if (reviewError) {
        console.error('[ReviewForm] ❌ Error inserting review:', reviewError);
        console.error('[ReviewForm] Error details:', {
          message: reviewError.message,
          code: reviewError.code,
          details: reviewError.details,
          hint: reviewError.hint
        });
        
        if (reviewError.message?.includes('violates row-level security') || reviewError.code === '42501') {
          setError('Anda tidak memiliki izin untuk mengirim review. Pastikan Anda sudah login dan coba lagi.');
        } else if (reviewError.message?.includes('duplicate key') || reviewError.code === '23505') {
          setError('Review ini sudah ada. Silakan refresh halaman.');
        } else if (reviewError.message?.includes('null value') || reviewError.code === '23502') {
          setError('Data review tidak lengkap. Silakan coba lagi.');
        } else {
          setError('Gagal menyimpan review: ' + (reviewError.message || 'Unknown error'));
        }
        setLoading(false);
        return;
      }
      
      if (!reviewData || !reviewData.id) {
        console.error('[ReviewForm] ❌ No review data returned after insert');
        setError('Gagal mendapatkan data review setelah insert. Silakan refresh halaman dan coba lagi.');
        setLoading(false);
        return;
      }

      console.log('[ReviewForm] ✅ Review inserted successfully with ID:', reviewData.id);
      console.log('[ReviewForm] Review data:', reviewData);
      
      // Set success message (tidak akan hilang sampai user clear form)
      setSuccess('Review berhasil dikirim!');
      
      // Callback to parent untuk update UI - PASTIKAN dipanggil
      if (onReviewSubmitted) {
        console.log('[ReviewForm] Calling onReviewSubmitted callback with:', reviewData);
        try {
          onReviewSubmitted({
            ...reviewData,
            source: 'supabase'
          });
          console.log('[ReviewForm] ✅ Callback executed successfully');
        } catch (callbackError) {
          console.error('[ReviewForm] Error in callback:', callbackError);
          // Jangan gagalkan submit jika callback error
        }
      } else {
        console.warn('[ReviewForm] ⚠️ onReviewSubmitted callback not provided');
      }
      
      // Clear form setelah delay kecil (biarkan user lihat success message)
      setTimeout(() => {
        setRating(0);
        setText('');
        // Jangan clear success message - biarkan user lihat
      }, 2000);

    } catch (err) {
      console.error('[ReviewForm] ❌ Submit exception:', err);
      console.error('[ReviewForm] Exception details:', {
        message: err.message,
        stack: err.stack,
        name: err.name
      });
      setError('Terjadi kesalahan saat mengirim review: ' + (err.message || 'Unknown error'));
    } finally {
      setLoading(false);
    }
  };

  // Show nothing if Supabase not configured
  if (!isSupabaseConfigured) {
    return null;
  }

  // Show login prompt if not authenticated
  if (!isAuthenticated) {
    return (
      <div className="bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-900/20 dark:to-orange-900/20 p-6 rounded-xl border border-amber-200 dark:border-amber-800">
        <div className="text-center">
          <div className="w-12 h-12 bg-amber-100 dark:bg-amber-900/30 rounded-full flex items-center justify-center mx-auto mb-3">
            <svg className="w-6 h-6 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
            Ingin memberikan review?
          </h3>
          <p className="text-gray-600 dark:text-gray-400 mb-4">
            Masuk atau daftar untuk menulis review tentang {shopName}
          </p>
          <Link
            to="/login"
            state={{
              from: {
                pathname: `/shop/${placeId}`,
                search: '?scrollToReview=true'
              },
              placeId: placeId,
              shopName: shopName,
              scrollToReview: true
            }}
            className="inline-flex items-center gap-2 px-6 py-3 bg-amber-600 hover:bg-amber-700 text-white font-semibold rounded-lg transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
            </svg>
            Masuk untuk Review
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-zinc-800 p-6 rounded-xl border border-gray-200 dark:border-zinc-700 shadow-sm">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
        <svg className="w-5 h-5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
        </svg>
        Tulis Review
      </h3>

      {/* Messages - Success message tidak akan hilang sampai form di-clear */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
        </div>
      )}
      {success && (
        <div className="mb-4 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
          <p className="text-sm text-green-700 dark:text-green-300 font-medium">{success}</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Rating */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Rating
          </label>
          <div className="flex gap-1">
            {[1, 2, 3, 4, 5].map((star) => (
              <button
                key={star}
                type="button"
                onClick={() => {
                  setRating(star);
                  setSuccess(''); // Clear success saat user ubah rating
                }}
                onMouseEnter={() => setHoverRating(star)}
                onMouseLeave={() => setHoverRating(0)}
                className="p-1 transition-transform hover:scale-110"
              >
                <svg
                  className={`w-8 h-8 ${
                    star <= (hoverRating || rating)
                      ? 'text-amber-500 fill-current'
                      : 'text-gray-400 dark:text-gray-500'
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
              </button>
            ))}
          </div>
        </div>

        {/* Text */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Review
          </label>
          <textarea
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setSuccess(''); // Clear success saat user ketik
            }}
            rows={4}
            className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-zinc-600 bg-white dark:bg-zinc-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-amber-500 focus:border-transparent resize-none"
            placeholder="Bagikan pengalaman Anda di coffee shop ini..."
            required
            minLength={1}
          />
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 px-4 bg-amber-600 hover:bg-amber-700 disabled:bg-amber-400 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
              <span>Mengirim...</span>
            </>
          ) : (
            <>
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
              Kirim Review
            </>
          )}
        </button>
      </form>
    </div>
  );
};

export default ReviewForm;

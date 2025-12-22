import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { supabase } from '../lib/supabase';
import { Link } from 'react-router-dom';

const ReviewForm = ({ placeId, shopName, onReviewSubmitted }) => {
  const { user, isAuthenticated, isSupabaseConfigured } = useAuth();
  const [rating, setRating] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);
  const [text, setText] = useState('');
  const [photos, setPhotos] = useState([]);
  const [photoPreviews, setPhotoPreviews] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const MAX_PHOTOS = 5;
  const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB

  // Handle photo selection
  const handlePhotoChange = (e) => {
    const files = Array.from(e.target.files);
    
    // Check total count
    if (photos.length + files.length > MAX_PHOTOS) {
      setError(`Maksimal ${MAX_PHOTOS} foto`);
      return;
    }

    // Validate each file
    const validFiles = [];
    const previews = [];

    for (const file of files) {
      if (file.size > MAX_FILE_SIZE) {
        setError(`File ${file.name} terlalu besar (maksimal 5MB)`);
        continue;
      }
      if (!file.type.startsWith('image/')) {
        setError(`File ${file.name} bukan gambar`);
        continue;
      }
      validFiles.push(file);
      previews.push(URL.createObjectURL(file));
    }

    setPhotos([...photos, ...validFiles]);
    setPhotoPreviews([...photoPreviews, ...previews]);
    setError('');
  };

  // Remove photo
  const removePhoto = (index) => {
    const newPhotos = photos.filter((_, i) => i !== index);
    const newPreviews = photoPreviews.filter((_, i) => i !== index);
    URL.revokeObjectURL(photoPreviews[index]);
    setPhotos(newPhotos);
    setPhotoPreviews(newPreviews);
  };

  // Upload photos to Supabase Storage
  const uploadPhotos = async (reviewId) => {
    const uploadedUrls = [];

    for (const photo of photos) {
      try {
        const fileExt = photo.name.split('.').pop();
        const fileName = `${reviewId}-${Date.now()}-${Math.random().toString(36).substring(7)}.${fileExt}`;
        // CRITICAL: Path structure must be: reviews/{userId}/{filename}
        // This matches the RLS policy for review photos
        const filePath = `reviews/${user.id}/${fileName}`;

        console.log('[ReviewForm] Uploading photo to:', filePath);

        const { data: uploadData, error: uploadError } = await supabase.storage
          .from('review-photos')
          .upload(filePath, photo, {
            cacheControl: '3600',
            upsert: false
          });

        if (uploadError) {
          console.error('[ReviewForm] Photo upload error:', uploadError);
          continue; // Skip this photo, continue with others
        }

        console.log('[ReviewForm] Photo uploaded successfully:', uploadData);

        const { data: { publicUrl } } = supabase.storage
          .from('review-photos')
          .getPublicUrl(filePath);

        uploadedUrls.push(publicUrl);
      } catch (error) {
        console.error('[ReviewForm] Exception uploading photo:', error);
        continue;
      }
    }

    return uploadedUrls;
  };

  // Submit review
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!rating) {
      setError('Silakan beri rating');
      return;
    }

    if (!text.trim()) {
      setError('Silakan tulis review');
      return;
    }

    setLoading(true);

    try {
      // VALIDATION: Check jumlah reviews user untuk coffee shop ini
      console.log(`[ReviewForm] Checking review count for user ${user.id} at place ${placeId}`);
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

      console.log(`[ReviewForm] User has ${count} existing reviews for this place`);

      // Check if user sudah mencapai limit 3 reviews
      if (count >= 3) {
        setError(`Anda sudah mencapai batas maksimal 3 review untuk ${shopName}. Silakan edit atau hapus review lama jika ingin membuat review baru.`);
        setLoading(false);
        return;
      }

      // OPTIMIZED: Insert review dengan query sederhana (hanya profile, tanpa photos/replies)
      // Photos dan replies akan di-fetch lazy atau via real-time untuk prevent timeout
      const insertStartTime = Date.now();
      
      // Step 1: Insert review dengan minimal select (hanya basic fields + profile)
      const insertPromise = supabase
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
      
      // Add timeout untuk insert query (8 detik - lebih pendek dari fetch query)
      const insertTimeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('Insert review timeout after 8 seconds')), 8000);
      });
      
      const { data: reviewData, error: reviewError } = await Promise.race([
        insertPromise,
        insertTimeoutPromise
      ]);
      
      const insertDuration = Date.now() - insertStartTime;
      console.log(`[ReviewForm] ⚡ Review inserted in ${insertDuration}ms`);

      if (reviewError) {
        console.error('[ReviewForm] ❌ Error inserting review:', reviewError);
        setError('Gagal menyimpan review: ' + reviewError.message);
        setLoading(false);
        return;
      }
      
      // Ensure reviewData has required structure untuk optimistic update
      if (!reviewData) {
        setError('Gagal mendapatkan data review setelah insert');
        setLoading(false);
        return;
      }

      // Upload photos if any (OPTIONAL - tidak wajib)
      let uploadedPhotos = [];
      if (photos.length > 0) {
        try {
          const photoUrls = await uploadPhotos(reviewData.id);

          // Insert photo records
          if (photoUrls.length > 0) {
            const photoRecords = photoUrls.map(url => ({
              review_id: reviewData.id,
              photo_url: url
            }));

            const { data: insertedPhotos, error: photoError } = await supabase
              .from('review_photos')
              .insert(photoRecords)
              .select('id, review_id, photo_url');
            
            if (photoError) {
              console.error('[ReviewForm] Error inserting photo records:', photoError);
              // Don't fail the whole review submission if photos fail
            } else if (insertedPhotos) {
              uploadedPhotos = insertedPhotos;
              console.log(`[ReviewForm] ✅ ${insertedPhotos.length} photos uploaded and saved`);
            }
          }
        } catch (photoErr) {
          console.error('[ReviewForm] Error uploading photos:', photoErr);
          // Don't fail the whole review submission if photos fail
        }
      }

      setSuccess('Review berhasil dikirim!');
      
      // Prepare review data untuk optimistic update
      // Include photos yang sudah di-upload
      const reviewDataForCallback = {
        ...reviewData,
        photos: uploadedPhotos, // Include uploaded photos
        replies: [], // Empty - akan di-fetch via real-time atau refetch
        source: 'supabase'
      };
      
      // Callback to parent IMMEDIATELY untuk optimistic UI update
      // This ensures instant feedback tanpa menunggu fetch
      if (onReviewSubmitted) {
        console.log('[ReviewForm] ✅ Review submitted, calling onReviewSubmitted callback immediately');
        onReviewSubmitted(reviewDataForCallback);
      }
      
      // Clear form after callback (slight delay untuk smooth UX)
      setTimeout(() => {
        setRating(0);
        setText('');
        setPhotos([]);
        setPhotoPreviews.forEach(url => URL.revokeObjectURL(url));
        setPhotoPreviews([]);
      }, 100);

    } catch (err) {
      setError('Terjadi kesalahan. Silakan coba lagi.');
    } finally {
      setLoading(false);
    }
  };

  // Show login prompt if not authenticated
  if (!isSupabaseConfigured) {
    return null;
  }

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

      {/* Messages */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
        </div>
      )}
      {success && (
        <div className="mb-4 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
          <p className="text-sm text-green-700 dark:text-green-300">{success}</p>
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
                onClick={() => setRating(star)}
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
            onChange={(e) => setText(e.target.value)}
            rows={4}
            className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-zinc-600 bg-white dark:bg-zinc-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-amber-500 focus:border-transparent resize-none"
            placeholder="Bagikan pengalaman Anda di coffee shop ini..."
            required
            minLength={1}
          />
        </div>

        {/* Photo Upload */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Foto (Opsional, maks {MAX_PHOTOS})
          </label>
          
          {/* Photo Previews */}
          {photoPreviews.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {photoPreviews.map((preview, index) => (
                <div key={index} className="relative">
                  <img
                    src={preview}
                    alt={`Preview ${index + 1}`}
                    className="w-20 h-20 object-cover rounded-lg border border-gray-200 dark:border-zinc-600"
                  />
                  <button
                    type="button"
                    onClick={() => removePhoto(index)}
                    className="absolute -top-2 -right-2 w-6 h-6 bg-red-500 text-white rounded-full flex items-center justify-center hover:bg-red-600 transition-colors"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Upload Button */}
          {photos.length < MAX_PHOTOS && (
            <label className="flex items-center justify-center gap-2 px-4 py-3 border-2 border-dashed border-gray-300 dark:border-zinc-600 rounded-lg cursor-pointer hover:border-amber-500 dark:hover:border-amber-500 transition-colors">
              <svg className="w-5 h-5 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <span className="text-sm text-gray-600 dark:text-gray-400">
                Tambah Foto
              </span>
              <input
                type="file"
                accept="image/*"
                multiple
                onChange={handlePhotoChange}
                className="hidden"
              />
            </label>
          )}
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

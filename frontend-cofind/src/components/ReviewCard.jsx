import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { supabase } from '../lib/supabase';

const ReviewCard = ({ review, onDelete, onUpdate, showSourceBadge = false }) => {
  const { user, isAuthenticated } = useAuth();
  const [showPhotos, setShowPhotos] = useState(false);
  const [selectedPhoto, setSelectedPhoto] = useState(null);
  const [showReportModal, setShowReportModal] = useState(false);
  const [reportReason, setReportReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(review.text || '');
  const [editRating, setEditRating] = useState(review.rating || 0);
  const [editError, setEditError] = useState('');
  const [success, setSuccess] = useState('');

  const isOwner = user?.id === review.user_id;
  const timeAgo = getTimeAgo(review.created_at, review.relative_time);
  
  // Debug logging untuk photos
  useEffect(() => {
    if (review.photos && review.photos.length > 0) {
      console.log(`[ReviewCard] Review ${review.id} has ${review.photos.length} photos:`, review.photos);
    }
  }, [review.id, review.photos]);

  // Handle edit click - reset state saat mulai edit
  const handleEditClick = () => {
    setEditText(review.text || '');
    setEditRating(review.rating || 0);
    setEditError('');
    setIsEditing(true);
  };

  // Format time ago
  function getTimeAgo(dateString, relativeTime) {
    // If legacy review has relative_time, use it directly
    if (relativeTime && typeof relativeTime === 'string') {
      return relativeTime;
    }
    
    // Try to parse date string
    if (!dateString) return 'Tidak diketahui';
    
    const date = new Date(dateString);
    
    // Check if date is valid
    if (isNaN(date.getTime())) {
      // If invalid date, try to use relative_time if available
      if (relativeTime) return relativeTime;
      return 'Tidak diketahui';
    }
    
    const now = new Date();
    const diffInSeconds = Math.floor((now - date) / 1000);

    if (diffInSeconds < 60) return 'Baru saja';
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)} menit lalu`;
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)} jam lalu`;
    if (diffInSeconds < 604800) return `${Math.floor(diffInSeconds / 86400)} hari lalu`;
    if (diffInSeconds < 2592000) return `${Math.floor(diffInSeconds / 604800)} minggu lalu`;
    return date.toLocaleDateString('id-ID', { year: 'numeric', month: 'long', day: 'numeric' });
  }

  // Handle edit submit
  const handleEditSubmit = async () => {
    if (!editText.trim()) {
      alert('Review tidak boleh kosong');
      return;
    }
    
    setLoading(true);

    try {
      const editStartTime = Date.now();
      
      // OPTIMIZED: Update review dengan timeout handling
      const updatePromise = supabase
        .from('reviews')
        .update({ 
          text: editText.trim(), 
          rating: editRating, 
          updated_at: new Date().toISOString() 
        })
        .eq('id', review.id)
        .select(`
          id,
          user_id,
          place_id,
          rating,
          text,
          created_at,
          updated_at
        `)
        .single();
      
      // Add timeout untuk update query (8 detik)
      const updateTimeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('Update review timeout after 8 seconds')), 8000);
      });
      
      const { data: updatedReview, error } = await Promise.race([
        updatePromise,
        updateTimeoutPromise
      ]);
      
      const editDuration = Date.now() - editStartTime;
      console.log(`[ReviewCard] ⚡ Review updated in ${editDuration}ms`);

      if (error) {
        console.error('[ReviewCard] ❌ Error updating review:', error);
        const errorMessage = error.message || 'Unknown error';
        if (errorMessage.includes('timeout')) {
          alert('Timeout saat menyimpan perubahan. Silakan coba lagi.');
        } else {
          alert('Gagal menyimpan perubahan: ' + errorMessage);
        }
        setLoading(false);
        return;
      }

      if (updatedReview) {
        // Fetch profile data untuk updated review (dengan timeout)
        let profileData = review.profiles; // Keep existing profile data
        
        if (updatedReview.user_id) {
          try {
            const profilePromise = supabase
              .from('profiles')
              .select('id, username, avatar_url, full_name')
              .eq('id', updatedReview.user_id)
              .single();
            
            const profileTimeoutPromise = new Promise((_, reject) => {
              setTimeout(() => reject(new Error('Profile fetch timeout')), 5000);
            });
            
            const { data: profile } = await Promise.race([
              profilePromise,
              profileTimeoutPromise
            ]);
            
            if (profile) {
              profileData = profile;
            }
          } catch (profileError) {
            console.warn('[ReviewCard] ⚠️ Error fetching profile (non-critical):', profileError?.message || profileError);
            // Keep existing profile data if fetch fails
          }
        }

        // Prepare updated review dengan semua data yang diperlukan
        const finalUpdatedReview = {
          ...review, // Keep existing data (photos, replies, etc.)
          ...updatedReview, // Override with updated data
          profiles: profileData,
          author_name: profileData?.username || profileData?.full_name || 'Anonim',
          source: review.source || 'supabase'
        };

        // Update local state
        setIsEditing(false);
        
        // Call onUpdate dengan data lengkap untuk update state di parent
        if (onUpdate) {
          onUpdate(finalUpdatedReview);
          console.log('[ReviewCard] Review updated successfully:', finalUpdatedReview.id);
        }

        // Show success message
        setSuccess('Review berhasil diperbarui!');
        console.log('[ReviewCard] Review updated in database:', finalUpdatedReview.id);
        
        // CRITICAL: Don't reload page - use optimistic update instead
        // onUpdate callback will trigger refresh in ReviewList
        // This is much faster and provides better UX
        console.log('[ReviewCard] Review updated - triggering refresh via onUpdate callback');
      }
    } catch (err) {
      console.error('[ReviewCard] Exception updating review:', err);
      const errorMessage = err.message || 'Unknown error';
      setEditError('Gagal menyimpan perubahan: ' + errorMessage);
    } finally {
      setLoading(false);
    }
  };

  // Handle delete
  const handleDelete = async () => {
    if (!confirm('Apakah Anda yakin ingin menghapus review ini?')) return;
    setLoading(true);

    try {
      const { error } = await supabase
        .from('reviews')
        .delete()
        .eq('id', review.id);

      if (!error && onDelete) {
        onDelete(review.id);
      }
    } catch (err) {
      console.error('Delete error:', err);
    } finally {
      setLoading(false);
    }
  };


  // Handle report submit
  const handleReportSubmit = async () => {
    if (!reportReason.trim() || !supabase) return;
    setLoading(true);

    try {
      const { error } = await supabase
        .from('review_reports')
        .insert({
          review_id: review.id,
          reporter_id: user.id,
          reason: reportReason.trim()
        });

      if (!error) {
        setReportReason('');
        setShowReportModal(false);
        alert('Laporan terkirim. Terima kasih!');
      }
    } catch (err) {
      console.error('Report error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white dark:bg-zinc-800 rounded-xl border border-gray-200 dark:border-zinc-700 p-4 sm:p-5">
      {/* Header */}
      <div className="flex items-start gap-3 mb-3">
        {/* Avatar */}
        <div className="w-10 h-10 rounded-full overflow-hidden bg-gray-200 dark:bg-zinc-700 flex-shrink-0">
          {review.profiles?.avatar_url ? (
            <img 
              src={review.profiles.avatar_url} 
              alt={review.profiles.username} 
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center bg-gradient-to-r from-amber-500 to-orange-500 text-white font-semibold">
              {review.profiles?.username?.[0]?.toUpperCase() || review.author_name?.[0]?.toUpperCase() || 'U'}
            </div>
          )}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <div className="flex items-center gap-2 flex-wrap">
              <h4 className="font-semibold text-gray-900 dark:text-white truncate">
                {review.profiles?.username || review.author_name || 'Anonim'}
              </h4>
              {showSourceBadge && review.source && (
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium flex-shrink-0 ${
                  review.source === 'legacy'
                    ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                    : 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                }`}>
                  {review.source === 'legacy' ? 'Google Review' : 'Review Pengguna'}
                </span>
              )}
            </div>
            <span className="text-xs text-gray-500 dark:text-gray-400 flex-shrink-0">
              {timeAgo}
            </span>
          </div>
          
          {/* Rating */}
          <div className="flex items-center gap-1 mt-1">
            {[1, 2, 3, 4, 5].map((star) => (
              <svg
                key={star}
                className={`w-4 h-4 ${
                  star <= (isEditing ? editRating : review.rating)
                    ? 'text-amber-500 fill-current'
                    : 'text-gray-400 dark:text-gray-500'
                } ${isEditing ? 'cursor-pointer' : ''}`}
                onClick={() => isEditing && setEditRating(star)}
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
        </div>
      </div>

      {/* Review Text */}
      {isEditing ? (
        <div className="mb-3">
          <textarea
            value={editText}
            onChange={(e) => {
              setEditText(e.target.value);
              setEditError(''); // Clear error saat user mengetik
            }}
            rows={3}
            className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-zinc-600 bg-white dark:bg-zinc-700 text-gray-900 dark:text-white text-sm resize-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
            placeholder="Tulis review Anda..."
          />
          {editError && (
            <p className="text-sm text-red-600 dark:text-red-400 mt-1">{editError}</p>
          )}
          {success && (
            <p className="text-sm text-green-600 dark:text-green-400 mt-1">{success}</p>
          )}
          <div className="flex gap-2 mt-2">
            <button
              onClick={handleEditSubmit}
              disabled={loading || !editText.trim()}
              className="px-3 py-1.5 bg-amber-600 text-white text-sm rounded-lg hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Menyimpan...' : 'Simpan'}
            </button>
            <button
              onClick={() => {
                setIsEditing(false);
                setEditText(review.text || '');
                setEditRating(review.rating || 0);
                setEditError('');
              }}
              disabled={loading}
              className="px-3 py-1.5 border border-gray-300 dark:border-zinc-600 text-gray-700 dark:text-gray-300 text-sm rounded-lg hover:bg-gray-50 dark:hover:bg-zinc-700 disabled:opacity-50"
            >
              Batal
            </button>
          </div>
        </div>
      ) : (
        <p className="text-gray-700 dark:text-gray-300 text-sm leading-relaxed mb-3">
          {review.text}
        </p>
      )}

      {/* Photos - CRITICAL: Always show if photos exist */}
      {review.photos && Array.isArray(review.photos) && review.photos.length > 0 && (
        <div className="mb-3">
          <div className="flex flex-wrap gap-2">
            {review.photos.slice(0, showPhotos ? undefined : 3).map((photo, index) => {
              // Handle both object format {id, photo_url} and string format
              const photoUrl = typeof photo === 'string' ? photo : (photo?.photo_url || photo?.url);
              const photoId = photo?.id || index;
              
              if (!photoUrl) {
                console.warn('[ReviewCard] Photo missing URL:', photo);
                return null;
              }
              
              return (
                <button
                  key={photoId}
                  onClick={() => setSelectedPhoto(photoUrl)}
                  className="relative group"
                >
                  <img
                    src={photoUrl}
                    alt={`Review photo ${index + 1}`}
                    className="w-20 h-20 object-cover rounded-lg border border-gray-200 dark:border-zinc-600 hover:opacity-90 transition-opacity cursor-pointer"
                    onError={(e) => {
                      console.error('[ReviewCard] Failed to load photo:', photoUrl);
                      e.target.style.display = 'none';
                    }}
                  />
                  <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-10 rounded-lg transition-opacity" />
                </button>
              );
            })}
            {!showPhotos && review.photos.length > 3 && (
              <button
                onClick={() => setShowPhotos(true)}
                className="w-20 h-20 rounded-lg bg-gray-100 dark:bg-zinc-700 flex items-center justify-center text-sm font-semibold text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-zinc-600 transition-colors"
              >
                +{review.photos.length - 3}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between border-t border-gray-200 dark:border-zinc-600 pt-3">
        <div className="flex items-center gap-3">
          {isAuthenticated && !isOwner && (
            <button
              onClick={() => setShowReportModal(true)}
              className="text-sm text-gray-600 dark:text-gray-400 hover:text-red-600 dark:hover:text-red-500 flex items-center gap-1"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              Laporkan
            </button>
          )}
        </div>

        {/* Owner Actions - Hanya tampil jika user authenticated DAN adalah owner */}
        {isAuthenticated && isOwner && !isEditing && (
          <div className="flex items-center gap-2">
            <button
              onClick={handleEditClick}
              className="text-sm text-gray-600 dark:text-gray-400 hover:text-amber-600 dark:hover:text-amber-500 flex items-center gap-1"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              Edit
            </button>
            <button
              onClick={handleDelete}
              disabled={loading}
              className="text-sm text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 flex items-center gap-1"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              Hapus
            </button>
          </div>
        )}
      </div>


      {/* Report Modal */}
      {showReportModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-zinc-800 rounded-xl p-6 max-w-md w-full">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Laporkan Review
            </h3>
            <textarea
              value={reportReason}
              onChange={(e) => setReportReason(e.target.value)}
              rows={3}
              placeholder="Jelaskan alasan pelaporan..."
              className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-zinc-600 bg-white dark:bg-zinc-700 text-gray-900 dark:text-white text-sm resize-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
            />
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => {
                  setShowReportModal(false);
                  setReportReason('');
                }}
                className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
              >
                Batal
              </button>
              <button
                onClick={handleReportSubmit}
                disabled={loading || !reportReason.trim()}
                className="px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700 disabled:opacity-50"
              >
                Kirim Laporan
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Photo Lightbox */}
      {selectedPhoto && (
        <div 
          className="fixed inset-0 bg-black/90 flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedPhoto(null)}
        >
          <button
            className="absolute top-4 right-4 text-white hover:text-gray-300"
            onClick={() => setSelectedPhoto(null)}
          >
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
          <img
            src={selectedPhoto}
            alt="Full size"
            className="max-w-full max-h-full object-contain"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
};

export default ReviewCard;

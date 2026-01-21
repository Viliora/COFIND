import React, { useState } from 'react';
import { useAuth } from '../context/authContext';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';

const ReviewCard = ({ review, onDelete, onUpdate }) => {
  const { user, isAuthenticated } = useAuth();
  const [loading, setLoading] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(review.text || '');
  const [editRating, setEditRating] = useState(review.rating || 0);
  const [editError, setEditError] = useState('');
  const [success, setSuccess] = useState('');

  const isOwner = user?.id === review.user_id;
  const timeAgo = getTimeAgo(review.created_at, review.relative_time);

  // Handle edit click
  const handleEditClick = () => {
    setEditText(review.text || '');
    setEditRating(review.rating || 0);
    setEditError('');
    setSuccess('');
    setIsEditing(true);
  };

  // Format time ago
  function getTimeAgo(dateString, relativeTime) {
    if (relativeTime && typeof relativeTime === 'string') {
      return relativeTime;
    }
    
    if (!dateString) return 'Tidak diketahui';
    
    const date = new Date(dateString);
    
    if (isNaN(date.getTime())) {
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

  // Handle edit submit - FIXED: Better error handling dan callback
  const handleEditSubmit = async () => {
    if (!editText.trim()) {
      setEditError('Review tidak boleh kosong');
      return;
    }
    
    if (!user?.id) {
      setEditError('Sesi Anda telah berakhir. Silakan login kembali.');
      return;
    }
    
    setLoading(true);
    setEditError('');
    setSuccess('');

    try {
      console.log('[ReviewCard] Updating review:', review.id);
      
      const response = await fetch(`${API_BASE}/api/reviews/${review.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: user.id,
          text: editText.trim(),
          rating: editRating,
        })
      });

      const payload = await response.json();
      if (!response.ok || payload.status !== 'success') {
        setEditError('Gagal menyimpan perubahan: ' + (payload.message || 'Unknown error'));
        setLoading(false);
        return;
      }

      const updatedReview = payload.review;
      if (!updatedReview || !updatedReview.id) {
        setEditError('Gagal mendapatkan data review setelah update.');
        setLoading(false);
        return;
      }

      console.log('[ReviewCard] ✅ Review updated successfully:', updatedReview.id);
      
      setIsEditing(false);
      setSuccess('Review berhasil diperbarui!');
      
      // Callback to parent dengan data lengkap
      if (onUpdate) {
        try {
          onUpdate({
            ...review,
            ...updatedReview,
            profiles: review.profiles
          });
          console.log('[ReviewCard] ✅ onUpdate callback executed');
        } catch (callbackError) {
          console.error('[ReviewCard] Error in onUpdate callback:', callbackError);
        }
      }
      
      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(''), 3000);
      
    } catch (err) {
      console.error('[ReviewCard] ❌ Exception updating review:', err);
      setEditError('Gagal menyimpan perubahan: ' + (err.message || 'Unknown error'));
    } finally {
      setLoading(false);
    }
  };

  // Handle delete - FIXED: Better error handling dan callback
  const handleDelete = async () => {
    if (!confirm('Apakah Anda yakin ingin menghapus review ini?')) return;
    
    if (!user?.id) {
      alert('Sesi Anda telah berakhir. Silakan login kembali.');
      return;
    }
    
    setLoading(true);

    try {
      console.log('[ReviewCard] Deleting review:', review.id);
      
      const response = await fetch(`${API_BASE}/api/reviews/${review.id}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: user.id })
      });

      const payload = await response.json();
      if (!response.ok || payload.status !== 'success') {
        alert('Gagal menghapus review: ' + (payload.message || 'Unknown error'));
        setLoading(false);
        return;
      }

      console.log('[ReviewCard] ✅ Review deleted successfully');
      
      // Callback to parent - PASTIKAN dipanggil
      if (onDelete) {
        try {
          onDelete(review.id);
          console.log('[ReviewCard] ✅ onDelete callback executed');
        } catch (callbackError) {
          console.error('[ReviewCard] Error in onDelete callback:', callbackError);
        }
      }
      
    } catch (err) {
      console.error('[ReviewCard] ❌ Delete exception:', err);
      alert('Terjadi kesalahan saat menghapus review: ' + (err.message || 'Unknown error'));
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
            <h4 className="font-semibold text-gray-900 dark:text-white truncate">
              {review.profiles?.username || review.author_name || 'Anonim'}
            </h4>
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
                } ${isEditing ? 'cursor-pointer hover:scale-110 transition-transform' : ''}`}
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
              setEditError('');
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
                setSuccess('');
              }}
              disabled={loading}
              className="px-3 py-1.5 border border-gray-300 dark:border-zinc-600 text-gray-700 dark:text-gray-300 text-sm rounded-lg hover:bg-gray-50 dark:hover:bg-zinc-700 disabled:opacity-50"
            >
              Batal
            </button>
          </div>
        </div>
      ) : (
        <>
          <p className="text-gray-700 dark:text-gray-300 text-sm leading-relaxed mb-3">
            {review.text}
          </p>
          {success && (
            <p className="text-sm text-green-600 dark:text-green-400 mb-3">{success}</p>
          )}
        </>
      )}

      {/* Actions */}
      {isAuthenticated && isOwner && !isEditing && (
        <div className="flex items-center justify-end gap-2 pt-3 border-t border-gray-200 dark:border-zinc-600">
          <button
            onClick={handleEditClick}
            disabled={loading}
            className="text-sm text-gray-600 dark:text-gray-400 hover:text-amber-600 dark:hover:text-amber-500 flex items-center gap-1 disabled:opacity-50"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
            Edit
          </button>
          <button
            onClick={handleDelete}
            disabled={loading}
            className="text-sm text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 flex items-center gap-1 disabled:opacity-50"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-red-600"></div>
                <span>Menghapus...</span>
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
                Hapus
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
};

export default ReviewCard;

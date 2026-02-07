import React, { useState } from 'react';
import { useAuth } from '../context/authContext';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';

const ReviewCard = ({ review, onDelete, onUpdate, onLike }) => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(review.text || '');
  const [editRating, setEditRating] = useState(review.rating || 0);
  const [editError, setEditError] = useState('');
  const [success, setSuccess] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const [showReportConfirm, setShowReportConfirm] = useState(false);
  const [photoModal, setPhotoModal] = useState(null);
  const [likeCount, setLikeCount] = useState(review.like_count ?? 0);
  const [userHasLiked, setUserHasLiked] = useState(review.user_has_liked ?? false);
  const [likeLoading, setLikeLoading] = useState(false);

  React.useEffect(() => {
    if (review.like_count !== undefined) setLikeCount(review.like_count);
    if (review.user_has_liked !== undefined) setUserHasLiked(review.user_has_liked);
  }, [review.like_count, review.user_has_liked]);

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

  // Format time ago: hari ini, kemarin, X hari lalu, lalu minggu/bulan
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
    const diffDays = Math.floor(diffInSeconds / 86400);
    const sameDay = now.getDate() === date.getDate() && now.getMonth() === date.getMonth() && now.getFullYear() === date.getFullYear();
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    const isYesterday = date.getDate() === yesterday.getDate() && date.getMonth() === yesterday.getMonth() && date.getFullYear() === yesterday.getFullYear();

    if (diffInSeconds < 60) return 'Baru saja';
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)} menit lalu`;
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)} jam lalu`;
    if (sameDay) return 'Hari ini';
    if (isYesterday) return 'Kemarin';
    if (diffDays >= 2 && diffDays < 7) return `${diffDays} hari lalu`;
    if (diffDays < 14) return `${Math.floor(diffDays / 7)} minggu lalu`;
    if (diffDays < 60) return `${Math.floor(diffDays / 7)} minggu lalu`;
    return date.toLocaleDateString('id-ID', { year: 'numeric', month: 'long', day: 'numeric' });
  }

  const isNewReview = () => {
    if (!review.created_at) return false;
    const date = new Date(review.created_at);
    const now = new Date();
    const diffDays = Math.floor((now - date) / 86400000);
    return diffDays <= 7;
  };

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

  const displayName = review.profiles?.full_name || review.profiles?.username || review.full_name || review.username || review.author_name || 'Anonim';
  const totalUlasan = review.user_total_reviews != null ? review.user_total_reviews : 0;

  const handleLikeClick = async () => {
    if (!user?.id || isOwner || likeLoading) return;
    setLikeLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/reviews/${review.id}/like`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: user.id })
      });
      const data = await response.json();
      if (data.status === 'success') {
        setLikeCount(data.like_count);
        setUserHasLiked(data.liked);
        if (onLike) onLike(review.id, { like_count: data.like_count, user_has_liked: data.liked });
      }
    } catch {
      // ignore
    } finally {
      setLikeLoading(false);
    }
  };

  return (
    <div className="bg-white dark:bg-zinc-800 rounded-xl border border-gray-200 dark:border-zinc-700 p-4 sm:p-5 relative">
      {/* Header: Foto profil, nama, total ulasan, kebab menu */}
      <div className="flex items-start gap-3 mb-3">
        {/* Avatar dengan border */}
        <div className="w-10 h-10 rounded-full overflow-hidden bg-gray-200 dark:bg-zinc-700 flex-shrink-0 ring-2 ring-amber-400/50 dark:ring-amber-500/50">
          {review.profiles?.avatar_url ? (
            <img
              src={review.profiles.avatar_url}
              alt={displayName}
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center bg-gradient-to-r from-amber-500 to-orange-500 text-white font-semibold text-sm">
              {displayName.toString().charAt(0).toUpperCase()}
            </div>
          )}
        </div>

        <div className="flex-1 min-w-0">
          <h4 className="font-bold text-gray-900 dark:text-white truncate">
            {displayName}
          </h4>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            {totalUlasan > 0 ? `${totalUlasan} ulasan` : 'Pengguna'}
          </p>
        </div>

        {/* Kebab menu (titik tiga) */}
        <div className="relative flex-shrink-0">
          <button
            type="button"
            onClick={() => setMenuOpen((o) => !o)}
            className="p-1.5 rounded-full hover:bg-gray-100 dark:hover:bg-zinc-700 text-gray-500 dark:text-gray-400"
            aria-label="Menu"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <circle cx="12" cy="5" r="1.5" />
              <circle cx="12" cy="12" r="1.5" />
              <circle cx="12" cy="19" r="1.5" />
            </svg>
          </button>
          {menuOpen && (
            <>
              <div className="fixed inset-0 z-10" aria-hidden="true" onClick={() => setMenuOpen(false)} />
              <div className="absolute right-0 top-full mt-1 py-1 w-48 bg-white dark:bg-zinc-700 rounded-lg shadow-lg border border-gray-200 dark:border-zinc-600 z-20">
                {isOwner && (
                  <>
                    <button
                      type="button"
                      onClick={() => { setMenuOpen(false); handleEditClick(); }}
                      className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-zinc-600"
                    >
                      Edit ulasan
                    </button>
                    <button
                      type="button"
                      onClick={() => { setMenuOpen(false); handleDelete(); }}
                      className="w-full px-4 py-2 text-left text-sm text-red-600 dark:text-red-400 hover:bg-gray-100 dark:hover:bg-zinc-600"
                    >
                      Hapus ulasan
                    </button>
                  </>
                )}
                {!isOwner && (
                  <button
                    type="button"
                    onClick={() => { setMenuOpen(false); setShowReportConfirm(true); }}
                    className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-zinc-600"
                  >
                    Laporkan ulasan
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Rating + kapan diupload + badge BARU */}
      <div className="flex items-center gap-2 flex-wrap mb-3">
        <div className="flex items-center gap-0.5">
          {[1, 2, 3, 4, 5].map((star) => (
            <svg
              key={star}
              className={`w-4 h-4 ${
                star <= (isEditing ? editRating : review.rating)
                  ? 'text-amber-500 fill-amber-500'
                  : 'text-gray-300 dark:text-gray-600'
              } ${isEditing ? 'cursor-pointer hover:scale-110 transition-transform' : ''}`}
              onClick={() => isEditing && setEditRating(star)}
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
            </svg>
          ))}
        </div>
        <span className="text-xs text-gray-500 dark:text-gray-400">{timeAgo}</span>
        {isNewReview() && (
          <span className="px-2 py-0.5 text-xs font-medium rounded bg-gray-200 dark:bg-zinc-600 text-gray-700 dark:text-gray-300">
            BARU
          </span>
        )}
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
          {review.photos && review.photos.filter((p) => p.image_data).length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {review.photos.filter((p) => p.image_data).map((photo) => (
                <div key={photo.id} className="flex flex-col">
                  <button
                    type="button"
                    onClick={() => setPhotoModal(photo)}
                    className="relative w-20 h-20 sm:w-24 sm:h-24 rounded-lg border-2 border-gray-200 dark:border-zinc-600 overflow-hidden cursor-pointer focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 transition-all duration-200 hover:scale-105 hover:border-amber-400 dark:hover:border-amber-500 hover:shadow-lg group"
                  >
                    <img
                      src={photo.image_data}
                      alt={photo.caption || 'Foto review'}
                      className="w-full h-full object-cover transition-transform duration-200 group-hover:scale-105"
                    />
                    <span className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors duration-200 pointer-events-none" aria-hidden />
                  </button>
                  {photo.caption && (
                    <span className="text-xs text-gray-500 dark:text-gray-400 mt-1 max-w-[96px] truncate" title={photo.caption}>
                      {photo.caption}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Modal foto review - tampil saat foto diklik */}
          {photoModal && (
            <>
              <div
                className="fixed inset-0 bg-black/70 z-[100]"
                aria-hidden="true"
                onClick={() => setPhotoModal(null)}
              />
              <div
                className="fixed inset-0 z-[101] flex items-center justify-center p-4"
                role="dialog"
                aria-modal="true"
                aria-label="Tampilan foto review"
              >
                <div className="relative max-w-4xl max-h-[90vh] w-full flex flex-col items-center" onClick={(e) => e.stopPropagation()}>
                  <button
                    type="button"
                    onClick={() => setPhotoModal(null)}
                    className="absolute -top-2 -right-2 sm:right-0 sm:top-0 z-10 p-2 rounded-full bg-white dark:bg-zinc-800 shadow-lg text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-zinc-700 transition-colors"
                    aria-label="Tutup"
                  >
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                  <img
                    src={photoModal.image_data}
                    alt={photoModal.caption || 'Foto review'}
                    className="max-w-full max-h-[85vh] w-auto h-auto object-contain rounded-lg shadow-2xl"
                  />
                  {photoModal.caption && (
                    <p className="mt-3 text-sm text-gray-200 dark:text-gray-300 text-center max-w-lg">
                      {photoModal.caption}
                    </p>
                  )}
                </div>
              </div>
            </>
          )}
          {success && (
            <p className="text-sm text-green-600 dark:text-green-400 mb-3">{success}</p>
          )}
        </>
      )}

      {/* Rating Makanan, Layanan, Suasana */}
      {(review.rating_makanan != null || review.rating_layanan != null || review.rating_suasana != null) && !isEditing && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-600 dark:text-gray-400 pt-2 border-t border-gray-100 dark:border-zinc-700">
          {review.rating_makanan != null && (
            <span>Makanan: <span className="font-medium text-gray-800 dark:text-gray-200">{review.rating_makanan}</span></span>
          )}
          {review.rating_layanan != null && (
            <span>Layanan: <span className="font-medium text-gray-800 dark:text-gray-200">{review.rating_layanan}</span></span>
          )}
          {review.rating_suasana != null && (
            <span>Suasana: <span className="font-medium text-gray-800 dark:text-gray-200">{review.rating_suasana}</span></span>
          )}
        </div>
      )}

      {/* Like button - hanya untuk review orang lain */}
      {!isOwner && !isEditing && (
        <div className="pt-3 flex items-center">
          <button
            type="button"
            onClick={handleLikeClick}
            disabled={likeLoading || !user?.id}
            className="inline-flex items-center gap-1.5 px-2 py-1.5 rounded-lg bg-transparent hover:bg-gray-100 dark:hover:bg-zinc-700/50 text-gray-600 dark:text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors disabled:opacity-50"
            aria-label={userHasLiked ? 'Batalkan like' : 'Suka'}
          >
            {userHasLiked ? (
              <svg className="w-5 h-5 text-red-500 fill-red-500" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
              </svg>
            ) : (
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
              </svg>
            )}
            <span className="text-sm font-medium">{likeCount}</span>
          </button>
        </div>
      )}

      {/* Modal konfirmasi laporkan ulasan */}
      {showReportConfirm && (
        <>
          <div className="fixed inset-0 bg-black/50 z-[100]" aria-hidden="true" onClick={() => setShowReportConfirm(false)} />
          <div className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[min(90vw,360px)] bg-white dark:bg-zinc-800 rounded-xl shadow-xl p-5 z-[101]" role="dialog" aria-labelledby="report-title">
            <h3 id="report-title" className="font-semibold text-gray-900 dark:text-white mb-2">Laporkan ulasan?</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Apakah Anda yakin ingin melaporkan ulasan ini? Tim kami akan meninjau laporan Anda.
            </p>
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => setShowReportConfirm(false)}
                className="px-4 py-2 rounded-lg border border-gray-300 dark:border-zinc-600 text-gray-700 dark:text-gray-300 text-sm font-medium hover:bg-gray-50 dark:hover:bg-zinc-700"
              >
                Batal
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowReportConfirm(false);
                  // TODO: panggil API laporkan ulasan jika ada
                  alert('Terima kasih. Laporan Anda telah dikirim.');
                }}
                className="px-4 py-2 rounded-lg bg-amber-600 text-white text-sm font-medium hover:bg-amber-700"
              >
                Laporkan
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default ReviewCard;

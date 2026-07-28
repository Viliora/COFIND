import React, { useState, useRef, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/authContext';
import { authService } from '../services/authService';
import { RATING_META } from './ShopVotesSummary';
import { BEST_FOR_META, SLIDER_META } from './ShopVoteModal';
import { SLIDER_LABELS_MAP } from './ShopOverallExperience';

const OVERALL_SLIDER_FIELDS = ['pelayanan', 'kebersihan', 'kenyamanan', 'harga'];

/** Override keterangan label khusus review card agar lebih jelas (misal untuk pelayanan). */
const REVIEW_CARD_SLIDER_LABELS_MAP = {
  ...SLIDER_LABELS_MAP,
  pelayanan: ['Terrible Service', 'Bad Service', 'Nice Service', 'Great Service', 'Special Service'],
};

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';
const MAX_PHOTOS = 1;
const MAX_REVIEW_IMAGE_BYTES = 2 * 1024 * 1024;

/** Foto yang boleh ditampilkan/diedit per review (maksimal MAX_PHOTOS). */
function sliceReviewPhotos(photos) {
  return (photos || []).filter((p) => p.image_data).slice(0, MAX_PHOTOS);
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

const RATING_BADGE_CLASSES = {
  love: 'bg-rose-100 text-rose-600 dark:bg-rose-900/30 dark:text-rose-300',
  like: 'bg-pink-100 text-pink-600 dark:bg-pink-900/30 dark:text-pink-300',
  ok: 'bg-orange-100 text-orange-600 dark:bg-orange-900/30 dark:text-orange-300',
  dislike: 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-300',
  hate: 'bg-slate-100 text-slate-600 dark:bg-slate-800/40 dark:text-slate-300',
};

const ReviewCard = ({ review, placeId, onDelete, onUpdate, onLike, highlightKeyword = '' }) => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [reviewerVote, setReviewerVote] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(review.text || '');
  const [editRating, setEditRating] = useState(review.rating || 0);
  const [editPhotos, setEditPhotos] = useState(() =>
    sliceReviewPhotos(review.photos).map((p) => ({ id: p.id, image_data: p.image_data }))
  );
  const [editError, setEditError] = useState('');
  const [success, setSuccess] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const [showReportConfirm, setShowReportConfirm] = useState(false);
  const [reportSubmitting, setReportSubmitting] = useState(false);
  const [reportFeedback, setReportFeedback] = useState(null);
  const [photoModal, setPhotoModal] = useState(null);
  const [likeCount, setLikeCount] = useState(review.like_count ?? 0);
  const [userHasLiked, setUserHasLiked] = useState(review.user_has_liked ?? false);
  const [likeLoading, setLikeLoading] = useState(false);
  const editPhotoInputRef = useRef(null);
  const editTextareaRef = useRef(null);

  React.useEffect(() => {
    if (review.like_count !== undefined) setLikeCount(review.like_count);
    if (review.user_has_liked !== undefined) setUserHasLiked(review.user_has_liked);
  }, [review.like_count, review.user_has_liked]);

  useEffect(() => {
    if (reportFeedback?.type !== 'success') return undefined;
    const timer = setTimeout(() => setReportFeedback(null), 3200);
    return () => clearTimeout(timer);
  }, [reportFeedback]);

  useEffect(() => {
    if (!placeId || !review.user_id) {
      setReviewerVote(null);
      return;
    }
    let cancelled = false;
    fetch(`${API_BASE}/api/coffeeshops/${encodeURIComponent(placeId)}/votes/me?user_id=${review.user_id}`)
      .then((res) => res.json())
      .then((data) => {
        if (!cancelled && data?.status === 'success') {
          setReviewerVote(data.vote || null);
        }
      })
      .catch(() => {
        if (!cancelled) setReviewerVote(null);
      });
    return () => {
      cancelled = true;
    };
  }, [placeId, review.user_id]);

  const isOwner = user?.id === review.user_id;
  const timeAgo = getTimeAgo(review.created_at, review.relative_time);

  const ratingMeta = reviewerVote?.rating
    ? RATING_META.find((r) => r.key === reviewerVote.rating) || null
    : null;

  const sliderMetas = OVERALL_SLIDER_FIELDS.map((field) => {
    const value = reviewerVote?.[field];
    if (value === null || value === undefined) return null;
    const sliderInfo = SLIDER_META.find((s) => s.key === field);
    const label = REVIEW_CARD_SLIDER_LABELS_MAP[field]?.[Math.max(1, Math.min(5, Number(value) || 0)) - 1];
    return sliderInfo && label ? { ...sliderInfo, valueLabel: label } : null;
  }).filter(Boolean);

  const bestForTags = (reviewerVote?.best_for || [])
    .map((key) => BEST_FOR_META.find((meta) => meta.key === key))
    .filter(Boolean);

  // Handle edit click - isi form dari review
  const handleEditClick = () => {
    setEditText(review.text || '');
    setEditRating(review.rating || 0);
    setEditPhotos(
      sliceReviewPhotos(review.photos).map((p) => ({ id: p.id, image_data: p.image_data })),
    );
    setEditError('');
    setSuccess('');
    setIsEditing(true);
  };

  useEffect(() => {
    if (isEditing && editTextareaRef.current) {
      const el = editTextareaRef.current;
      el.focus();
      const len = el.value.length;
      el.setSelectionRange(len, len);
    }
  }, [isEditing]);

  const fileToBase64 = (file) =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
    });

  const handleEditAddPhoto = async (e) => {
    const files = e.target.files;
    if (!files?.length || editPhotos.length >= MAX_PHOTOS) return;
    for (let i = 0; i < files.length && editPhotos.length < MAX_PHOTOS; i++) {
      const file = files[i];
      if (!file.type.startsWith('image/')) continue;
      if (file.size > MAX_REVIEW_IMAGE_BYTES) {
        setEditError(`Ukuran gambar maksimal 2 MB per file. "${file.name}" dilewati.`);
        continue;
      }
      try {
        const image_data = await fileToBase64(file);
        setEditPhotos((prev) => [...prev, { image_data }]);
      } catch {
        setEditError('Gagal membaca file.');
      }
    }
    e.target.value = '';
  };

  const removeEditPhoto = (index) => {
    setEditPhotos((prev) => prev.filter((_, i) => i !== index));
  };

  const closeEditModal = () => {
    setMenuOpen(false);
    setIsEditing(false);
    setEditText(review.text || '');
    setEditRating(review.rating || 0);
    setEditPhotos(
      sliceReviewPhotos(review.photos).map((p) => ({ id: p.id, image_data: p.image_data })),
    );
    setEditError('');
    setSuccess('');
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
          photos: editPhotos.map((p) => ({ image_data: p.image_data })),
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
  const displayReviewPhotos = sliceReviewPhotos(review.photos);

  const renderHighlightedReviewText = () => {
    const text = String(review.text || '');
    if (!highlightKeyword?.trim()) return text;

    const escapedKeyword = escapeRegExp(highlightKeyword.trim());
    const parts = text.split(new RegExp(`(${escapedKeyword})`, 'gi'));

    return parts.map((part, index) =>
      part.toLowerCase() === highlightKeyword.trim().toLowerCase() ? (
        <strong key={`${part}-${index}`} className="font-bold text-gray-900 dark:text-white">
          {part}
        </strong>
      ) : (
        <React.Fragment key={`${part}-${index}`}>{part}</React.Fragment>
      )
    );
  };

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

  const handleReportClick = () => {
    setMenuOpen(false);
    if (!user?.id) {
      navigate('/login', {
        state: {
          from: window.location.pathname,
          placeId: placeId || review.place_id || null,
        },
      });
      return;
    }
    setReportFeedback(null);
    setShowReportConfirm(true);
  };

  const handleSubmitReport = async () => {
    if (!user?.id || isOwner || reportSubmitting || !review?.id) return;
    setReportSubmitting(true);
    setReportFeedback(null);
    try {
      const token = authService.getToken();
      if (!token) {
        setReportFeedback({ type: 'error', message: 'Silakan login untuk melaporkan ulasan.' });
        return;
      }
      const response = await fetch(`${API_BASE}/api/reviews/${review.id}/report`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          report_reason: 'Ulasan tidak pantas',
          report_text: '',
        }),
      });
      let data = null;
      try {
        data = await response.json();
      } catch {
        data = null;
      }
      if (response.ok && data?.status === 'success') {
        setShowReportConfirm(false);
        setReportFeedback({
          type: 'success',
          message: data.message || 'Laporan berhasil dikirim.',
        });
        return;
      }
      setReportFeedback({
        type: 'error',
        message: data?.message || 'Gagal mengirim laporan. Coba lagi.',
      });
    } catch (err) {
      setReportFeedback({
        type: 'error',
        message: err?.message || 'Gagal menghubungi server.',
      });
    } finally {
      setReportSubmitting(false);
    }
  };

  // Klik kartu review (oleh pemilik ataupun user lain) langsung membuka detail shop
  // dan auto-scroll ke review yang bersangkutan.
  const effectivePlaceId = placeId || review.place_id || review.placeId || '';
  const canOpenShop = Boolean(effectivePlaceId) && Boolean(review.id) && !isEditing && !menuOpen && !photoModal && !showReportConfirm;

  const handleCardClick = (e) => {
    if (!canOpenShop) return;
    if (e.target.closest('a, button, textarea, input, select')) return;
    navigate(`/shop/${encodeURIComponent(effectivePlaceId)}#review-${review.id}`);
  };

  return (
    <div
      onClick={handleCardClick}
      className={`bg-white dark:bg-zinc-800 rounded-xl border border-gray-200 dark:border-zinc-700 p-4 sm:p-5 relative ${
        canOpenShop ? 'cursor-pointer transition-shadow hover:shadow-md hover:border-amber-300 dark:hover:border-amber-600' : ''
      }`}
      title={canOpenShop ? 'Lihat coffee shop & review ini' : undefined}
    >
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
          {review.user_id ? (
            <Link
              to={`/profile/${review.user_id}`}
              className="font-bold text-gray-900 dark:text-white truncate block cursor-pointer hover:underline hover:text-amber-600 dark:hover:text-amber-500 transition-colors"
            >
              {displayName}
            </Link>
          ) : (
            <h4 className="font-bold text-gray-900 dark:text-white truncate">
              {displayName}
            </h4>
          )}
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
                    onClick={handleReportClick}
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

      {/* Kapan diupload + badge BARU (kiri) + label rating, overall experience, best-for (kanan) */}
      <div className="flex items-center justify-between gap-2 flex-wrap mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-gray-500 dark:text-gray-400">{timeAgo}</span>
          {isNewReview() && (
            <span className="px-2 py-0.5 text-xs font-medium rounded bg-gray-200 dark:bg-zinc-600 text-gray-700 dark:text-gray-300">
              BARU
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5 flex-wrap justify-end">
          {ratingMeta ? (
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${
                RATING_BADGE_CLASSES[ratingMeta.key]
              }`}
              title="Rating yang diberikan pengguna ini untuk coffee shop ini"
            >
              <span>{ratingMeta.emoji}</span>
              <span>{ratingMeta.label}</span>
            </span>
          ) : null}
          {sliderMetas.map((slider) => (
            <span
              key={slider.key}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-600 dark:bg-zinc-700 dark:text-gray-300"
              title={slider.label}
            >
              <span>{slider.emoji}</span>
              <span>{slider.valueLabel}</span>
            </span>
          ))}
          {bestForTags.map((tag) => (
            <span
              key={tag.key}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-600 dark:bg-zinc-700 dark:text-gray-300"
              title="Best when you want to"
            >
              <span>{tag.emoji}</span>
              <span>{tag.label}</span>
            </span>
          ))}
        </div>
      </div>

      {/* Review Text - tampil dengan paragraf (enter), atau form edit inline saat isEditing */}
      <>
        {isEditing ? (
          <div className="mb-3">
            <textarea
              ref={editTextareaRef}
              value={editText}
              onChange={(e) => { setEditText(e.target.value); setEditError(''); }}
              rows={4}
              className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-zinc-600 bg-white dark:bg-zinc-700 text-gray-900 dark:text-white placeholder-gray-500 focus:ring-2 focus:ring-amber-500 focus:border-transparent resize-none"
              placeholder="Bagikan pengalaman Anda tentang tempat ini..."
            />

            <div className="mt-3">
              <input
                ref={editPhotoInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleEditAddPhoto}
              />
              <button
                type="button"
                onClick={() => editPhotoInputRef.current?.click()}
                disabled={editPhotos.length >= MAX_PHOTOS}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border-2 border-dashed border-gray-300 dark:border-zinc-600 text-gray-600 dark:text-gray-400 hover:border-amber-500 hover:text-amber-600 dark:hover:text-amber-400 transition-colors disabled:opacity-50"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 13v7a2 2 0 01-2 2H7a2 2 0 01-2-2v-7" />
                </svg>
                Tambahkan foto ({editPhotos.length}/{MAX_PHOTOS})
              </button>
              {editPhotos.length > 0 && (
                <div className="mt-2 space-y-2">
                  {editPhotos.map((p, i) => (
                    <div key={p.id ?? `new-${i}`} className="flex gap-2 items-center p-2 bg-gray-50 dark:bg-zinc-900/50 rounded-lg">
                      <img src={p.image_data} alt="" className="w-14 h-14 object-cover rounded flex-shrink-0" />
                      <button type="button" onClick={() => removeEditPhoto(i)} className="p-1 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded flex-shrink-0 ml-auto" aria-label="Hapus foto">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {editError && <p className="text-sm text-red-600 dark:text-red-400 mt-2">{editError}</p>}

            <div className="flex justify-end gap-2 mt-3">
              <button type="button" onClick={closeEditModal} disabled={loading} className="px-4 py-2 rounded-lg font-medium bg-gray-200 dark:bg-zinc-600 text-gray-800 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-zinc-500 transition-colors disabled:opacity-50">
                Batal
              </button>
              <button type="button" onClick={handleEditSubmit} disabled={loading || !editText.trim()} className="px-4 py-2 rounded-lg font-medium bg-amber-600 hover:bg-amber-700 disabled:opacity-60 text-white transition-colors">
                {loading ? 'Menyimpan...' : 'Simpan'}
              </button>
            </div>
          </div>
        ) : (
          <>
            <p className="text-gray-700 dark:text-gray-300 text-sm leading-relaxed mb-3 whitespace-pre-wrap">
              {renderHighlightedReviewText()}
            </p>
            {displayReviewPhotos.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-3">
                {displayReviewPhotos.map((photo) => (
                  <div key={photo.id} className="flex flex-col">
                    <button
                      type="button"
                      onClick={() => setPhotoModal(photo)}
                      className="relative w-20 h-20 sm:w-24 sm:h-24 rounded-lg border-2 border-gray-200 dark:border-zinc-600 overflow-hidden cursor-pointer focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 transition-all duration-200 hover:scale-105 hover:border-amber-400 dark:hover:border-amber-500 hover:shadow-lg group"
                    >
                      <img
                        src={photo.image_data}
                        alt="Foto review"
                        className="w-full h-full object-cover transition-transform duration-200 group-hover:scale-105"
                      />
                      <span className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors duration-200 pointer-events-none" aria-hidden />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </>
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
                    alt="Foto review"
                    className="max-w-full max-h-[85vh] w-auto h-auto object-contain rounded-lg shadow-2xl"
                  />
                </div>
              </div>
            </>
          )}
          {success && (
            <p className="text-sm text-green-600 dark:text-green-400 mb-3">{success}</p>
          )}
      </>

      {/* Like button - tetap tampil di review sendiri, count tetap terlihat, tapi tetap nonaktif */}
      {!isEditing && (
        <div className="pt-3 flex items-center">
          <button
            type="button"
            onClick={handleLikeClick}
            disabled={likeLoading || !user?.id || isOwner}
            className={`inline-flex items-center gap-1.5 px-2 py-1.5 rounded-lg bg-transparent text-gray-600 dark:text-gray-400 transition-colors disabled:opacity-50 ${
              isOwner
                ? 'cursor-default'
                : 'hover:bg-gray-100 dark:hover:bg-zinc-700/50 hover:text-red-500 dark:hover:text-red-400'
            }`}
            aria-label={isOwner ? 'Total like review pribadi' : userHasLiked ? 'Batalkan like' : 'Suka'}
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
          <div
            className="fixed inset-0 bg-black/50 z-[100]"
            aria-hidden="true"
            onClick={() => !reportSubmitting && setShowReportConfirm(false)}
          />
          <div className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[min(90vw,360px)] bg-white dark:bg-zinc-800 rounded-xl shadow-xl p-5 z-[101]" role="dialog" aria-labelledby="report-title">
            <h3 id="report-title" className="font-semibold text-gray-900 dark:text-white mb-2">Laporkan ulasan?</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Apakah Anda yakin ingin melaporkan ulasan ini? Tim kami akan meninjau laporan Anda.
            </p>
            {reportFeedback?.type === 'error' && (
              <p className="mb-3 text-sm text-red-600 dark:text-red-400">{reportFeedback.message}</p>
            )}
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                disabled={reportSubmitting}
                onClick={() => setShowReportConfirm(false)}
                className="px-4 py-2 rounded-lg border border-gray-300 dark:border-zinc-600 text-gray-700 dark:text-gray-300 text-sm font-medium hover:bg-gray-50 dark:hover:bg-zinc-700 disabled:opacity-60"
              >
                Batal
              </button>
              <button
                type="button"
                disabled={reportSubmitting}
                onClick={handleSubmitReport}
                className="px-4 py-2 rounded-lg bg-amber-600 text-white text-sm font-medium hover:bg-amber-700 disabled:opacity-60"
              >
                {reportSubmitting ? 'Mengirim...' : 'Laporkan'}
              </button>
            </div>
          </div>
        </>
      )}

      {reportFeedback?.type === 'success' && !showReportConfirm && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[102] max-w-sm rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white shadow-lg">
          {reportFeedback.message}
        </div>
      )}
    </div>
  );
};

export default ReviewCard;

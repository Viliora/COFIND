import React, { useState, useRef } from 'react';
import { useAuth } from '../context/authContext';
import { Link } from 'react-router-dom';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';
const MAX_PHOTOS = 5;
const MAX_IMAGE_SIZE_KB = 500;

function StarRating({ value, hoverValue, onSelect, onHover }) {
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          onClick={() => onSelect(star)}
          onMouseEnter={() => onHover(star)}
          onMouseLeave={() => onHover(0)}
          className="p-0.5 transition-transform hover:scale-110 focus:outline-none"
          aria-label={`${star} bintang`}
        >
          <svg
            className={`w-8 h-8 ${
              star <= (hoverValue || value)
                ? 'text-amber-500 fill-amber-500'
                : 'text-gray-300 dark:text-gray-600'
            }`}
            fill="currentColor"
            viewBox="0 0 24 24"
          >
            <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
          </svg>
        </button>
      ))}
    </div>
  );
}

const ReviewForm = ({ placeId, shopName, onReviewSubmitted }) => {
  const { user, isAuthenticated } = useAuth();
  const [showModal, setShowModal] = useState(false);
  const [rating, setRating] = useState(0);
  const [ratingMakanan, setRatingMakanan] = useState(0);
  const [ratingLayanan, setRatingLayanan] = useState(0);
  const [ratingSuasana, setRatingSuasana] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);
  const [hoverMakanan, setHoverMakanan] = useState(0);
  const [hoverLayanan, setHoverLayanan] = useState(0);
  const [hoverSuasana, setHoverSuasana] = useState(0);
  const [text, setText] = useState('');
  const [photos, setPhotos] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const fileInputRef = useRef(null);

  const openModal = () => {
    setShowModal(true);
    setError('');
    setSuccess('');
  };

  const closeModal = () => {
    setShowModal(false);
    setRating(0);
    setRatingMakanan(0);
    setRatingLayanan(0);
    setRatingSuasana(0);
    setText('');
    setPhotos([]);
    setError('');
  };

  const fileToBase64 = (file) =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
    });

  const handleAddPhoto = async (e) => {
    const files = e.target.files;
    if (!files?.length || photos.length >= MAX_PHOTOS) return;
    for (let i = 0; i < files.length && photos.length < MAX_PHOTOS; i++) {
      const file = files[i];
      if (!file.type.startsWith('image/')) continue;
      if (file.size > MAX_IMAGE_SIZE_KB * 1024) {
        setError(`Ukuran gambar maksimal ${MAX_IMAGE_SIZE_KB} KB. "${file.name}" dilewati.`);
        continue;
      }
      try {
        const image_data = await fileToBase64(file);
        setPhotos((prev) => [...prev, { caption: '', image_data, file_name: file.name }]);
      } catch {
        setError('Gagal membaca file.');
      }
    }
    e.target.value = '';
  };

  const removePhoto = (index) => {
    setPhotos((prev) => prev.filter((_, i) => i !== index));
  };

  const updatePhotoCaption = (index, caption) => {
    setPhotos((prev) => prev.map((p, i) => (i === index ? { ...p, caption } : p)));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    if (!user?.id) {
      setError('Sesi Anda telah berakhir. Silakan login kembali.');
      return;
    }
    if (!rating) {
      setError('Silakan beri rating untuk tempat.');
      return;
    }
    if (!text.trim()) {
      setError('Silakan tulis pengalaman Anda.');
      return;
    }
    if (!placeId) {
      setError('ID tempat tidak valid.');
      return;
    }
    setLoading(true);
    try {
      const payload = {
        user_id: user.id,
        place_id: placeId,
        rating,
        text: text.trim(),
        rating_makanan: ratingMakanan || undefined,
        rating_layanan: ratingLayanan || undefined,
        rating_suasana: ratingSuasana || undefined,
        photos: photos.map((p) => ({ caption: p.caption || undefined, image_data: p.image_data }))
      };
      const response = await fetch(`${API_BASE}/api/reviews`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok || data.status !== 'success') {
        setError(data.message || 'Gagal menyimpan review.');
        setLoading(false);
        return;
      }
      setSuccess('Review berhasil dikirim!');
      if (onReviewSubmitted) {
        onReviewSubmitted({
          ...data.review,
          profiles: { username: user?.username, full_name: user?.full_name },
          source: 'local'
        });
      }
      setTimeout(() => {
        closeModal();
        setSuccess('');
      }, 1500);
    } catch (err) {
      setError('Terjadi kesalahan: ' + (err.message || 'Unknown error'));
    } finally {
      setLoading(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-900/20 dark:to-orange-900/20 p-6 rounded-xl border border-amber-200 dark:border-amber-800">
        <div className="text-center">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">Ingin memberikan review?</h3>
          <p className="text-gray-600 dark:text-gray-400 mb-4">Masuk atau daftar untuk menulis review tentang {shopName}</p>
          <Link
            to="/login"
            state={{ from: { pathname: `/shop/${placeId}`, search: '?scrollToReview=true' }, placeId, shopName, scrollToReview: true }}
            className="inline-flex items-center gap-2 px-6 py-3 bg-amber-600 hover:bg-amber-700 text-white font-semibold rounded-lg transition-colors"
          >
            Masuk untuk Review
          </Link>
        </div>
      </div>
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={openModal}
        className="w-full py-3 px-4 bg-amber-600 hover:bg-amber-700 text-white font-semibold rounded-xl border border-amber-500 dark:border-amber-600 transition-colors flex items-center justify-center gap-2"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
        </svg>
        Tulis Review
      </button>

      {showModal && (
        <>
          <div
            className="fixed inset-0 bg-black/50 z-[100]"
            aria-hidden="true"
            onClick={closeModal}
          />
          <div
            className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[min(95vw,520px)] max-h-[90vh] overflow-y-auto bg-white dark:bg-zinc-800 rounded-2xl border border-gray-200 dark:border-zinc-700 shadow-2xl z-[101]"
            role="dialog"
            aria-labelledby="review-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-5 sm:p-6">
              <h2 id="review-modal-title" className="text-xl font-semibold text-gray-900 dark:text-white text-center mb-4">
                {shopName}
              </h2>

              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-full bg-indigo-100 dark:bg-indigo-900/50 flex items-center justify-center text-indigo-600 dark:text-indigo-400 font-semibold">
                  {(user?.username || user?.full_name || 'U').toString().charAt(0).toUpperCase()}
                </div>
                <div>
                  <p className="font-semibold text-gray-900 dark:text-white">
                    {(user?.full_name || user?.username || 'User').toString().toUpperCase()}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1">
                    Memposting untuk publik di Google
                    <span className="inline-flex w-4 h-4 rounded-full bg-gray-200 dark:bg-gray-600 items-center justify-center text-gray-500" title="Review akan tampil secara publik">ⓘ</span>
                  </p>
                </div>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Rating tempat</p>
                  <StarRating value={rating} hoverValue={hoverRating} onSelect={setRating} onHover={setHoverRating} />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Makanan</p>
                  <StarRating value={ratingMakanan} hoverValue={hoverMakanan} onSelect={setRatingMakanan} onHover={setHoverMakanan} />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Layanan</p>
                  <StarRating value={ratingLayanan} hoverValue={hoverLayanan} onSelect={setRatingLayanan} onHover={setHoverLayanan} />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Suasana</p>
                  <StarRating value={ratingSuasana} hoverValue={hoverSuasana} onSelect={setRatingSuasana} onHover={setHoverSuasana} />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Bagikan pengalaman Anda tentang tempat ini
                  </label>
                  <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    rows={4}
                    className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-zinc-600 bg-white dark:bg-zinc-700 text-gray-900 dark:text-white placeholder-gray-500 focus:ring-2 focus:ring-amber-500 focus:border-transparent resize-none"
                    placeholder="Bagikan pengalaman Anda tentang tempat ini"
                  />
                </div>

                <div>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    multiple
                    className="hidden"
                    onChange={handleAddPhoto}
                  />
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={photos.length >= MAX_PHOTOS}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border-2 border-dashed border-gray-300 dark:border-zinc-600 text-gray-600 dark:text-gray-400 hover:border-amber-500 hover:text-amber-600 dark:hover:text-amber-400 transition-colors disabled:opacity-50"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 13v7a2 2 0 01-2 2H7a2 2 0 01-2-2v-7" />
                    </svg>
                    Tambahkan foto & video
                    {photos.length > 0 && <span className="text-xs">({photos.length}/{MAX_PHOTOS})</span>}
                  </button>
                  {photos.length > 0 && (
                    <div className="mt-2 space-y-2">
                      {photos.map((p, i) => (
                        <div key={i} className="flex gap-2 items-start p-2 bg-gray-50 dark:bg-zinc-900/50 rounded-lg">
                          <img src={p.image_data} alt="" className="w-14 h-14 object-cover rounded" />
                          <div className="flex-1 min-w-0">
                            <input
                              type="text"
                              value={p.caption}
                              onChange={(e) => updatePhotoCaption(i, e.target.value)}
                              placeholder="Keterangan (opsional)"
                              className="w-full text-sm px-2 py-1 rounded border border-gray-200 dark:border-zinc-600 bg-white dark:bg-zinc-700"
                            />
                          </div>
                          <button type="button" onClick={() => removePhoto(i)} className="p-1 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {error && (
                  <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
                )}
                {success && (
                  <p className="text-sm text-green-600 dark:text-green-400 font-medium">{success}</p>
                )}

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={closeModal}
                    className="px-4 py-2 rounded-lg font-medium bg-gray-200 dark:bg-zinc-600 text-gray-800 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-zinc-500 transition-colors"
                  >
                    Batal
                  </button>
                  <button
                    type="submit"
                    disabled={loading}
                    className="px-4 py-2 rounded-lg font-medium bg-amber-600 hover:bg-amber-700 disabled:opacity-60 text-white transition-colors"
                  >
                    {loading ? 'Mengirim...' : 'Posting'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </>
      )}
    </>
  );
};

export default ReviewForm;

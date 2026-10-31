import React, { useState } from 'react';
import { useAuth } from '../context/authContext';
import { Link } from 'react-router-dom';

import { API_BASE } from '../config/apiBase.js';
import { authService } from '../services/authService';

const ReviewForm = ({
  placeId,
  shopName,
  onReviewSubmitted,
}) => {
  const { user, isAuthenticated } = useAuth();
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showSuccessPopup, setShowSuccessPopup] = useState(false);

  const resetForm = () => {
    setText('');
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    if (!user?.id) {
      setError('Sesi Anda telah berakhir. Silakan login kembali.');
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
        rating: 5,
        text: text.trim(),
      };
      const response = await fetch(`${API_BASE}/api/reviews`, {
        method: 'POST',
        headers: authService.getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok || data.status !== 'success') {
        setError(data.message || 'Gagal menyimpan review.');
        setLoading(false);
        return;
      }
      setSuccess('Review berhasil dikirim!');
      setShowSuccessPopup(true);
      if (onReviewSubmitted) {
        onReviewSubmitted({
          ...data.review,
          profiles: { username: user?.username, full_name: user?.full_name },
          source: 'local',
        });
      }
      setTimeout(() => {
        resetForm();
        setSuccess('');
      }, 1500);
      setTimeout(() => setShowSuccessPopup(false), 2500);
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
      {showSuccessPopup && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center p-4 pointer-events-none">
          <div className="bg-white dark:bg-zinc-800 rounded-xl shadow-2xl border border-amber-200 dark:border-amber-700 px-6 py-4 flex items-center gap-3 animate-fadeIn max-w-sm">
            <div className="w-10 h-10 rounded-full bg-green-100 dark:bg-green-900/40 flex items-center justify-center flex-shrink-0">
              <svg className="w-6 h-6 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <p className="text-gray-900 dark:text-white font-medium">Review berhasil di input</p>
          </div>
        </div>
      )}

      <div className="bg-white dark:bg-zinc-800 rounded-2xl border border-gray-200 dark:border-zinc-700 shadow-sm">
        <div className="p-5 sm:p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={4}
                className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-zinc-600 bg-white dark:bg-zinc-700 text-gray-900 dark:text-white placeholder-gray-500 focus:ring-2 focus:ring-amber-500 focus:border-transparent resize-none"
                placeholder="Bagikan pengalaman Anda tentang tempat ini"
              />
            </div>

            {error && (
              <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
            )}
            {success && (
              <p className="text-sm text-green-600 dark:text-green-400 font-medium">{success}</p>
            )}

            <div className="flex justify-end gap-2 pt-2">
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
  );
};

export default ReviewForm;

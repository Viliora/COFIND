import React, { useEffect, useState } from 'react';
import { BestForBar, BEST_FOR_META, PRESENCE_META, RATING_META, VoteBarGroup } from './ShopVotesSummary';

export { BEST_FOR_META };

export const SLIDER_META = [
  { key: 'pelayanan', label: 'Pelayanan', emoji: '🛎️', color: 'accent-blue-500' },
  { key: 'kebersihan', label: 'Kebersihan', emoji: '✨', color: 'accent-emerald-500' },
  { key: 'kenyamanan', label: 'Kenyamanan', emoji: '🛋️', color: 'accent-purple-500' },
  { key: 'harga', label: 'Harga', emoji: '💰', color: 'accent-amber-500' },
];

const SLIDER_LABELS = ['Buruk', 'Kurang', 'Cukup', 'Baik', 'Istimewa'];

/**
 * Modal untuk memberikan vote pada coffee shop:
 * - Status kunjungan (here/been/want)
 * - Rating (love/like/ok/dislike/hate)
 * - Best for (tags multi-select)
 * - Slider: pelayanan, kebersihan, kenyamanan, harga
 */
const ShopVoteModal = ({ isOpen, onClose, shopName, summary, myVote, onSubmit, isSubmitting }) => {
  const [presence, setPresence] = useState(myVote?.presence || null);
  const [rating, setRating] = useState(myVote?.rating || null);
  const [bestFor, setBestFor] = useState(myVote?.best_for || []);
  const [sliders, setSliders] = useState({
    pelayanan: myVote?.pelayanan ?? null,
    kebersihan: myVote?.kebersihan ?? null,
    kenyamanan: myVote?.kenyamanan ?? null,
    harga: myVote?.harga ?? null,
  });

  useEffect(() => {
    if (isOpen) {
      setPresence(myVote?.presence || null);
      setRating(myVote?.rating || null);
      setBestFor(myVote?.best_for || []);
      setSliders({
        pelayanan: myVote?.pelayanan ?? null,
        kebersihan: myVote?.kebersihan ?? null,
        kenyamanan: myVote?.kenyamanan ?? null,
        harga: myVote?.harga ?? null,
      });
    }
  }, [isOpen, myVote]);

  useEffect(() => {
    if (!isOpen) return;
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleSubmit = () => {
    onSubmit({
      presence,
      rating,
      best_for: bestFor,
      ...sliders,
    });
  };

  const presenceCounts = summary?.presence_counts || {};
  const ratingCounts = summary?.rating_counts || {};
  const bestForCounts = summary?.best_for_counts || {};

  const maxPresence = Math.max(1, ...PRESENCE_META.map((p) => presenceCounts[p.key] || 0));
  const maxRating = Math.max(1, ...RATING_META.map((r) => ratingCounts[r.key] || 0));

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="shop-vote-modal-title"
    >
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      <div className="relative z-10 w-full max-w-2xl max-h-[90vh] bg-white dark:bg-zinc-900 rounded-2xl shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between gap-3 px-5 sm:px-6 py-4 border-b border-gray-200 dark:border-zinc-700 bg-gray-50 dark:bg-zinc-800/60">
          <div className="flex items-center gap-2 min-w-0">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-amber-100 dark:bg-amber-900/30 text-lg">
              ⭐
            </span>
            <h2 id="shop-vote-modal-title" className="text-base sm:text-lg font-bold text-gray-900 dark:text-white truncate">
              Beri vote untuk {shopName || 'coffee shop ini'}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex-shrink-0 inline-flex h-9 w-9 items-center justify-center rounded-full bg-white/80 text-gray-600 hover:bg-white hover:text-gray-900 dark:bg-zinc-700 dark:text-gray-300 dark:hover:bg-zinc-600 shadow-sm transition-colors cursor-pointer"
            aria-label="Tutup modal"
          >
            <svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto px-5 sm:px-6 py-5 space-y-6">
          <section className="flex flex-col gap-4">
            <VoteBarGroup
              title="Rating"
              titleEmoji="❤️"
              items={RATING_META}
              counts={ratingCounts}
              maxCount={maxRating}
              selectedKey={rating}
              onSelect={(key) => setRating((prev) => (prev === key ? null : key))}
              isSubmitting={isSubmitting}
            />
            <VoteBarGroup
              title="Status Kunjungan"
              titleEmoji="🕐"
              items={PRESENCE_META}
              counts={presenceCounts}
              maxCount={maxPresence}
              selectedKey={presence}
              onSelect={(key) => setPresence((prev) => (prev === key ? null : key))}
              isSubmitting={isSubmitting}
            />
            <BestForBar
              counts={bestForCounts}
              selectedKeys={bestFor}
              onToggle={(key) => setBestFor((prev) => (
                prev.includes(key) ? prev.filter((item) => item !== key) : [...prev, key]
              ))}
              isSubmitting={isSubmitting}
            />
          </section>

          {/* Sliders (opsional, tidak ada default rating) */}
          <section className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-5">
            {SLIDER_META.map((slider) => {
              const value = sliders[slider.key];
              const isRated = value !== null && value !== undefined;
              const displayValue = isRated ? value : 0;
              return (
                <div key={slider.key}>
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <div className="flex items-center gap-2">
                      <span>{slider.emoji}</span>
                      <span className="text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-300">
                        {slider.label}
                      </span>
                    </div>
                    {isRated && (
                      <button
                        type="button"
                        onClick={() => setSliders((prev) => ({ ...prev, [slider.key]: null }))}
                        className="text-[11px] text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300 transition-colors cursor-pointer"
                      >
                        Hapus
                      </button>
                    )}
                  </div>
                  <p className={`text-sm mb-1 ${isRated ? 'text-gray-800 dark:text-gray-100' : 'text-gray-400 dark:text-gray-500 italic'}`}>
                    {isRated ? SLIDER_LABELS[value - 1] : 'Belum dinilai (opsional)'}
                  </p>
                  <input
                    type="range"
                    min={0}
                    max={5}
                    step={1}
                    list={`ticks-${slider.key}`}
                    value={displayValue}
                    onChange={(e) => {
                      const v = Number(e.target.value);
                      setSliders((prev) => ({ ...prev, [slider.key]: v <= 0 ? null : v }));
                    }}
                    className={`w-full h-2 bg-gray-200 dark:bg-zinc-600 rounded-lg appearance-none cursor-pointer ${
                      isRated ? slider.color : 'accent-gray-400'
                    }`}
                  />
                  <datalist id={`ticks-${slider.key}`}>
                    <option value="0" />
                    <option value="1" />
                    <option value="2" />
                    <option value="3" />
                    <option value="4" />
                    <option value="5" />
                  </datalist>
                  <div className="flex justify-between px-0.5 mt-1">
                    <span
                      key="no-vote"
                      title="No vote (default)"
                      className={`h-1.5 w-1.5 rounded-full ring-1 ring-gray-400 dark:ring-zinc-500 ${
                        !isRated ? slider.color.replace('accent-', 'bg-') : 'bg-transparent'
                      }`}
                    />
                    {[1, 2, 3, 4, 5].map((level) => (
                      <span
                        key={level}
                        className={`h-1.5 w-1.5 rounded-full ${
                          isRated && level <= displayValue
                            ? slider.color.replace('accent-', 'bg-')
                            : 'bg-gray-300 dark:bg-zinc-600'
                        }`}
                      />
                    ))}
                  </div>
                  <div className="flex justify-between px-0.5 mt-0.5">
                    <span className="text-[9px] text-gray-400 dark:text-zinc-500 -ml-1">No vote</span>
                  </div>
                </div>
              );
            })}
          </section>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-5 sm:px-6 py-4 border-t border-gray-200 dark:border-zinc-700 bg-gray-50 dark:bg-zinc-800/60">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-200 dark:text-gray-300 dark:hover:bg-zinc-700 transition-colors cursor-pointer"
          >
            Batal
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="px-5 py-2 rounded-lg text-sm font-semibold bg-amber-600 hover:bg-amber-700 text-white shadow-sm transition-colors disabled:opacity-60 cursor-pointer"
          >
            {isSubmitting ? 'Menyimpan...' : 'Simpan Vote'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ShopVoteModal;

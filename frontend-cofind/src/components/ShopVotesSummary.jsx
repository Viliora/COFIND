import React from 'react';

export const RATING_META = [
  { key: 'love', label: 'love', emoji: '😍', barColor: 'bg-rose-400', textColor: 'text-rose-500' },
  { key: 'like', label: 'like', emoji: '🙂', barColor: 'bg-pink-400', textColor: 'text-pink-500' },
  { key: 'ok', label: 'ok', emoji: '😐', barColor: 'bg-orange-400', textColor: 'text-orange-500' },
  { key: 'dislike', label: 'dislike', emoji: '🙁', barColor: 'bg-blue-400', textColor: 'text-blue-500' },
  { key: 'hate', label: 'hate', emoji: '😠', barColor: 'bg-slate-400', textColor: 'text-slate-500' },
];

export const PRESENCE_META = [
  { key: 'here', label: 'saya sedang di sini', emoji: '📍', barColor: 'bg-emerald-400', textColor: 'text-emerald-500' },
  { key: 'been', label: 'saya pernah ke sini', emoji: '👣', barColor: 'bg-blue-400', textColor: 'text-blue-500' },
  { key: 'want', label: 'saya mau ke sini', emoji: '💛', barColor: 'bg-amber-400', textColor: 'text-amber-500' },
];

export const BEST_FOR_META = [
  { key: 'belajar', label: 'Belajar', emoji: '📚' },
  { key: 'kerja', label: 'Kerja/WFC', emoji: '💻' },
  { key: 'nge_game', label: 'Nge-game', emoji: '🎮' },
  { key: 'meeting', label: 'Meeting/Pertemuan', emoji: '🤝' },
  { key: 'family_time', label: 'Family Time', emoji: '👨‍👩‍👧' },
  { key: 'instagrammable', label: 'Instagrammable', emoji: '📸' },
];

function formatCount(n) {
  const num = Number(n) || 0;
  if (num >= 1000) return `${(num / 1000).toFixed(num % 1000 === 0 ? 0 : 1)}k`;
  return String(num);
}

function VoteBarGroup({ title, titleEmoji, items, counts, maxCount, selectedKey, onSelect, isSubmitting }) {
  return (
    <div className="flex-1 min-w-[220px] rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 p-4">
      <div className="flex items-center gap-2 mb-3 text-sm font-semibold text-gray-700 dark:text-gray-200">
        <span>{titleEmoji}</span>
        <span className="uppercase tracking-wide">{title}</span>
      </div>
      <div className="flex justify-between gap-2">
        {items.map((item) => {
          const count = counts?.[item.key] || 0;
          const pct = maxCount > 0 ? Math.max((count / maxCount) * 100, count > 0 ? 6 : 0) : 0;
          const isSelected = selectedKey === item.key;
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => onSelect?.(item.key)}
              disabled={isSubmitting}
              title={isSelected ? `Batalkan vote "${item.label}"` : `Vote "${item.label}"`}
              className="flex flex-col items-center gap-1.5 flex-1 cursor-pointer rounded-lg py-1 transition-colors hover:bg-gray-50 dark:hover:bg-zinc-700/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <span
                className={`text-2xl leading-none transition-all duration-300 ${
                  isSelected ? 'grayscale-0 opacity-100 scale-110' : 'grayscale opacity-60'
                }`}
              >
                {item.emoji}
              </span>
              <span className="text-xs text-gray-600 dark:text-gray-300">{item.label}</span>
              <div className="w-full h-1.5 rounded-full bg-gray-200 dark:bg-zinc-600 overflow-hidden">
                <div
                  className={`h-full rounded-full ${item.barColor} transition-all duration-500`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className={`text-xs font-semibold ${item.textColor}`}>{formatCount(count)}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Ringkasan hasil vote coffee shop (presence + rating).
 * Klik langsung pada salah satu opsi (emoji/bar) akan segera mengirim vote
 * untuk opsi tersebut, tanpa membuka ShopVoteModal. ShopVoteModal hanya
 * diakses lewat tombol "My Votes" / "Edit My Vote" di halaman ShopDetail
 * (untuk mengatur best_for & slider). Emoji pada setiap opsi ditampilkan
 * hitam-putih/grey, kecuali opsi yang telah dipilih user (myVote) yang
 * ditampilkan berwarna.
 */
const ShopVotesSummary = ({ summary, myVote, onSelectRating, onSelectPresence, onToggleBestFor, isSubmitting }) => {
  const presenceCounts = summary?.presence_counts || {};
  const ratingCounts = summary?.rating_counts || {};
  const bestForCounts = summary?.best_for_counts || {};
  const myBestFor = myVote?.best_for || [];

  const maxPresence = Math.max(1, ...PRESENCE_META.map((p) => presenceCounts[p.key] || 0));
  const maxRating = Math.max(1, ...RATING_META.map((r) => ratingCounts[r.key] || 0));
  const maxBestFor = Math.max(1, ...BEST_FOR_META.map((b) => bestForCounts[b.key] || 0));

  return (
    <div className="space-y-4">
    <div className="flex flex-col sm:flex-row gap-4">
      <VoteBarGroup
        title="Rating"
        titleEmoji="❤️"
        items={RATING_META}
        counts={ratingCounts}
        maxCount={maxRating}
        selectedKey={myVote?.rating}
        onSelect={onSelectRating}
        isSubmitting={isSubmitting}
      />
      <VoteBarGroup
        title="Status Kunjungan"
        titleEmoji="🕐"
        items={PRESENCE_META}
        counts={presenceCounts}
        maxCount={maxPresence}
        selectedKey={myVote?.presence}
        onSelect={onSelectPresence}
        isSubmitting={isSubmitting}
      />
    </div>

      <div className="rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 p-4">
        <div className="flex items-center gap-2 mb-3 text-sm font-semibold text-gray-700 dark:text-gray-200">
          <span>🎯</span>
          <span className="uppercase tracking-wide">It's best when you want to</span>
        </div>
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
          {BEST_FOR_META.map((item) => {
            const count = bestForCounts[item.key] || 0;
            const pct = maxBestFor > 0 ? Math.max((count / maxBestFor) * 100, count > 0 ? 6 : 0) : 0;
            const isSelected = myBestFor.includes(item.key);
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => onToggleBestFor?.(item.key)}
                disabled={isSubmitting}
                title={isSelected ? `Batalkan vote "${item.label}"` : `Vote "${item.label}"`}
                className="flex flex-col items-center gap-1.5 group cursor-pointer rounded-lg py-1 transition-colors hover:bg-gray-50 dark:hover:bg-zinc-700/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <span
                  className={`flex h-11 w-11 items-center justify-center rounded-full text-xl border-2 transition-all ${
                    isSelected
                      ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-900/30 scale-105'
                      : 'border-gray-200 dark:border-zinc-600 bg-white dark:bg-zinc-800 group-hover:border-gray-300'
                  }`}
                >
                  {item.emoji}
                </span>
                <span
                  className={`text-[11px] text-center leading-tight font-medium ${
                    isSelected ? 'text-emerald-700 dark:text-emerald-400' : 'text-gray-600 dark:text-gray-300'
                  }`}
                >
                  {item.label}
                </span>
                <div className="w-full h-1.5 rounded-full bg-gray-200 dark:bg-zinc-600 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${isSelected ? 'bg-emerald-400' : 'bg-gray-300 dark:bg-zinc-500'}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="text-[11px] text-gray-500 dark:text-gray-400">{formatCount(count)}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default ShopVotesSummary;

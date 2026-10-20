import React from 'react';
import { BEST_FOR_META, PRESENCE_META, RATING_META } from '../constants/shopVoteMeta';

function formatCount(n) {
  const num = Number(n) || 0;
  if (num >= 1000) return `${(num / 1000).toFixed(num % 1000 === 0 ? 0 : 1)}k`;
  return String(num);
}

export function VoteBarGroup({
  title,
  titleEmoji,
  items,
  counts,
  maxCount,
  selectedKey,
  onSelect,
  isSubmitting,
  readOnly = false,
}) {
  return (
    <div className="flex-1 min-w-[220px] rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 p-4">
      {(title || titleEmoji) && (
        <div className="flex items-center gap-2 mb-3 text-sm font-semibold text-gray-700 dark:text-gray-200">
          {titleEmoji ? <span>{titleEmoji}</span> : null}
          {title ? <span className="uppercase tracking-wide">{title}</span> : null}
        </div>
      )}
      <div className="flex justify-between gap-2">
        {items.map((item) => {
          const count = counts?.[item.key] || 0;
          const pct = maxCount > 0 ? Math.max((count / maxCount) * 100, count > 0 ? 6 : 0) : 0;
          const isSelected = selectedKey === item.key;
          const emojiClass = isSelected
            ? 'grayscale-0 opacity-100 scale-110'
            : readOnly && count > 0
              ? 'grayscale-0 opacity-90'
              : 'grayscale opacity-60';
          const inner = (
            <>
              <span className={`text-2xl leading-none transition-all duration-300 ${emojiClass}`}>
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
            </>
          );
          if (readOnly) {
            return (
              <div
                key={item.key}
                className="flex flex-col items-center gap-1.5 flex-1 rounded-lg py-1"
                title={`${formatCount(count)} ulasan`}
              >
                {inner}
              </div>
            );
          }
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => onSelect?.(item.key)}
              disabled={isSubmitting}
              title={isSelected ? `Batalkan vote "${item.label}"` : `Vote "${item.label}"`}
              className="flex flex-col items-center gap-1.5 flex-1 cursor-pointer rounded-lg py-1 transition-colors hover:bg-gray-50 dark:hover:bg-zinc-700/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {inner}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function BestForBar({ counts, selectedKeys = [], onToggle, isSubmitting }) {
  const maxCount = Math.max(1, ...BEST_FOR_META.map((item) => counts?.[item.key] || 0));

  return (
    <div className="rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 p-4">
      <div className="flex items-center gap-2 mb-3 text-sm font-semibold text-gray-700 dark:text-gray-200">
        <span>🎯</span>
        <span className="uppercase tracking-wide">It's best when you want to</span>
      </div>
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
        {BEST_FOR_META.map((item) => {
          const count = counts?.[item.key] || 0;
          const pct = maxCount > 0 ? Math.max((count / maxCount) * 100, count > 0 ? 6 : 0) : 0;
          const isSelected = selectedKeys.includes(item.key);
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => onToggle?.(item.key)}
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
  );
}

/**
 * Ringkasan hasil vote coffee shop (presence + rating).
 * Klik langsung pada salah satu opsi (emoji/bar) akan segera mengirim vote
 * untuk opsi tersebut, tanpa membuka ShopVoteModal. ShopVoteModal hanya
 * diakses lewat tombol "My Votes" / "Edit My Vote" di halaman ShopDetail
 * (untuk mengatur slider dan opsi lanjutan). Emoji pada setiap opsi ditampilkan
 * hitam-putih/grey, kecuali opsi yang telah dipilih user (myVote) yang
 * ditampilkan berwarna.
 */
const ShopVotesSummary = ({
  summary,
  myVote,
  onSelectRating,
  onSelectPresence,
  isSubmitting,
  hidePresence = false,
  readOnly = false,
}) => {
  const presenceCounts = summary?.presence_counts || {};
  const ratingCounts = summary?.rating_counts || {};

  const maxPresence = Math.max(1, ...PRESENCE_META.map((p) => presenceCounts[p.key] || 0));
  const maxRating = Math.max(1, ...RATING_META.map((r) => ratingCounts[r.key] || 0));

  return (
    <div className={`flex flex-col ${hidePresence ? '' : 'sm:flex-row'} gap-4`}>
      <VoteBarGroup
        items={RATING_META}
        counts={ratingCounts}
        maxCount={maxRating}
        selectedKey={readOnly ? null : myVote?.rating}
        onSelect={onSelectRating}
        isSubmitting={isSubmitting}
        readOnly={readOnly}
      />
      {!hidePresence && (
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
      )}
    </div>
  );
};

export default ShopVotesSummary;

import React, { useMemo } from 'react';

const STAR_LEVELS = [5, 4, 3, 2, 1];

function formatCount(n) {
  const num = Number(n) || 0;
  if (num >= 1000) return `${(num / 1000).toFixed(num % 1000 === 0 ? 0 : 1)}k`;
  return String(num);
}

function StarIcons({ count }) {
  return (
    <span className="inline-flex text-amber-400 text-sm leading-none" aria-hidden>
      {Array.from({ length: count }, (_, i) => (
        <span key={i}>★</span>
      ))}
    </span>
  );
}

/**
 * Histogram rating bintang 1–5 dari ulasan (review_star_counts API).
 */
export default function ShopReviewStarSummary({
  reviewStarCounts,
  reviewStarTotal = 0,
  averageRating = null,
}) {
  const counts = reviewStarCounts || {};
  const total = useMemo(
    () => Number(reviewStarTotal) || STAR_LEVELS.reduce((sum, star) => sum + (Number(counts[String(star)]) || 0), 0),
    [counts, reviewStarTotal],
  );
  const maxCount = useMemo(
    () => Math.max(1, ...STAR_LEVELS.map((star) => Number(counts[String(star)]) || 0)),
    [counts],
  );

  if (!total) {
    return (
      <p className="text-sm text-gray-600 dark:text-gray-400 rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 p-4">
        Belum ada ulasan dengan rating bintang untuk coffee shop ini.
      </p>
    );
  }

  return (
    <div className="rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 p-4 sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-4">
        <p className="text-xs text-gray-500 dark:text-gray-400">
          Berdasarkan {formatCount(total)} ulasan dengan rating bintang
        </p>
        {averageRating != null && Number.isFinite(Number(averageRating)) ? (
          <p className="text-sm font-semibold text-gray-900 dark:text-white">
            Rata-rata{' '}
            <span className="text-amber-500">★ {Number(averageRating).toFixed(1)}</span>
          </p>
        ) : null}
      </div>
      <ul className="space-y-2.5">
        {STAR_LEVELS.map((star) => {
          const count = Number(counts[String(star)]) || 0;
          const pct = maxCount > 0 ? Math.max((count / maxCount) * 100, count > 0 ? 4 : 0) : 0;
          return (
            <li key={star} className="flex items-center gap-3">
              <div className="flex items-center gap-1 w-[4.5rem] shrink-0">
                <StarIcons count={star} />
              </div>
              <div className="flex-1 h-2.5 rounded-full bg-gray-200 dark:bg-zinc-600 overflow-hidden">
                <div
                  className="h-full rounded-full bg-amber-400 dark:bg-amber-500 transition-all duration-500"
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="w-8 text-right text-sm font-semibold text-gray-700 dark:text-gray-200 tabular-nums">
                {formatCount(count)}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

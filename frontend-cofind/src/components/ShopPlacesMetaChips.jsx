import React from 'react';
import { formatOpenNowBadge } from '../utils/googlePlacesDisplay';

/**
 * Badge metadata toko di hero detail: rating, jumlah ulasan, status buka/tutup.
 */
export default function ShopPlacesMetaChips({ meta }) {
  if (!meta) return null;

  const { rating, userRatingsTotal, openNow, todayHours } = meta;
  const openBadge = formatOpenNowBadge(openNow, todayHours);

  const hasAny =
    rating != null
    || userRatingsTotal != null
    || openNow !== undefined;

  if (!hasAny) return null;

  return (
    <div className="flex flex-wrap gap-2 text-xs sm:text-sm text-gray-700 dark:text-gray-300">
      {rating != null && (
        <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 dark:bg-amber-900/20 px-3 py-1.5 border border-amber-200 dark:border-amber-900/50 font-semibold text-gray-900 dark:text-white">
          ⭐ {Number(rating).toFixed(1)}
        </span>
      )}
      {userRatingsTotal != null && (
        <span className="inline-flex items-center rounded-full bg-white/90 dark:bg-zinc-800 px-3 py-1.5 border border-gray-200 dark:border-zinc-700">
          {Number(userRatingsTotal).toLocaleString('id-ID')} ulasan
        </span>
      )}
      {openBadge && (
        <span
          title={openBadge.title}
          className={`inline-flex items-center rounded-full px-3 py-1.5 border font-medium max-w-full truncate ${
            openNow
              ? 'bg-green-50 border-green-200 text-green-800 dark:bg-green-950/40 dark:border-green-800 dark:text-green-200'
              : 'bg-red-50 border-red-200 text-red-800 dark:bg-red-950/40 dark:border-red-800 dark:text-red-200'
          }`}
        >
          {openBadge.text}
        </span>
      )}
    </div>
  );
}

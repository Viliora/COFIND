import React, { useMemo } from 'react';
import { resolveOpeningHoursSchedule } from '../utils/googlePlacesDisplay';

/**
 * Jam operasional hari ini + dropdown jadwal lengkap (native <details>).
 */
export default function ShopOpeningHoursBlock({ shop }) {
  const { today, todayHours, allDays } = useMemo(
    () => resolveOpeningHoursSchedule(shop || {}),
    [shop],
  );

  const hasSchedule = Boolean(todayHours) || allDays.length > 0;
  const showFullSchedule = allDays.length > 1
    || (allDays.length === 1 && allDays[0].day !== 'Setiap hari');

  if (!hasSchedule) {
    return (
      <div className="flex items-start gap-3 p-4 bg-amber-50/50 dark:bg-amber-900/10 rounded-lg border border-amber-100 dark:border-amber-900/30">
        <span className="text-lg flex-shrink-0" aria-hidden>🕐</span>
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Jam Operasional</p>
          <p className="text-sm sm:text-base text-gray-600 dark:text-gray-400">
            Jam operasional belum diisi
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-amber-100 dark:border-amber-900/30 bg-amber-50/50 dark:bg-amber-900/10 overflow-hidden">
      <div className="flex items-start gap-3 p-4">
        <span className="text-lg flex-shrink-0" aria-hidden>🕐</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Jam Operasional</p>
          <p className="text-sm sm:text-base text-gray-800 dark:text-gray-200">
            <span className="font-semibold text-gray-900 dark:text-white">{today}</span>
            {' · '}
            {todayHours || '—'}
          </p>
        </div>
      </div>

      {showFullSchedule ? (
        <details className="group border-t border-amber-100/80 dark:border-amber-900/40">
          <summary className="cursor-pointer list-none px-4 py-2.5 text-sm font-medium text-indigo-700 dark:text-indigo-300 hover:bg-amber-100/60 dark:hover:bg-amber-900/20 flex items-center justify-between gap-2 select-none [&::-webkit-details-marker]:hidden">
            <span>Lihat jadwal lengkap</span>
            <svg
              className="w-4 h-4 flex-shrink-0 transition-transform group-open:rotate-180"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
              aria-hidden
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </summary>
          <ul className="px-4 pb-4 pt-1 space-y-1.5 text-sm text-gray-700 dark:text-gray-300">
            {allDays.map((row) => {
              const isToday = row.day === today;
              return (
                <li
                  key={`${row.day}-${row.hours}`}
                  className={`flex flex-wrap justify-between gap-x-3 gap-y-0.5 rounded-md px-2 py-1.5 ${
                    isToday
                      ? 'bg-white/80 dark:bg-zinc-800/80 font-medium text-gray-900 dark:text-white'
                      : ''
                  }`}
                >
                  <span>{row.day}</span>
                  <span className="text-gray-600 dark:text-gray-400 tabular-nums">{row.hours}</span>
                </li>
              );
            })}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

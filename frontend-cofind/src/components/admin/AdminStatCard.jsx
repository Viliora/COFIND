import React from 'react';

export default function AdminStatCard({ label, value, helper }) {
  return (
    <div className="rounded-2xl border border-gray-100 dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm p-5 hover:shadow-md transition-shadow">
      <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">{label}</p>
      <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">{value}</p>
      {helper ? <p className="mt-2 text-xs text-gray-400 dark:text-gray-500">{helper}</p> : null}
    </div>
  );
}

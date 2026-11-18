import React from 'react';

export default function AdminStatCard({ label, value, helper }) {
  return (
    <div className="rounded-panel border border-cofind-rule bg-cofind-surface p-5 shadow-cofind-sm transition-colors duration-200 hover:bg-cofind-paper">
      <p className="text-xs font-semibold uppercase tracking-wider text-cofind-muted">{label}</p>
      <p className="mt-2 font-display text-3xl font-bold text-cofind-ink">{value}</p>
      {helper ? <p className="mt-2 text-xs text-cofind-muted">{helper}</p> : null}
    </div>
  );
}
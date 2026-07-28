import React from 'react';

export default function AdminStatCard({ label, value, helper }) {
  return (
    <div className="rounded-2xl border border-stone-200/50 bg-[#FAF9F6]/95 shadow-[0_8px_30px_rgb(0,0,0,0.04)] p-5 transition-all duration-300 ease-out hover:-translate-y-1 hover:shadow-[0_12px_40px_rgb(0,0,0,0.06)]">
      <p className="text-xs font-semibold uppercase tracking-wider text-stone-400">{label}</p>
      <p className="mt-2 font-serif text-3xl font-bold text-stone-800">{value}</p>
      {helper ? <p className="mt-2 text-xs text-stone-500">{helper}</p> : null}
    </div>
  );
}

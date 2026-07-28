import React from 'react';

export default function AdminTopbar({ profile, onLogout }) {

  return (
    <div className="rounded-2xl border border-stone-200/50 bg-[#FAF9F6]/95 shadow-[0_8px_30px_rgb(0,0,0,0.04)] px-5 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-full bg-gradient-to-br from-amber-600 to-orange-700 flex items-center justify-center text-stone-50 font-bold text-sm shrink-0 shadow-[0_8px_30px_rgb(0,0,0,0.04)]">
          {(profile?.full_name || profile?.username || 'A')[0].toUpperCase()}
        </div>
        <div>
          <p className="text-xs text-stone-400 uppercase tracking-wider font-medium">Administrator</p>
          <p className="font-serif text-sm font-semibold text-stone-800 leading-tight">
            {profile?.full_name || profile?.username || 'Admin'}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onLogout}
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-100 transition-all duration-300 ease-out cursor-pointer"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          Logout
        </button>
      </div>
    </div>
  );
}

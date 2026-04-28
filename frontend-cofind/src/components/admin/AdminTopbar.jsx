import React from 'react';

export default function AdminTopbar({ profile, onLogout }) {

  return (
    <div className="rounded-2xl border border-gray-100 bg-white shadow-sm px-5 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-full bg-amber-100 flex items-center justify-center text-amber-700 font-bold text-sm shrink-0">
          {(profile?.full_name || profile?.username || 'A')[0].toUpperCase()}
        </div>
        <div>
          <p className="text-xs text-gray-400 uppercase tracking-wider font-medium">Administrator</p>
          <p className="text-sm font-semibold text-gray-900 leading-tight">
            {profile?.full_name || profile?.username || 'Admin'}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onLogout}
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-100 transition-colors"
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

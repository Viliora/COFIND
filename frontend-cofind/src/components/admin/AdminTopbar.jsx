import React from 'react';

export default function AdminTopbar({ profile, onLogout }) {
  return (
    <div className="flex flex-col gap-4 rounded-panel border border-cofind-rule bg-cofind-surface px-5 py-4 shadow-cofind-sm sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-cofind-primary text-sm font-bold text-cofind-on-primary shadow-cofind-sm">
          {(profile?.full_name || profile?.username || 'A')[0].toUpperCase()}
        </div>
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-cofind-muted">Administrator</p>
          <p className="font-display text-sm font-semibold leading-tight text-cofind-ink">
            {profile?.full_name || profile?.username || 'Admin'}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onLogout}
          className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-panel border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-600 transition-colors duration-200 hover:bg-red-100"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          Logout
        </button>
      </div>
    </div>
  );
}
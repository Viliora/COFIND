import React from 'react';

export default function AdminModal({ isOpen, title, onClose, children, maxWidth = 'max-w-3xl' }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-cofind-ink/40 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        className={`relative z-[121] max-h-[90vh] w-full overflow-y-auto rounded-panel border border-cofind-rule bg-cofind-surface shadow-cofind-lg ${maxWidth}`}
      >
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-cofind-rule bg-cofind-surface px-5 py-4">
          <h3 className="font-display text-base font-semibold text-cofind-ink">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="cursor-pointer rounded-control p-1.5 text-cofind-muted transition-colors duration-200 hover:bg-cofind-paper hover:text-cofind-ink"
            aria-label="Tutup"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}
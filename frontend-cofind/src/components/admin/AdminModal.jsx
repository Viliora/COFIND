import React from 'react';

export default function AdminModal({ isOpen, title, onClose, children, maxWidth = 'max-w-3xl' }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-stone-900/40 backdrop-blur-sm" onClick={onClose} aria-hidden="true" />
      <div className={`relative z-[121] w-full ${maxWidth} rounded-2xl bg-[#FAF9F6] shadow-[0_12px_40px_rgb(0,0,0,0.12)] border border-stone-200/50 max-h-[90vh] overflow-y-auto`}>
        <div className="sticky top-0 z-10 flex items-center justify-between px-5 py-4 border-b border-stone-200/60 bg-[#FAF9F6]/95 backdrop-blur">
          <h3 className="font-serif text-base font-semibold text-stone-800">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-stone-400 hover:bg-stone-100 hover:text-stone-700 transition-all duration-300 ease-out cursor-pointer"
            aria-label="Tutup"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

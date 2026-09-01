import React, { useEffect, useRef, useState } from 'react';
import { FACILITY_ATTRIBUTE_GROUPS } from '../constants/reviewPills';

/**
 * Preferensi lapis 2 (atribut fasilitas).
 *
 * Tombol opsi muncul setelah konteks aktivitas lapis 1 dipilih; saat ditekan,
 * panel berisi daftar checkbox atribut terbuka. Input tetap tertutup (bukan
 * teks bebas) supaya nilai yang dikirim ke backend selalu dikenali.
 */
/** Harus sama dengan _MAX_ATTRIBUTE_PILLS di app.py; lebih dari ini diabaikan backend. */
export const MAX_FACILITY_ATTRIBUTES = 3;

export default function FacilityAttributePicker({
  selected = [],
  onChange,
  disabled = false,
  maxSelected = MAX_FACILITY_ATTRIBUTES,
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;

    const onPointerDown = (event) => {
      if (!containerRef.current?.contains(event.target)) setOpen(false);
    };
    const onKeyDown = (event) => {
      if (event.key === 'Escape') setOpen(false);
    };

    document.addEventListener('mousedown', onPointerDown);
    window.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  useEffect(() => {
    if (disabled) setOpen(false);
  }, [disabled]);

  const selectedCount = selected.length;
  const limitReached = selectedCount >= maxSelected;

  const toggleAttribute = (value) => {
    if (selected.includes(value)) {
      onChange?.(selected.filter((item) => item !== value));
      return;
    }
    if (limitReached) return;
    onChange?.([...selected, value]);
  };

  return (
    <div ref={containerRef} className="relative mt-4">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={disabled}
          onClick={() => setOpen((prev) => !prev)}
          aria-expanded={open}
          aria-haspopup="true"
          className={`
            inline-flex items-center gap-2 px-3 sm:px-4 py-2 rounded-full text-sm font-semibold
            transition-shadow duration-200 ease-out
            focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-zinc-900
            disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none
            ${
              selectedCount > 0
                ? 'bg-gradient-to-r from-indigo-500 via-violet-500 to-purple-600 text-white shadow-lg shadow-indigo-600/35 hover:shadow-xl hover:shadow-indigo-600/45'
                : 'bg-gradient-to-br from-slate-200 via-slate-100 to-zinc-200 text-slate-900 dark:from-zinc-600 dark:via-zinc-700 dark:to-zinc-800 dark:text-zinc-100 shadow-md shadow-slate-500/10 hover:shadow-lg hover:shadow-slate-500/25'
            }
          `}
        >
          <span aria-hidden>⚙️</span>
          Fasilitas tambahan
          {selectedCount > 0 && (
            <span className="inline-flex items-center justify-center min-w-5 h-5 px-1.5 rounded-full bg-white/25 text-xs font-bold">
              {selectedCount}
            </span>
          )}
          <span className={`text-xs transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden>
            ▾
          </span>
        </button>
      </div>

      {open && (
        <div className="absolute z-30 mt-2 w-[min(28rem,calc(100vw-2rem))] max-h-[26rem] overflow-y-auto rounded-2xl border border-gray-200 bg-white p-4 shadow-2xl dark:border-zinc-700 dark:bg-zinc-900">
          <div className="mb-3">
            <p className="text-sm font-semibold text-gray-800 dark:text-gray-100">
              Detail fasilitas (opsional)
            </p>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              Centang atribut yang Anda butuhkan (maksimal {maxSelected}).
            </p>
            {limitReached && (
              <p className="mt-1 text-xs font-medium text-amber-600 dark:text-amber-400">
                Batas {maxSelected} atribut tercapai. Hapus salah satu untuk menukar pilihan.
              </p>
            )}
          </div>

          <div className="space-y-4">
            {FACILITY_ATTRIBUTE_GROUPS.map((group) => (
              <fieldset key={group.id}>
                <legend className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  {group.label}
                </legend>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
                  {group.options.map((option) => {
                    const checked = selected.includes(option.value);
                    const blocked = !checked && limitReached;
                    return (
                      <label
                        key={option.value}
                        className={`
                          flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm
                          transition-colors
                          ${blocked ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}
                          ${
                            checked
                              ? 'bg-indigo-50 text-indigo-800 dark:bg-indigo-500/15 dark:text-indigo-100'
                              : 'text-gray-700 hover:bg-gray-50 dark:text-gray-200 dark:hover:bg-zinc-800'
                          }
                        `}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={disabled || blocked}
                          onChange={() => toggleAttribute(option.value)}
                          className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 dark:border-zinc-600 dark:bg-zinc-800"
                        />
                        <span aria-hidden>{option.icon}</span>
                        <span>{option.label}</span>
                      </label>
                    );
                  })}
                </div>
              </fieldset>
            ))}
          </div>

          <div className="mt-4 flex items-center justify-between gap-2 border-t border-gray-100 pt-3 dark:border-zinc-700">
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {selectedCount > 0
                ? `${selectedCount}/${maxSelected} atribut dipilih`
                : 'Belum ada atribut dipilih'}
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => onChange?.([])}
                disabled={disabled || selectedCount === 0}
                className="px-3 py-1.5 rounded-full text-xs font-semibold text-gray-600 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed dark:text-gray-300 dark:hover:bg-zinc-800"
              >
                Reset
              </button>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="px-3 py-1.5 rounded-full text-xs font-semibold bg-indigo-600 text-white shadow-sm hover:bg-indigo-700"
              >
                Selesai
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

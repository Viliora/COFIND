import React, { useEffect, useRef, useState } from 'react';
import { FACILITY_ATTRIBUTE_GROUPS } from '../constants/reviewPills';

/** Harus sama dengan _MAX_ATTRIBUTE_PILLS di app.py */
export const MAX_FACILITY_ATTRIBUTES = 3;

export default function FacilityAttributePicker({
  // Kompatibilitas ganda: menerima 'selected' (dari ShopList) atau 'selectedAttributes'
  selected,
  selectedAttributes: rawSelectedAttributes,
  // Kompatibilitas ganda: menerima 'onChange' (dari ShopList) atau 'onToggleAttribute'
  onChange,
  onToggleAttribute,
  disabled = false,
  maxSelected = MAX_FACILITY_ATTRIBUTES,
}) {
  const [open, setOpen] = useState(false);

  // Normalisasi data props
  const currentSelected = selected ?? rawSelectedAttributes ?? [];

  const containerRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;

    const onPointerDown = (event) => {
      if (!containerRef.current?.contains(event.target)) {
        setOpen(false);
      }
    };

    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', onPointerDown);
    window.addEventListener('keydown', onKeyDown);

    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  useEffect(() => {
    if (disabled) {
      setOpen(false);
    }
  }, [disabled]);

  const selectedCount = currentSelected.length;
  const limitReached = selectedCount >= maxSelected;

  const toggleAttribute = (value) => {
    if (disabled) return;

    let nextValues = [];
    if (currentSelected.includes(value)) {
      nextValues = currentSelected.filter((item) => item !== value);
    } else {
      if (limitReached) return;
      nextValues = [...currentSelected, value];
    }

    // Panggil callback yang disediakan parent
    if (typeof onChange === 'function') {
      onChange(nextValues);
    } else if (typeof onToggleAttribute === 'function') {
      onToggleAttribute(value);
    }
  };

  return (
    <div ref={containerRef} className="relative mt-4 w-full">
      {/* Tombol Utama Buka/Tutup Panel */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={disabled}
          onClick={() => setOpen((prev) => !prev)}
          aria-expanded={open}
          aria-haspopup="true"
          className={`
            inline-flex items-center gap-2 px-3 sm:px-4 py-2 rounded-full
            text-sm font-semibold transition-all duration-200 ease-out
            focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400
            disabled:opacity-50 disabled:cursor-not-allowed
            ${
              selectedCount > 0
                ? 'bg-gradient-to-r from-indigo-500 via-violet-500 to-purple-600 text-white shadow-lg shadow-indigo-600/35 hover:shadow-indigo-600/45'
                : 'bg-slate-100 dark:bg-zinc-800 text-slate-800 dark:text-zinc-200 border border-slate-200 dark:border-zinc-700 hover:bg-slate-200 dark:hover:bg-zinc-700 shadow-sm'
            }
          `}
        >
          <span aria-hidden>⚙️</span>
          <span>Fasilitas tambahan</span>

          {selectedCount > 0 && (
            <span className="inline-flex items-center justify-center min-w-5 h-5 px-1.5 rounded-full bg-white/25 text-xs font-bold">
              {selectedCount}
            </span>
          )}

          <span
            className={`text-xs transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
            aria-hidden
          >
            ▾
          </span>
        </button>
      </div>

      {/* Dropdown Panel Atribut */}
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

                <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
                  {group.options.map((option) => {
                    const checked = currentSelected.includes(option.value);
                    const blocked = !checked && limitReached;

                    return (
                      <label
                        key={option.value}
                        onClick={(e) => {
                          // Cegah bubbling klik ganda browser
                          if (e.target.tagName !== 'INPUT') {
                            e.preventDefault();
                            toggleAttribute(option.value);
                          }
                        }}
                        className={`
                          flex items-center gap-2 px-2.5 py-2 rounded-lg text-sm select-none transition-colors
                          ${disabled || blocked ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}
                          ${
                            checked
                              ? 'bg-indigo-50 text-indigo-800 dark:bg-indigo-500/20 dark:text-indigo-200 font-medium'
                              : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-zinc-800'
                          }
                        `}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={disabled}
                          onChange={() => toggleAttribute(option.value)}
                          className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 dark:border-zinc-600 dark:bg-zinc-800 pointer-events-none"
                        />
                        <span aria-hidden className="pointer-events-none">{option.icon}</span>
                        <span className="pointer-events-none">{option.label}</span>
                      </label>
                    );
                  })}
                </div>
              </fieldset>
            ))}
          </div>

          {/* Footer Dropdown */}
          <div className="mt-4 flex items-center justify-between gap-2 border-t border-gray-100 pt-3 dark:border-zinc-700">
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {selectedCount > 0 ? `${selectedCount}/${maxSelected} atribut dipilih` : 'Belum ada atribut dipilih'}
            </span>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  if (typeof onChange === 'function') onChange([]);
                  if (typeof onToggleAttribute === 'function') {
                    currentSelected.forEach((item) => onToggleAttribute(item));
                  }
                }}
                disabled={disabled || selectedCount === 0}
                className="rounded-full px-3 py-1.5 text-xs font-semibold text-gray-600 hover:bg-gray-100 disabled:opacity-50 dark:text-gray-300 dark:hover:bg-zinc-800"
              >
                Reset
              </button>

              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-full bg-indigo-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700"
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

import React, { useState } from 'react';
import {
  CONTEXT_PILL_OPTIONS,
  CONTEXT_PILL_THEMES,
  CONTEXT_PILL_THEME_DEFAULT,
  FACILITY_ATTRIBUTE_GROUPS,
} from '../constants/reviewPills';

/** Sinkron recommendation/request_prefs.py _MAX_ATTRIBUTE_PILLS */
export const MAX_FACILITY_ATTRIBUTES = 3;

const TABS = [
  { id: 'activity', label: 'Aktivitas' },
  { id: 'facility', label: 'Fasilitas' },
];

export default function PreferencePillPicker({
  selectedActivities = [],
  selectedFacilities = [],
  onActivitiesChange,
  onFacilitiesChange,
  disabled = false,
  maxActivities = 1,
  maxFacilities = MAX_FACILITY_ATTRIBUTES,
}) {
  const [activeTab, setActiveTab] = useState('activity');

  const activityCount = selectedActivities.length;
  const facilityCount = selectedFacilities.length;
  const facilityLimitReached = facilityCount >= maxFacilities;

  const toggleActivity = (value) => {
    if (disabled) return;
    if (selectedActivities.includes(value)) {
      onActivitiesChange([]);
      return;
    }
    onActivitiesChange([value].slice(0, maxActivities));
  };

  const toggleFacility = (value) => {
    if (disabled) return;
    if (selectedFacilities.includes(value)) {
      onFacilitiesChange(selectedFacilities.filter((item) => item !== value));
      return;
    }
    if (facilityLimitReached) return;
    onFacilitiesChange([...selectedFacilities, value].slice(0, maxFacilities));
  };

  return (
    <div className="rounded-2xl border border-gray-200 bg-gray-50/80 p-3 sm:p-4 dark:border-zinc-700 dark:bg-zinc-900/40">
      <div
        role="tablist"
        aria-label="Preferensi pill"
        className="mb-3 flex gap-1 rounded-full bg-white p-1 shadow-sm dark:bg-zinc-800"
      >
        {TABS.map((tab) => {
          const count = tab.id === 'activity' ? activityCount : facilityCount;
          const selected = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={selected}
              disabled={disabled}
              onClick={() => setActiveTab(tab.id)}
              className={`
                flex-1 rounded-full px-3 py-2 text-xs sm:text-sm font-semibold transition-colors
                disabled:opacity-50 disabled:cursor-not-allowed
                ${
                  selected
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-zinc-700'
                }
              `}
            >
              {tab.label}
              {count > 0 ? (
                <span className="ml-1.5 inline-flex min-w-[1.25rem] justify-center rounded-full bg-white/25 px-1 text-[10px] font-bold">
                  {count}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>

      {activeTab === 'activity' && (
        <div role="tabpanel" aria-labelledby="tab-activity" className="space-y-2">
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Pilih satu aktivitas (opsional jika Anda hanya butuh fasilitas).
          </p>
          <div className="flex flex-wrap gap-2 sm:gap-3">
            {CONTEXT_PILL_OPTIONS.map((field) => {
              const isSelected = selectedActivities.includes(field.value);
              const theme = CONTEXT_PILL_THEMES[field.value] || CONTEXT_PILL_THEME_DEFAULT;
              return (
                <button
                  key={field.value}
                  type="button"
                  disabled={disabled}
                  onClick={() => toggleActivity(field.value)}
                  className={`
                    px-3 sm:px-4 py-2 rounded-full text-sm font-semibold
                    transition-shadow duration-200 ease-out
                    focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400
                    disabled:opacity-50 disabled:cursor-not-allowed
                    ${isSelected ? theme.selected : theme.idle}
                  `}
                >
                  {field.label}
                  {isSelected && (
                    <span className="ml-1.5 text-xs opacity-95" aria-hidden>
                      ✓
                    </span>
                  )}
                </button>
              );
            })}
          </div>
          {selectedActivities.length > 0 && (() => {
            const selectedActivity = CONTEXT_PILL_OPTIONS.find(
              (option) => selectedActivities.includes(option.value),
            );
            if (!selectedActivity?.desc) return null;
            return (
              <p className="text-xs sm:text-sm text-gray-600 dark:text-gray-300">
                💡 <span className="font-semibold">{selectedActivity.label}:</span>{' '}
                {selectedActivity.desc}
              </p>
            );
          })()}
        </div>
      )}

      {activeTab === 'facility' && (
        <div role="tabpanel" aria-labelledby="tab-facility" className="space-y-3">
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Pilih fasilitas yang Anda butuhkan (maks. {maxFacilities}, tanpa wajib pilih aktivitas).
          </p>
          {facilityLimitReached && (
            <p className="text-xs font-medium text-amber-600 dark:text-amber-400">
              Batas {maxFacilities} fasilitas — hapus satu untuk menukar.
            </p>
          )}
          {FACILITY_ATTRIBUTE_GROUPS.map((group) => (
            <fieldset key={group.id}>
              <legend className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                {group.label}
              </legend>
              <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
                {group.options.map((option) => {
                  const checked = selectedFacilities.includes(option.value);
                  const blocked = !checked && facilityLimitReached;
                  return (
                    <label
                      key={option.value}
                      className={`
                        flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm select-none transition-colors
                        ${disabled || blocked ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}
                        ${
                          checked
                            ? 'bg-indigo-50 font-medium text-indigo-800 dark:bg-indigo-500/20 dark:text-indigo-200'
                            : 'text-gray-700 hover:bg-white dark:text-gray-300 dark:hover:bg-zinc-800'
                        }
                      `}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={disabled || blocked}
                        onChange={() => toggleFacility(option.value)}
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
          <div className="flex items-center justify-between border-t border-gray-200 pt-2 dark:border-zinc-700">
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {facilityCount > 0
                ? `${facilityCount}/${maxFacilities} fasilitas dipilih`
                : 'Belum ada fasilitas dipilih'}
            </span>
            <button
              type="button"
              disabled={disabled || facilityCount === 0}
              onClick={() => onFacilitiesChange([])}
              className="rounded-full px-3 py-1.5 text-xs font-semibold text-gray-600 hover:bg-gray-100 disabled:opacity-50 dark:text-gray-300 dark:hover:bg-zinc-800"
            >
              Reset fasilitas
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

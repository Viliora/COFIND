import React, { useMemo, useState } from 'react';

const POPULAR_FOR_LABELS = {
  breakfast: 'Sarapan',
  lunch: 'Makan siang',
  dinner: 'Makan malam',
  brunch: 'Brunch',
  solo_dining: 'Makan sendiri',
  good_for_working_on_laptop: 'WFC / kerja laptop',
  good_for_kids: 'Ramah anak',
  good_for_groups: 'Berkelompok',
};

const POPULAR_FOR_ORDER = [
  'breakfast',
  'brunch',
  'lunch',
  'dinner',
  'solo_dining',
  'good_for_working_on_laptop',
  'good_for_groups',
  'good_for_kids',
];

const HIGHLIGHT_LABELS = {
  good_coffee: 'Kopi enak',
  good_desserts: 'Dessert enak',
  good_tea_selection: 'Pilihan teh beragam',
  sports: 'Cocok nonton olahraga',
  live_music: 'Live music',
  fast_service: 'Layanan cepat',
  great_cocktails: 'Cocktail recommended',
};

const HIGHLIGHT_ORDER = [
  'good_coffee',
  'good_desserts',
  'good_tea_selection',
  'live_music',
  'sports',
];

function titleCaseWords(text) {
  return String(text || '')
    .split(' ')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function toReadableLabel(key, labels = {}) {
  if (!key) return '';
  if (labels[key]) return labels[key];
  return titleCaseWords(String(key).replace(/_/g, ' '));
}

function orderedTrueKeys(sourceObj, preferredOrder = []) {
  if (!sourceObj || typeof sourceObj !== 'object') return [];
  const keys = Object.entries(sourceObj)
    .filter(([, value]) => value === true)
    .map(([key]) => key);

  const orderIndex = (key) => {
    const i = preferredOrder.indexOf(key);
    return i === -1 ? preferredOrder.length : i;
  };

  return keys.sort((a, b) => orderIndex(a) - orderIndex(b) || a.localeCompare(b));
}

const FacilitiesTab = ({ facilities }) => {
  const popularForItems = useMemo(() => {
    const keys = orderedTrueKeys(facilities?.popular_for, POPULAR_FOR_ORDER);
    return keys.map((key) => toReadableLabel(key, POPULAR_FOR_LABELS));
  }, [facilities?.popular_for]);

  const highlightItems = useMemo(() => {
    const keys = orderedTrueKeys(facilities?.highlights, HIGHLIGHT_ORDER);
    return keys.map((key) => toReadableLabel(key, HIGHLIGHT_LABELS));
  }, [facilities?.highlights]);

  const atmosphereItems = useMemo(() => {
    const source = Array.isArray(facilities?.atmosphere) ? facilities.atmosphere : [];
    return source
      .map((item) => String(item || '').trim())
      .filter(Boolean)
      .map((item) => toReadableLabel(item));
  }, [facilities?.atmosphere]);

  const hasAnyData = (
    popularForItems.length > 0
    || highlightItems.length > 0
    || atmosphereItems.length > 0
  );

  const tabConfigs = useMemo(() => ([
    {
      key: 'popular_for',
      label: 'Populer',
      items: popularForItems,
      emptyText: 'Belum ada data populer untuk.',
      pillClassName: 'border border-amber-200/90 bg-white text-amber-900 dark:border-amber-800/60 dark:bg-zinc-800 dark:text-amber-100',
      iconContainerClassName: 'bg-gradient-to-br from-amber-400 to-orange-500 text-white',
      icon: (
        <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20" aria-hidden>
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
      ),
    },
    {
      key: 'highlights',
      label: 'Keunggulan',
      items: highlightItems,
      emptyText: 'Belum ada data highlights.',
      pillClassName: 'border border-indigo-200/90 bg-white text-indigo-900 dark:border-indigo-800/60 dark:bg-zinc-800 dark:text-indigo-100',
      iconContainerClassName: 'bg-gradient-to-br from-indigo-500 to-violet-500 text-white',
      icon: (
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      ),
    },
    {
      key: 'atmosphere',
      label: 'Suasana',
      items: atmosphereItems,
      emptyText: 'Belum ada data suasana.',
      pillClassName: 'border border-emerald-200/90 bg-white text-emerald-900 dark:border-emerald-800/60 dark:bg-zinc-800 dark:text-emerald-100',
      iconContainerClassName: 'bg-gradient-to-br from-emerald-500 to-teal-500 text-white',
      icon: (
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.868v4.264a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
  ]), [popularForItems, highlightItems, atmosphereItems]);

  const availableTabs = useMemo(
    () => tabConfigs.filter((tab) => tab.items.length > 0),
    [tabConfigs]
  );
  const [selectedTab, setSelectedTab] = useState('popular_for');

  const activeTab = useMemo(() => {
    const activeKeyExists = availableTabs.some((tab) => tab.key === selectedTab);
    if (activeKeyExists) {
      return availableTabs.find((tab) => tab.key === selectedTab);
    }
    return availableTabs[0] || tabConfigs[0];
  }, [availableTabs, selectedTab, tabConfigs]);

  if (!facilities) {
    return (
      <div className="text-center py-10 px-4 text-gray-500 dark:text-gray-400">
        <svg className="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p className="text-sm">Informasi belum tersedia</p>
      </div>
    );
  }

  if (!hasAnyData) {
    return (
      <div className="rounded-2xl border border-dashed border-gray-200 dark:border-zinc-600 bg-gray-50/80 dark:bg-zinc-900/40 px-6 py-10 text-center">
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Informasi fasilitas dan suasana belum tersedia untuk tempat ini.
        </p>
      </div>
    );
  }

  return (
    <div className="relative overflow-hidden rounded-2xl border border-amber-100/80 dark:border-amber-900/40 bg-gradient-to-br from-amber-50/90 via-white to-orange-50/50 dark:from-amber-950/30 dark:via-zinc-900 dark:to-orange-950/20 shadow-sm">
      <div
        className="pointer-events-none absolute -right-16 -top-16 h-40 w-40 rounded-full bg-amber-200/30 dark:bg-amber-500/10 blur-2xl"
        aria-hidden
      />
      <div className="relative p-4 sm:p-6">
        <div className="mb-4 flex flex-wrap gap-2">
          {tabConfigs.map((tab) => {
            const isActive = activeTab?.key === tab.key;
            const isDisabled = tab.items.length === 0;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => !isDisabled && setSelectedTab(tab.key)}
                disabled={isDisabled}
                className={[
                  'inline-flex items-center gap-2 rounded-full px-3.5 py-2 text-xs sm:text-sm font-medium transition-all',
                  isActive
                    ? 'bg-gray-900 text-white shadow dark:bg-white dark:text-zinc-900'
                    : 'bg-white/80 text-gray-700 border border-gray-200 dark:bg-zinc-800 dark:text-gray-200 dark:border-zinc-700',
                  isDisabled ? 'opacity-45 cursor-not-allowed' : 'hover:shadow-sm',
                ].join(' ')}
              >
                <span className={`inline-flex h-5 w-5 items-center justify-center rounded-full ${tab.iconContainerClassName}`}>
                  {tab.icon}
                </span>
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="rounded-2xl border border-gray-200/80 dark:border-zinc-700/80 bg-white/80 dark:bg-zinc-900/50 p-4 sm:p-5 shadow-sm">
          <div className="flex items-center gap-2.5 mb-3">
            <span className={`inline-flex h-8 w-8 items-center justify-center rounded-lg ${activeTab.iconContainerClassName}`}>
              {activeTab.icon}
            </span>
            <h3 className="text-sm sm:text-base font-semibold text-gray-900 dark:text-gray-100">{activeTab.label}</h3>
          </div>

          {activeTab.items.length > 0 ? (
            <ul className="flex flex-wrap gap-2.5">
              {activeTab.items.map((item) => (
                <li key={`${activeTab.key}-${item}`}>
                  <span className={`inline-flex items-center rounded-full px-3 py-1.5 text-xs sm:text-sm font-medium ${activeTab.pillClassName}`}>
                    {item}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs sm:text-sm text-gray-500 dark:text-gray-400">{activeTab.emptyText}</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default FacilitiesTab;

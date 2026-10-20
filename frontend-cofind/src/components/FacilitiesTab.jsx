import React, { useMemo, useState } from 'react';
import { FACILITY_TAB_SPECS } from '../config/facilityTabsConfig';
import { buildFacilityTabItems } from '../utils/facilityTabItems';
import { isLikelyEnglishFacilityText } from '../utils/facilityLabelsId';

const FacilitiesTab = ({ facilities, googleSnapshot }) => {
  const itemsByTabId = useMemo(
    () => buildFacilityTabItems(facilities, googleSnapshot),
    [facilities, googleSnapshot],
  );

  const tabConfigs = useMemo(
    () =>
      FACILITY_TAB_SPECS.map((spec) => ({
        key: spec.id,
        label: spec.label,
        items: itemsByTabId[spec.id] || [],
        emptyText: spec.emptyText,
        pillClassName: spec.pillClassName,
        iconContainerClassName: spec.iconContainerClassName,
        icon: <span className="text-sm leading-none" aria-hidden>{spec.emoji}</span>,
      })),
    [itemsByTabId],
  );

  const editorialRaw = (googleSnapshot?.editorial_summary || '').trim();
  const editorial = editorialRaw && !isLikelyEnglishFacilityText(editorialRaw) ? editorialRaw : '';

  const hasAnyData = tabConfigs.some((tab) => tab.items.length > 0) || editorial;

  const availableTabs = useMemo(
    () => tabConfigs.filter((tab) => tab.items.length > 0),
    [tabConfigs],
  );

  const [selectedTab, setSelectedTab] = useState(FACILITY_TAB_SPECS[0]?.id || 'accessibility');

  const activeTab = useMemo(() => {
    const activeKeyExists = availableTabs.some((tab) => tab.key === selectedTab);
    if (activeKeyExists) {
      return availableTabs.find((tab) => tab.key === selectedTab);
    }
    return availableTabs[0] || tabConfigs[0];
  }, [availableTabs, selectedTab, tabConfigs]);

  if (!facilities && !googleSnapshot) {
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
          Informasi fasilitas belum tersedia untuk tempat ini.
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
        {editorial && (
          <p className="mb-4 text-sm text-gray-700 dark:text-gray-300 leading-relaxed border-l-4 border-amber-400 pl-3">
            {editorial}
          </p>
        )}

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

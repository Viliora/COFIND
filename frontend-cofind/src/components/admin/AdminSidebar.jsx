import React from 'react';

export default function AdminSidebar({ items, activeSection, onChangeSection }) {
  return (
    <aside className="w-full lg:w-64 shrink-0 rounded-2xl border border-amber-100 dark:border-gray-800 bg-white dark:bg-black shadow-sm overflow-hidden">
      <div className="px-5 py-5 bg-gradient-to-br from-amber-600 to-amber-700 dark:from-gray-950 dark:to-black border-b border-transparent dark:border-gray-800">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-2xl">☕</span>
          <h1 className="text-lg font-bold text-white tracking-wide">Cofind Admin</h1>
        </div>
        <p className="text-xs text-amber-100">Dashboard pengelolaan aplikasi</p>
      </div>

      <nav className="p-2 space-y-0.5">
        {items.map((item) => {
          const isActive = activeSection === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onChangeSection(item.id)}
              className={`w-full rounded-xl px-4 py-2.5 text-left transition-all ${
                isActive
                  ? 'bg-amber-50 dark:bg-gray-900 text-amber-700 dark:text-amber-300 font-semibold border border-amber-200 dark:border-gray-700'
                  : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-950 hover:text-gray-900 dark:hover:text-white border border-transparent'
              }`}
            >
              <div className="text-sm">{item.label}</div>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}

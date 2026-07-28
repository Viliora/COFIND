import React from 'react';

export default function AdminSidebar({ items, activeSection, onChangeSection }) {
  return (
    <aside className="w-full lg:w-64 shrink-0 rounded-2xl border border-stone-200/50 bg-[#FAF9F6]/95 shadow-[0_8px_30px_rgb(0,0,0,0.04)] overflow-hidden">
      <div className="px-5 py-5 bg-gradient-to-br from-amber-700 to-orange-800">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-2xl">☕</span>
          <h1 className="font-serif text-lg font-semibold text-stone-50 tracking-wide">Cofind Admin</h1>
        </div>
        <p className="text-xs text-amber-100/90">Dashboard pengelolaan aplikasi</p>
      </div>

      <nav className="p-2 space-y-0.5">
        {items.map((item) => {
          const isActive = activeSection === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onChangeSection(item.id)}
              className={`w-full rounded-xl px-4 py-2.5 text-left transition-all duration-300 ease-out cursor-pointer ${
                isActive
                  ? 'bg-amber-50 text-amber-800 font-semibold border border-amber-200/70 shadow-[0_8px_30px_rgb(0,0,0,0.03)]'
                  : 'text-stone-600 hover:bg-stone-100/70 hover:text-stone-900 border border-transparent'
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

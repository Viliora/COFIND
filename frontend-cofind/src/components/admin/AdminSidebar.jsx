import React from 'react';

export default function AdminSidebar({ items, activeSection, onChangeSection }) {
  return (
    <aside className="w-full shrink-0 overflow-hidden rounded-panel border border-cofind-rule bg-cofind-surface shadow-cofind-sm lg:w-64">
      <div className="bg-cofind-primary px-5 py-5">
        <div className="mb-1 flex items-center gap-2">
          <span className="text-2xl" aria-hidden>
            ☕
          </span>
          <h1 className="font-display text-lg font-semibold tracking-wide text-cofind-on-primary">
            Cofind Admin
          </h1>
        </div>
        <p className="text-xs text-cofind-on-primary/85">Dashboard pengelolaan aplikasi</p>
      </div>

      <nav className="space-y-0.5 p-2">
        {items.map((item) => {
          const isActive = activeSection === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onChangeSection(item.id)}
              className={`w-full cursor-pointer rounded-panel border px-4 py-2.5 text-left transition-colors duration-200 ${
                isActive
                  ? 'border-cofind-rule bg-cofind-paper font-semibold text-cofind-primary shadow-cofind-sm'
                  : 'border-transparent text-cofind-muted hover:bg-cofind-paper hover:text-cofind-ink'
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
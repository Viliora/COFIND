import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ensureCoffeeShopImageMap, getCoffeeShopImage } from '../utils/coffeeShopImages';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';

async function fetchLatestReviews() {
  const urls = [
    `${API_BASE}/api/reviews/latest?limit=10`,
    `${API_BASE}/api/reviews?limit=10`,
  ];
  for (const url of urls) {
    try {
      const res = await fetch(url);
      const data = await res.json().catch(() => null);
      if (res.ok && data?.status === 'success') {
        return Array.isArray(data.items) ? data.items : [];
      }
    } catch {
      // coba URL berikutnya
    }
  }
  return [];
}

export default function LatestReviewsAside({ className = '' }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      try {
        const reviews = await fetchLatestReviews();
        if (cancelled) return;
        ensureCoffeeShopImageMap(reviews.map((item) => ({ place_id: item.place_id })));
        setItems(reviews);
      } catch {
        if (!cancelled) setItems([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <aside
      className={`rounded-2xl border border-stone-200 bg-white dark:border-stone-700 dark:bg-stone-900 px-3 py-3 sm:px-4 sm:py-4 ${className}`}
    >
      <h2 className="font-sans text-lg font-bold tracking-tight text-slate-800 dark:text-stone-100">
        Latest Reviews
      </h2>
      <div className="mt-1.5 h-px w-full bg-gradient-to-r from-slate-500 via-slate-200 to-transparent dark:from-stone-400 dark:via-stone-700" />

      {loading ? (
        <p className="py-8 text-sm text-stone-400">Memuat ulasan...</p>
      ) : items.length === 0 ? (
        <p className="py-8 text-sm text-stone-400">Belum ada ulasan.</p>
      ) : (
        <ul className="mt-3 space-y-2.5">
          {items.map((item, index) => {
            const shopImage = getCoffeeShopImage(item.place_id);
            const reviewer = item.username || 'Anonim';
            const card = (
              <div className="flex gap-2.5">
                <img
                  src={shopImage}
                  alt=""
                  className="h-11 w-11 flex-shrink-0 rounded-full object-cover bg-stone-100 dark:bg-stone-800"
                />
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-sm leading-snug text-[#0f766e] dark:text-teal-300">
                    {item.shop_name}
                  </p>
                  <p className="mt-0.5 text-xs leading-snug text-stone-500 dark:text-stone-400 line-clamp-2">
                    {item.address || 'Pontianak'}
                  </p>
                  <p className="mt-2 text-right text-[11px] text-stone-400">
                    by {reviewer}
                  </p>
                </div>
              </div>
            );

            return (
              <li key={item.id || `${item.place_id}-${index}`}>
                {item.place_id ? (
                  <Link
                    to={`/shop/${encodeURIComponent(item.place_id)}`}
                    className="block rounded-xl border border-stone-200 bg-white p-2.5 transition-colors hover:border-stone-300 hover:bg-stone-50 dark:border-stone-700 dark:bg-stone-900 dark:hover:border-stone-600 dark:hover:bg-stone-800/60"
                  >
                    {card}
                  </Link>
                ) : (
                  <div className="rounded-xl border border-stone-200 bg-white p-2.5 dark:border-stone-700 dark:bg-stone-900">
                    {card}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </aside>
  );
}

export function PageWithLatestReviews({ children, className = '' }) {
  return (
    <div className={`grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_300px] gap-6 lg:gap-8 items-start ${className}`}>
      <div className="min-w-0 overflow-x-hidden">{children}</div>
      <LatestReviewsAside className="lg:sticky lg:top-24" />
    </div>
  );
}

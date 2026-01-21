import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/authContext';
import CoffeeShopCard from '../components/CoffeeShopCard';
import { ensureCoffeeShopImageMap } from '../utils/coffeeShopImages';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';

const WantToVisit = () => {
  const { isAuthenticated, user } = useAuth();
  const [wantToVisitShops, setWantToVisitShops] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  // ✅ OPTIMIZED: Wrapped dengan useCallback untuk mencegah re-creation setiap render
  const loadWantToVisit = useCallback(async () => {
    try {
      setIsLoading(true);
      
      if (isAuthenticated && user?.id) {
        const response = await fetch(`${API_BASE}/api/users/${user.id}/want-to-visit`, {
          method: 'GET'
        });
        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }
        const payload = await response.json();
        const wantList = Array.isArray(payload.want_to_visit) ? payload.want_to_visit : [];
        const shops = wantList
          .filter(item => item.shop)
          .map(item => ({
            place_id: item.place_id,
            name: item.shop.name,
            address: item.shop.address,
            vicinity: item.shop.address,
            rating: item.shop.rating,
            user_ratings_total: item.shop.user_ratings_total
          }));
        ensureCoffeeShopImageMap(shops);
        setWantToVisitShops(shops);
        setIsLoading(false);
        return;
      }

      // Guest mode: localStorage fallback
      const wantToVisitPlaceIds = JSON.parse(localStorage.getItem('wantToVisitShops') || '[]');
      if (wantToVisitPlaceIds.length === 0) {
        setWantToVisitShops([]);
        setIsLoading(false);
        return;
      }

      const response = await fetch(`${API_BASE}/api/coffeeshops`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      });
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      const payload = await response.json();
      const all = Array.isArray(payload.data) ? payload.data : [];
      const shops = all.filter(shop => wantToVisitPlaceIds.includes(shop.place_id));
      ensureCoffeeShopImageMap(shops);
      setWantToVisitShops(shops);
      setIsLoading(false);
    } catch (err) {
      console.error('[WantToVisit] Error loading want-to-visit:', err);
      setIsLoading(false);
    }
  }, [isAuthenticated, user?.id]); // ✅ Dependencies yang benar

  // ✅ OPTIMIZED: useEffect dengan dependency array yang benar
  useEffect(() => {
    loadWantToVisit();
  }, [loadWantToVisit]); // ✅ Sekarang aman karena fungsi sudah di-wrap dengan useCallback

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-zinc-900 py-6 sm:py-8 px-3 sm:px-4 md:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <p className="text-center text-lg text-gray-600 dark:text-gray-400">Memuat want to visit...</p>
        </div>
      </div>
    );
  }

  if (wantToVisitShops.length === 0) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-zinc-900 py-6 sm:py-8 px-3 sm:px-4 md:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center py-8 sm:py-12 md:py-16">
            <svg
              className="mx-auto h-16 w-16 sm:h-20 sm:w-20 md:h-24 md:w-24 text-blue-400 dark:text-blue-500"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="1.5"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"></path>
            </svg>
            <h1 className="mt-4 sm:mt-6 text-2xl sm:text-3xl md:text-4xl font-bold text-gray-900 dark:text-white px-4">
              Belum Ada Coffee Shop
            </h1>
            <p className="mt-3 sm:mt-4 text-base sm:text-lg text-gray-600 dark:text-gray-400 px-4">
              Tandai coffee shop yang ingin Anda kunjungi!
            </p>
            <Link
              to="/"
              className="inline-block mt-6 px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
            >
              Jelajahi Coffee Shop
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Guest access - show login prompt
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-zinc-900 py-6 sm:py-8 px-3 sm:px-4 md:px-6 lg:px-8">
        <div className="max-w-2xl mx-auto text-center py-12">
          <div className="w-20 h-20 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg className="w-10 h-10 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
            Login Diperlukan
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mb-8">
            Silakan login untuk melihat dan mengelola daftar coffee shop yang ingin Anda kunjungi.
          </p>
          <Link
            to="/login"
            className="inline-flex items-center gap-2 px-6 py-3 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors font-semibold"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
            </svg>
            Masuk / Daftar
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-zinc-900 py-6 sm:py-8 px-3 sm:px-4 md:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold text-gray-900 dark:text-white mb-2 flex items-center gap-3">
            <svg className="w-8 h-8 sm:w-10 sm:h-10 text-blue-500" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"></path>
            </svg>
            Want to Visit
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            {wantToVisitShops.length} coffee shop yang ingin Anda kunjungi
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 sm:gap-6">
          {wantToVisitShops.map((shop) => (
            <div key={shop.place_id}>
              <CoffeeShopCard shop={shop} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default WantToVisit;

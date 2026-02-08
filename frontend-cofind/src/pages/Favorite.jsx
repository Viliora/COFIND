import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/authContext';
import CoffeeShopCard from '../components/CoffeeShopCard';
import { ensureCoffeeShopImageMap } from '../utils/coffeeShopImages';
import { getPersonalizedRecommendations } from '../utils/personalizedRecommendations';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';

const Favorite = () => {
  const { isAuthenticated, user } = useAuth();
  const [favoriteShops, setFavoriteShops] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [allShops, setAllShops] = useState([]); // Semua coffee shops untuk recommendations

  // Load semua coffee shops untuk recommendations
  const loadAllShops = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/coffeeshops`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      });
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      const payload = await response.json();
      if (payload?.status === 'success' && Array.isArray(payload.data)) {
        setAllShops(payload.data);
      }
    } catch (error) {
      console.error('[Favorite] Error loading all shops:', error);
    }
  }, []);

  const loadFavorites = useCallback(async () => {
    try {
      setIsLoading(true);
      
      if (isAuthenticated && user?.id) {
        const response = await fetch(`${API_BASE}/api/users/${user.id}/favorites`, {
          method: 'GET'
        });
        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }
        const payload = await response.json();
        const favorites = Array.isArray(payload.favorites) ? payload.favorites : [];
        const shops = favorites
          .filter(fav => fav.shop)
          .map(fav => ({
            place_id: fav.place_id,
            name: fav.shop.name,
            address: fav.shop.address,
            vicinity: fav.shop.address,
            rating: fav.shop.rating,
            user_ratings_total: fav.shop.user_ratings_total,
            photos: fav.shop.photos || null
          }));

        ensureCoffeeShopImageMap(shops);
        setFavoriteShops(shops);
        setIsLoading(false);
        return;
      }

      // Guest mode: localStorage fallback
      const favoritePlaceIds = JSON.parse(localStorage.getItem('favoriteShops') || '[]');
      if (favoritePlaceIds.length === 0) {
        setFavoriteShops([]);
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
      const shops = all.filter(shop => favoritePlaceIds.includes(shop.place_id));
      ensureCoffeeShopImageMap(shops);
      setFavoriteShops(shops);
      setIsLoading(false);
    } catch (err) {
      console.error('Error loading favorites:', err);
      setIsLoading(false);
    }
  }, [isAuthenticated, user?.id]);

  useEffect(() => {
    loadFavorites();
    loadAllShops();
  }, [isAuthenticated, user?.id, loadFavorites, loadAllShops]);

  // Title halaman
  useEffect(() => {
    document.title = 'Favorit - Cofind';
    return () => { document.title = 'Cofind'; };
  }, []);

  // Generate Personalized Recommendations berdasarkan favorit
  const personalizedRecommendations = useMemo(() => {
    if (favoriteShops.length === 0 || allShops.length === 0) return [];
    
    try {
      const recommendations = getPersonalizedRecommendations(
        favoriteShops,
        allShops,
        {
          maxResults: 8,
          minRating: 4.0,
          excludeFavorites: true,
          weightFeatures: 0.7, // 70% fokus pada context similarity
          weightRating: 0.2,
          weightLocation: 0.1,
        }
      );
      
      return recommendations;
    } catch (error) {
      console.error('[Favorite] Error generating personalized recommendations:', error);
      return [];
    }
  }, [favoriteShops, allShops]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-zinc-900 py-6 sm:py-8 px-3 sm:px-4 md:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <p className="text-center text-lg text-gray-600 dark:text-gray-400">Memuat favorit...</p>
        </div>
      </div>
    );
  }

  if (favoriteShops.length === 0) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-zinc-900 py-6 sm:py-8 px-3 sm:px-4 md:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center py-8 sm:py-12 md:py-16">
            <svg
              className="mx-auto h-16 w-16 sm:h-20 sm:w-20 md:h-24 md:w-24 text-rose-400 dark:text-rose-500"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="1.5"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"></path>
            </svg>
            <h1 className="mt-4 sm:mt-6 text-2xl sm:text-3xl md:text-4xl font-bold text-gray-900 dark:text-white px-4">
              Belum Ada Favorit
            </h1>
            <p className="mt-3 sm:mt-4 text-base sm:text-lg text-gray-600 dark:text-gray-400 px-4">
              Mulai tambahkan coffee shop favorit Anda!
            </p>
            <div className="mt-6 flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4">
              <Link
                to="/"
                className="inline-flex items-center justify-center px-6 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium"
              >
                Jelajahi Coffee Shop
              </Link>
              <Link
                to="/login"
                className="inline-flex items-center justify-center px-6 py-2.5 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-2 border-gray-300 dark:border-gray-600 rounded-lg hover:border-indigo-500 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors font-medium"
              >
                Login untuk melihat coffee shop favorit-mu!
              </Link>
            </div>
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
          <div className="w-20 h-20 bg-amber-100 dark:bg-amber-900/30 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg className="w-10 h-10 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
            Login Diperlukan
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mb-8">
            Silakan login untuk melihat dan mengelola coffee shop favorit Anda.
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
          <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold text-gray-900 dark:text-white mb-2">
            ❤️ Favorit Saya
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            {favoriteShops.length} coffee shop yang Anda sukai
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 sm:gap-6">
          {favoriteShops.map((shop) => (
            <div key={shop.place_id}>
              <CoffeeShopCard shop={shop} />
            </div>
          ))}
        </div>

        {/* Personalized Recommendations - Berdasarkan kemiripan konteks review */}
        {personalizedRecommendations.length > 0 && (
          <div className="mt-12">
            <div className="mb-6">
              <h2 className="text-xl sm:text-2xl md:text-3xl font-bold text-gray-800 dark:text-gray-200 flex items-center gap-2 mb-2">
                <span className="text-2xl">✨</span>
                Rekomendasi untuk Anda
              </h2>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Coffee shop dengan review yang mirip dengan favorit Anda
              </p>
            </div>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 sm:gap-6">
              {personalizedRecommendations.map((shop) => (
                <div
                  key={shop.place_id}
                  className="block hover:shadow-2xl transition duration-300"
                >
                  <CoffeeShopCard shop={shop} />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Favorite;

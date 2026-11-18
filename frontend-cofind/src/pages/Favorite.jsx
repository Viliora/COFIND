import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/authContext';
import CoffeeShopCard, { SHOP_CATALOG_GRID_CLASS } from '../components/CoffeeShopCard';
import { ensureCoffeeShopImageMap } from '../utils/coffeeShopImages';
import {
  CollectionEmptyState,
  CollectionLoading,
  CollectionLoginGate,
  CollectionPageHeader,
  CollectionPageLayout,
} from '../components/CollectionPageLayout';

import { API_BASE } from '../config/apiBase.js';
import { authService } from '../services/authService';

const Favorite = () => {
  const { isAuthenticated, user } = useAuth();
  const [favoriteShops, setFavoriteShops] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  const loadFavorites = useCallback(async () => {
    try {
      setIsLoading(true);

      if (isAuthenticated && user?.id) {
        const response = await fetch(`${API_BASE}/api/users/${user.id}/favorites`, {
          method: 'GET',
          headers: authService.getAuthHeaders(),
        });
        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }
        const payload = await response.json();
        const favorites = Array.isArray(payload.favorites) ? payload.favorites : [];
        const shops = favorites
          .filter((fav) => fav.shop)
          .map((fav) => ({
            place_id: fav.place_id,
            name: fav.shop.name,
            address: fav.shop.address,
            vicinity: fav.shop.address,
            rating: fav.shop.rating,
            user_ratings_total: fav.shop.user_ratings_total,
            photos: fav.shop.photos || null,
          }));

        ensureCoffeeShopImageMap(shops);
        setFavoriteShops(shops);
        setIsLoading(false);
        return;
      }

      const favoritePlaceIds = JSON.parse(localStorage.getItem('favoriteShops') || '[]');
      if (favoritePlaceIds.length === 0) {
        setFavoriteShops([]);
        setIsLoading(false);
        return;
      }

      const response = await fetch(`${API_BASE}/api/coffeeshops`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      const payload = await response.json();
      const all = Array.isArray(payload.data) ? payload.data : [];
      const shops = all.filter((shop) => favoritePlaceIds.includes(shop.place_id));
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
  }, [isAuthenticated, user?.id, loadFavorites]);

  useEffect(() => {
    document.title = 'Favorit - Cofind';
    return () => {
      document.title = 'Cofind';
    };
  }, []);

  if (isLoading) {
    return <CollectionLoading message="Memuat favorit..." />;
  }

  if (favoriteShops.length === 0) {
    return (
      <CollectionEmptyState
        icon={
          <svg
            className="mx-auto h-16 w-16 text-cofind-primary sm:h-20 sm:w-20 md:h-24 md:w-24"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="1.5"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden
          >
            <path d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
          </svg>
        }
        title="Belum Ada Favorit"
        description="Mulai tambahkan coffee shop favorit Anda!"
        primaryTo="/"
        primaryLabel="Jelajahi Coffee Shop"
        secondaryTo="/login"
        secondaryLabel="Login untuk melihat coffee shop favorit-mu!"
      />
    );
  }

  if (!isAuthenticated) {
    return (
      <CollectionLoginGate
        title="Login Diperlukan"
        description="Silakan login untuk melihat dan mengelola coffee shop favorit Anda."
      />
    );
  }

  return (
    <CollectionPageLayout>
      <CollectionPageHeader
        title="Favorit Saya"
        subtitle={`${favoriteShops.length} coffee shop yang Anda sukai`}
        icon={
          <span className="text-2xl sm:text-3xl" aria-hidden>
            ❤️
          </span>
        }
      />
      <div className={SHOP_CATALOG_GRID_CLASS}>
        {favoriteShops.map((shop) => (
          <div key={shop.place_id}>
            <CoffeeShopCard shop={shop} />
          </div>
        ))}
      </div>
    </CollectionPageLayout>
  );
};

export default Favorite;
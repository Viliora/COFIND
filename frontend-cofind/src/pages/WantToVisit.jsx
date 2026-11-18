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

const WantToVisit = () => {
  const { isAuthenticated, user } = useAuth();
  const [wantToVisitShops, setWantToVisitShops] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  const loadWantToVisit = useCallback(async () => {
    try {
      setIsLoading(true);

      if (isAuthenticated && user?.id) {
        const response = await fetch(`${API_BASE}/api/users/${user.id}/want-to-visit`, {
          method: 'GET',
        });
        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }
        const payload = await response.json();
        const wantList = Array.isArray(payload.want_to_visit) ? payload.want_to_visit : [];
        const shops = wantList
          .filter((item) => item.shop)
          .map((item) => ({
            place_id: item.place_id,
            name: item.shop.name,
            address: item.shop.address,
            vicinity: item.shop.address,
            rating: item.shop.rating,
            user_ratings_total: item.shop.user_ratings_total,
          }));
        ensureCoffeeShopImageMap(shops);
        setWantToVisitShops(shops);
        setIsLoading(false);
        return;
      }

      const wantToVisitPlaceIds = JSON.parse(localStorage.getItem('wantToVisitShops') || '[]');
      if (wantToVisitPlaceIds.length === 0) {
        setWantToVisitShops([]);
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
      const shops = all.filter((shop) => wantToVisitPlaceIds.includes(shop.place_id));
      ensureCoffeeShopImageMap(shops);
      setWantToVisitShops(shops);
      setIsLoading(false);
    } catch (err) {
      console.error('[WantToVisit] Error loading want-to-visit:', err);
      setIsLoading(false);
    }
  }, [isAuthenticated, user?.id]);

  useEffect(() => {
    loadWantToVisit();
  }, [loadWantToVisit]);

  useEffect(() => {
    document.title = 'Tempat yang Ingin Dikunjungi - Cofind';
    return () => {
      document.title = 'Cofind';
    };
  }, []);

  if (isLoading) {
    return <CollectionLoading message="Memuat want to visit..." />;
  }

  if (wantToVisitShops.length === 0) {
    return (
      <CollectionEmptyState
        icon={
          <svg
            className="mx-auto h-16 w-16 text-cofind-secondary sm:h-20 sm:w-20 md:h-24 md:w-24"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="1.5"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden
          >
            <path d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
          </svg>
        }
        title="Belum Ada Coffee Shop"
        description="Tandai coffee shop yang ingin Anda kunjungi!"
        primaryTo="/"
        primaryLabel="Jelajahi Coffee Shop"
        secondaryTo="/login"
        secondaryLabel="Login untuk melihat coffee shop yang ingin kamu kunjungi!"
      />
    );
  }

  if (!isAuthenticated) {
    return (
      <CollectionLoginGate
        title="Login Diperlukan"
        description="Silakan login untuk melihat dan mengelola daftar coffee shop yang ingin Anda kunjungi."
      />
    );
  }

  return (
    <CollectionPageLayout>
      <CollectionPageHeader
        title="Want to Visit"
        subtitle={`${wantToVisitShops.length} coffee shop yang ingin Anda kunjungi`}
        icon={
          <svg
            className="h-8 w-8 text-cofind-secondary sm:h-10 sm:w-10"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden
          >
            <path d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
          </svg>
        }
      />
      <div className={SHOP_CATALOG_GRID_CLASS}>
        {wantToVisitShops.map((shop) => (
          <div key={shop.place_id}>
            <CoffeeShopCard shop={shop} />
          </div>
        ))}
      </div>
    </CollectionPageLayout>
  );
};

export default WantToVisit;
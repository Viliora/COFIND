import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import CoffeeShopCard from '../components/CoffeeShopCard';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';
const USE_API = import.meta.env.VITE_USE_API === 'true';

const WantToVisit = () => {
  const [wantToVisitShops, setWantToVisitShops] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadWantToVisit();
  }, []);

  const loadWantToVisit = async () => {
    try {
      setIsLoading(true);
      // Get list of want-to-visit place_ids from localStorage
      const wantToVisit = JSON.parse(localStorage.getItem('wantToVisitShops') || '[]');
      
      if (wantToVisit.length === 0) {
        setWantToVisitShops([]);
        setIsLoading(false);
        return;
      }

      // Load full shop data for each want-to-visit
      let shops = [];

      if (USE_API) {
        // Try to get details from backend for each want-to-visit
        for (const placeId of wantToVisit) {
          try {
            console.log(`[WantToVisit] Fetching details for place_id: ${placeId}`);
            const response = await fetch(`${API_BASE}/api/coffeeshops/detail/${placeId}`);
            const data = await response.json();
            
            console.log(`[WantToVisit] Response for ${placeId}:`, data);
            
            if (data.status === 'success' && data.data) {
              const detail = data.data;
              
              // Pastikan photos adalah array of URLs (bukan objects)
              let photoUrls = [];
              if (Array.isArray(detail.photos)) {
                // Photos sudah dalam format URL string dari backend
                photoUrls = detail.photos.slice(0, 1); // Ambil 1 foto pertama
                console.log(`[WantToVisit] Photos for ${detail.name}:`, photoUrls);
              }
              
              const shop = {
                place_id: placeId,
                name: detail.name,
                address: detail.formatted_address,
                vicinity: detail.formatted_address,
                rating: detail.rating,
                user_ratings_total: detail.user_ratings_total,
                location: detail.geometry?.location,
                business_status: detail.business_status,
                price_level: detail.price_level,
                photos: photoUrls,
              };
              
              console.log(`[WantToVisit] Shop data prepared:`, shop);
              shops.push(shop);
            }
          } catch (err) {
            console.error(`[WantToVisit] Error loading want-to-visit ${placeId}:`, err);
          }
        }
      }
      
      console.log(`[WantToVisit] Total shops loaded: ${shops.length}`);
      setWantToVisitShops(shops);
      setIsLoading(false);
    } catch (err) {
      console.error('[WantToVisit] Error loading want-to-visit:', err);
      setIsLoading(false);
    }
  };

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
            <Link key={shop.place_id} to={`/shop/${shop.place_id}`}>
              <CoffeeShopCard shop={shop} />
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
};

export default WantToVisit;


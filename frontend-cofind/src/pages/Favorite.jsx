import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import CoffeeShopCard from '../components/CoffeeShopCard';
import localPlacesData from '../data/places.json';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';
const USE_API = import.meta.env.VITE_USE_API === 'true';
const USE_LOCAL_DATA = true; // Set true untuk menggunakan data lokal JSON

const Favorite = () => {
  const [favoriteShops, setFavoriteShops] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadFavorites();
  }, []);

  const loadFavorites = async () => {
    try {
      setIsLoading(true);
      // Get list of favorite place_ids from localStorage
      const favorites = JSON.parse(localStorage.getItem('favoriteShops') || '[]');
      
      if (favorites.length === 0) {
        setFavoriteShops([]);
        setIsLoading(false);
        return;
      }

      // Load full shop data for each favorite
      let shops = [];

      // Prioritaskan data lokal jika USE_LOCAL_DATA aktif
      if (USE_LOCAL_DATA) {
        console.log('[Favorite] Using local JSON data...');
        if (localPlacesData && localPlacesData.data && Array.isArray(localPlacesData.data)) {
          for (const placeId of favorites) {
            const foundShop = localPlacesData.data.find(shop => shop.place_id === placeId);
            if (foundShop) {
              console.log(`[Favorite] Found shop in local data: ${foundShop.name}`);
              shops.push({
                place_id: foundShop.place_id,
                name: foundShop.name,
                address: foundShop.address,
                vicinity: foundShop.address,
                rating: foundShop.rating,
                user_ratings_total: foundShop.user_ratings_total,
                location: foundShop.location,
                business_status: foundShop.business_status,
                price_level: foundShop.price_level,
                photos: Array.isArray(foundShop.photos) ? foundShop.photos : [],
              });
            }
          }
          console.log(`[Favorite] Total shops loaded from local data: ${shops.length}`);
          setFavoriteShops(shops);
          setIsLoading(false);
          return;
        }
      }

      if (USE_API) {
        // Try to get details from backend for each favorite
        for (const placeId of favorites) {
          try {
            console.log(`[Favorite] Fetching details for place_id: ${placeId}`);
            const response = await fetch(`${API_BASE}/api/coffeeshops/detail/${placeId}`);
            const data = await response.json();
            
            console.log(`[Favorite] Response for ${placeId}:`, data);
            
            if (data.status === 'success' && data.data) {
              const detail = data.data;
              
              // Pastikan photos adalah array of URLs (bukan objects)
              let photoUrls = [];
              if (Array.isArray(detail.photos)) {
                // Photos sudah dalam format URL string dari backend
                photoUrls = detail.photos.slice(0, 1); // Ambil 1 foto pertama
                console.log(`[Favorite] Photos for ${detail.name}:`, photoUrls);
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
              
              console.log(`[Favorite] Shop data prepared:`, shop);
              shops.push(shop);
            }
          } catch (err) {
            console.error(`[Favorite] Error loading favorite ${placeId}:`, err);
          }
        }
      }
      
      console.log(`[Favorite] Total shops loaded: ${shops.length}`);

      setFavoriteShops(shops);
      setIsLoading(false);
    } catch (err) {
      console.error('Error loading favorites:', err);
      setIsLoading(false);
    }
  };

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
          <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold text-gray-900 dark:text-white mb-2">
            ❤️ Favorit Saya
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            {favoriteShops.length} coffee shop yang Anda sukai
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 sm:gap-6">
          {favoriteShops.map((shop) => (
            <Link key={shop.place_id} to={`/shop/${shop.place_id}`}>
              <CoffeeShopCard shop={shop} />
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Favorite;


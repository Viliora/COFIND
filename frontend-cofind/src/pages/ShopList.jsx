import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Link } from 'react-router-dom';
import SearchBar from '../components/SearchBar';
import CoffeeShopCard from '../components/CoffeeShopCard';
import { preloadFeaturedImages } from '../utils/imagePreloader';

// Konfigurasi API (optional - bisa di-set via environment variable)
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';
const USE_API = import.meta.env.VITE_USE_API === 'true'; // Set VITE_USE_API=true untuk enable API

export default function ShopList() {
  const [coffeeShops, setCoffeeShops] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [error, setError] = useState(null);
  const [isFromCache, setIsFromCache] = useState(false);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [activeFilter, setActiveFilter] = useState('all'); // Filter state
  const scrollContainerRef = useRef(null);
  const featuredScrollRef = useRef(null);

  const [isDragging, setIsDragging] = useState(false);
  const dragStateRef = useRef({ startX: 0, scrollLeft: 0 });

  const addGrabbingCursor = () => {
    const container = scrollContainerRef.current;
    if (container) {
      container.classList.add('cursor-grabbing');
    }
  };

  const removeGrabbingCursor = () => {
    const container = scrollContainerRef.current;
    if (container) {
      container.classList.remove('cursor-grabbing');
    }
  };

  const handleMouseDown = (event) => {
    const container = scrollContainerRef.current;
    if (!container) return;

    setIsDragging(true);
    dragStateRef.current = {
      startX: event.pageX - container.offsetLeft,
      scrollLeft: container.scrollLeft,
    };
    addGrabbingCursor();
  };

  const handleMouseLeave = () => {
    if (!isDragging) return;
    setIsDragging(false);
    removeGrabbingCursor();
  };

  const handleMouseUp = () => {
    if (!isDragging) return;
    setIsDragging(false);
    removeGrabbingCursor();
  };

  const handleMouseMove = (event) => {
    if (!isDragging) return;
    event.preventDefault();
    const container = scrollContainerRef.current;
    if (!container) return;

    const x = event.pageX - container.offsetLeft;
    const walk = x - dragStateRef.current.startX;
    container.scrollLeft = dragStateRef.current.scrollLeft - walk;
  };

  const handleTouchStart = (event) => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const touch = event.touches[0];
    setIsDragging(true);
    dragStateRef.current = {
      startX: touch.pageX - container.offsetLeft,
      scrollLeft: container.scrollLeft,
    };
    addGrabbingCursor();
  };

  const handleTouchMove = (event) => {
    if (!isDragging) return;
    const container = scrollContainerRef.current;
    if (!container) return;

    const touch = event.touches[0];
    const x = touch.pageX - container.offsetLeft;
    const walk = x - dragStateRef.current.startX;
    container.scrollLeft = dragStateRef.current.scrollLeft - walk;
  };

  const handleTouchEnd = () => {
    if (!isDragging) return;
    setIsDragging(false);
    removeGrabbingCursor();
  };

  // Listen untuk online/offline events
  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  useEffect(() => {
    const loadShops = async () => {
      try {
        setIsLoading(true);
        setError(null);
        
        // Direct API call without caching
        if (USE_API && isOnline) {
          try {
            const apiUrl = `${API_BASE}/api/search/coffeeshops?lat=-0.026330&lng=109.342506`;
            console.log('[ShopList] Fetching from API:', apiUrl);
            
            const response = await fetch(apiUrl);
            
            if (!response.ok) {
              throw new Error(`API returned status ${response.status}`);
            }
            
            const result = await response.json();
            
            if (result.data && Array.isArray(result.data) && result.data.length > 0) {
              console.log('[ShopList] Loaded from API:', result.data.length, 'shops');
              setCoffeeShops(result.data);
              setIsFromCache(false);
              setIsLoading(false);
              return;
            }
          } catch (apiError) {
            console.error('[ShopList] API fetch failed:', apiError.message);
            throw new Error('Unable to load coffee shops. Please check your internet connection and ensure the backend is running.');
          }
        } else {
          throw new Error('API is disabled or you are offline. Please check your connection.');
        }
      } catch (err) {
        console.error("Error loading data:", err);
        setError(err.message || "Failed to load coffee shop data");
        setCoffeeShops([]);
        setIsLoading(false);
      }
    };

    loadShops();
  }, [isOnline]); // Re-run saat online status berubah

  // Dapatkan Featured Coffee Shops (Top 5 berdasarkan scoring) - menggunakan useMemo untuk optimasi
  const featuredShops = useMemo(() => {
    if (coffeeShops.length === 0) return [];
    
    const calculateFeaturedScore = (shop) => {
      const rating = shop.rating || 0;
      const reviews = shop.user_ratings_total || 0;
      const maxReviews = Math.max(...coffeeShops.map(s => s.user_ratings_total || 0));
      const normalizedReviews = maxReviews > 0 ? reviews / maxReviews : 0;
      const hasCompleteData = shop.address && shop.rating && shop.user_ratings_total ? 1 : 0.5;
      
      // Scoring: rating (40%) + popularity (30%) + data completeness (30%)
      return (rating * 0.4) + (normalizedReviews * 5 * 0.3) + (hasCompleteData * 5 * 0.3);
    };

    return coffeeShops
      .filter(shop => shop.rating >= 4.0) // Minimal rating 4.0
      .map(shop => ({ ...shop, featuredScore: calculateFeaturedScore(shop) }))
      .sort((a, b) => b.featuredScore - a.featuredScore)
      .slice(0, 5);
  }, [coffeeShops]);

  // Filter berdasarkan kategori
  const getFilteredShopsByCategory = (shops) => {
    switch (activeFilter) {
      case 'top-rated':
        return shops.filter(shop => shop.rating >= 4.5);
      case 'popular':
        return shops.sort((a, b) => (b.user_ratings_total || 0) - (a.user_ratings_total || 0));
      case 'budget':
        return shops.filter(shop => shop.price_level && shop.price_level <= 2);
      case 'premium':
        return shops.filter(shop => shop.price_level && shop.price_level >= 3);
      case 'hidden-gems':
        return shops.filter(shop => shop.rating >= 4.3 && (shop.user_ratings_total || 0) < 200);
      default:
        return shops;
    }
  };

  // Filter berdasarkan search dan kategori
  const filteredShops = getFilteredShopsByCategory(
    coffeeShops.filter(shop =>
      shop.name.toLowerCase().includes(searchTerm.toLowerCase())
    )
  );

  // Statistics
  const stats = {
    total: coffeeShops.length,
    avgRating: coffeeShops.length > 0 
      ? (coffeeShops.reduce((sum, shop) => sum + (shop.rating || 0), 0) / coffeeShops.length).toFixed(1)
      : 0,
    topRated: coffeeShops.filter(shop => shop.rating >= 4.5).length,
    totalReviews: coffeeShops.reduce((sum, shop) => sum + (shop.user_ratings_total || 0), 0),
  };

  // Preload featured images setelah data dimuat
  useEffect(() => {
    if (featuredShops.length > 0 && !isLoading) {
      // Preload featured images dengan delay kecil agar tidak mengganggu initial render
      const timer = setTimeout(() => {
        preloadFeaturedImages(featuredShops)
          .then(() => {
            console.log('[ShopList] Featured images preloaded successfully');
          })
          .catch((err) => {
            console.warn('[ShopList] Some featured images failed to preload:', err);
          });
      }, 100);

      return () => clearTimeout(timer);
    }
  }, [featuredShops, isLoading]); // featuredShops sudah di-memoize, aman digunakan sebagai dependency

  if (isLoading) {
    return (
      <div className="text-center p-8 sm:p-12 md:p-16">
        <h1 className="text-xl sm:text-2xl md:text-3xl text-indigo-600 font-semibold px-4">Loading Coffee Shops in Pontianak...</h1>
        <div className="mt-4 flex justify-center">
          <div className="animate-spin rounded-full h-10 w-10 sm:h-12 sm:w-12 border-b-2 border-indigo-600"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full pb-6 sm:pb-8">
      <div className="bg-indigo-700 h-24 sm:h-32 md:h-40 flex items-center justify-center text-white mb-4 sm:mb-6 shadow-lg px-4 w-full">
        <h1 className="text-lg sm:text-2xl md:text-3xl lg:text-4xl font-extrabold tracking-tight text-center">Temukan Coffee Shop Terbaik di Pontianak</h1>
      </div>

      <SearchBar setSearchTerm={setSearchTerm} />

      <main className="w-full py-4 sm:py-6 md:py-8 px-4 sm:px-6">
        
        {/* Statistics Cards */}
        {!error && !isLoading && coffeeShops.length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4 mb-6 sm:mb-8">
            <div className="bg-gradient-to-br from-indigo-500 to-indigo-600 rounded-xl p-4 sm:p-5 text-white shadow-lg hover:shadow-xl transition-shadow">
              <div className="text-2xl sm:text-3xl font-bold mb-1">{stats.total}+</div>
              <div className="text-xs sm:text-sm opacity-90">Coffee Shops</div>
              <div className="text-xs mt-1 opacity-75">di Pontianak</div>
            </div>
            
            <div className="bg-gradient-to-br from-amber-500 to-orange-600 rounded-xl p-4 sm:p-5 text-white shadow-lg hover:shadow-xl transition-shadow">
              <div className="text-2xl sm:text-3xl font-bold mb-1 flex items-center">
                ⭐ {stats.avgRating}
              </div>
              <div className="text-xs sm:text-sm opacity-90">Rata-rata Rating</div>
              <div className="text-xs mt-1 opacity-75">dari semua review</div>
            </div>
            
            <div className="bg-gradient-to-br from-green-500 to-emerald-600 rounded-xl p-4 sm:p-5 text-white shadow-lg hover:shadow-xl transition-shadow">
              <div className="text-2xl sm:text-3xl font-bold mb-1">{stats.topRated}</div>
              <div className="text-xs sm:text-sm opacity-90">Top Rated</div>
              <div className="text-xs mt-1 opacity-75">rating ≥ 4.5</div>
            </div>
            
            <div className="bg-gradient-to-br from-purple-500 to-pink-600 rounded-xl p-4 sm:p-5 text-white shadow-lg hover:shadow-xl transition-shadow">
              <div className="text-2xl sm:text-3xl font-bold mb-1">{stats.totalReviews.toLocaleString()}</div>
              <div className="text-xs sm:text-sm opacity-90">Total Reviews</div>
              <div className="text-xs mt-1 opacity-75">dari pengguna</div>
            </div>
          </div>
        )}

        {/* Featured Coffee Shops */}
        {!error && !isLoading && featuredShops.length > 0 && !searchTerm && (
          <div className="mb-8 sm:mb-10">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl sm:text-2xl md:text-3xl font-bold text-gray-800 dark:text-gray-200 flex items-center gap-2">
                <span className="text-2xl">🏆</span>
                Featured Coffee Shops
              </h2>
              <span className="text-xs sm:text-sm text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 px-3 py-1 rounded-full">
                Top {featuredShops.length}
              </span>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Dipilih berdasarkan rating tinggi, popularitas, dan kelengkapan informasi
            </p>
            
            <div className="relative">
              <div
                ref={featuredScrollRef}
                className="flex gap-4 overflow-x-auto scroll-smooth pb-4 snap-x snap-mandatory"
              >
                {featuredShops.map((shop, index) => (
                  <Link
                    key={shop.place_id}
                    to={`/shop/${shop.place_id}`}
                    className="relative block hover:shadow-2xl transition duration-300 min-w-[280px] sm:min-w-[320px] md:min-w-[350px] shrink-0 snap-start group"
                  >
                    <div className="absolute -top-2 -left-2 z-10 bg-gradient-to-r from-yellow-400 to-orange-500 text-white w-10 h-10 rounded-full flex items-center justify-center font-bold text-lg shadow-lg">
                      {index + 1}
                    </div>
                    <div className="relative">
                      <CoffeeShopCard shop={shop} />
                      <div className="absolute top-2 right-2 bg-yellow-400 text-yellow-900 px-2 py-1 rounded-full text-xs font-bold shadow-md">
                        ⭐ Featured
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Quick Filter Categories */}
        {!error && !isLoading && coffeeShops.length > 0 && (
          <div className="mb-6">
            <h3 className="text-lg sm:text-xl font-semibold text-gray-800 dark:text-gray-200 mb-3">
              Filter Cepat
            </h3>
            <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
              <button
                onClick={() => setActiveFilter('all')}
                className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-all ${
                  activeFilter === 'all'
                    ? 'bg-indigo-600 text-white shadow-lg scale-105'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
                }`}
              >
                🏠 Semua ({coffeeShops.length})
              </button>
              
              <button
                onClick={() => setActiveFilter('top-rated')}
                className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-all ${
                  activeFilter === 'top-rated'
                    ? 'bg-indigo-600 text-white shadow-lg scale-105'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
                }`}
              >
                ⭐ Top Rated ({coffeeShops.filter(s => s.rating >= 4.5).length})
              </button>
              
              <button
                onClick={() => setActiveFilter('popular')}
                className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-all ${
                  activeFilter === 'popular'
                    ? 'bg-indigo-600 text-white shadow-lg scale-105'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
                }`}
              >
                🔥 Populer
              </button>
              
              <button
                onClick={() => setActiveFilter('budget')}
                className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-all ${
                  activeFilter === 'budget'
                    ? 'bg-indigo-600 text-white shadow-lg scale-105'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
                }`}
              >
                💵 Budget Friendly ({coffeeShops.filter(s => s.price_level && s.price_level <= 2).length})
              </button>
              
              <button
                onClick={() => setActiveFilter('premium')}
                className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-all ${
                  activeFilter === 'premium'
                    ? 'bg-indigo-600 text-white shadow-lg scale-105'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
                }`}
              >
                💎 Premium ({coffeeShops.filter(s => s.price_level && s.price_level >= 3).length})
              </button>
              
              <button
                onClick={() => setActiveFilter('hidden-gems')}
                className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-all ${
                  activeFilter === 'hidden-gems'
                    ? 'bg-indigo-600 text-white shadow-lg scale-105'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
                }`}
              >
                💎 Hidden Gems ({coffeeShops.filter(s => s.rating >= 4.3 && (s.user_ratings_total || 0) < 200).length})
              </button>
            </div>
          </div>
        )}
        <div className="flex items-center justify-between mb-4 sm:mb-6">
          <h2 className="text-xl sm:text-2xl md:text-3xl font-bold text-gray-800 dark:text-gray-200 border-b pb-2 flex-1">
            {activeFilter === 'all' ? 'Semua Coffee Shop' : 
             activeFilter === 'top-rated' ? '⭐ Top Rated Coffee Shops' :
             activeFilter === 'popular' ? '🔥 Coffee Shop Populer' :
             activeFilter === 'budget' ? '💵 Budget Friendly' :
             activeFilter === 'premium' ? '💎 Premium Coffee Shops' :
             activeFilter === 'hidden-gems' ? '💎 Hidden Gems' : 'Coffee Shop Catalog'} ({filteredShops.length})
            {searchTerm && <span className="block sm:inline text-gray-500 dark:text-gray-400 text-sm sm:text-base md:text-lg mt-1 sm:mt-0"> - Search: "{searchTerm}"</span>}
          </h2>
          {isFromCache && !isLoading && (
            <span className="ml-2 px-2 py-1 text-xs bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-200 rounded-full">
              📦 Cached
            </span>
          )}
          {!isOnline && !isLoading && (
            <span className="ml-2 px-2 py-1 text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200 rounded-full">
              📡 Offline
            </span>
          )}
        </div>

        {error && (
          <div className="bg-red-50 dark:bg-red-900/20 border-l-4 border-red-400 p-4 mb-6">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3 flex-1">
                <h3 className="text-sm font-medium text-red-800 dark:text-red-200">Error loading data</h3>
                <p className="mt-1 text-sm text-red-700 dark:text-red-300">{error}</p>
                <div className="mt-3 flex gap-2">
                  <button
                    onClick={() => window.location.reload()}
                    className="text-sm px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-md font-medium transition-colors"
                  >
                    Try Again →
                  </button>
                  <button
                    onClick={() => {
                      window.location.reload();
                    }}
                    className="text-sm px-3 py-1.5 bg-gray-600 hover:bg-gray-700 text-white rounded-md font-medium transition-colors"
                  >
                    Reload Page
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {!error && filteredShops.length > 0 && (
          <div className="relative px-2 sm:px-0">
            <div
              ref={scrollContainerRef}
              className="flex gap-3 sm:gap-4 md:gap-6 overflow-x-auto scroll-smooth pb-4 pr-12 sm:pr-16 snap-x snap-mandatory cursor-grab select-none"
              onMouseDown={handleMouseDown}
              onMouseLeave={handleMouseLeave}
              onMouseUp={handleMouseUp}
              onMouseMove={handleMouseMove}
              onTouchStart={handleTouchStart}
              onTouchMove={handleTouchMove}
              onTouchEnd={handleTouchEnd}
            >
              {filteredShops.map((shop) => (
                <Link
                  key={shop.place_id}
                  to={`/shop/${shop.place_id}`}
                  className="block hover:shadow-2xl transition duration-300 min-w-[240px] sm:min-w-[280px] md:min-w-[300px] shrink-0 snap-start"
                >
                  <CoffeeShopCard shop={shop} />
                </Link>
              ))}
            </div>
          </div>
        )}

        {!error && !isLoading && filteredShops.length === 0 && searchTerm === '' && (
          <div className="text-center py-12">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M12 20a8 8 0 100-16 8 8 0 000 16z" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900">No coffee shops found</h3>
            <p className="mt-1 text-sm text-gray-500">Check if the backend is returning data correctly.</p>
          </div>
        )}
        {!error && !isLoading && filteredShops.length === 0 && searchTerm !== '' && (
          <div className="text-center py-12">
            <h3 className="text-lg font-medium text-gray-900">No results for "{searchTerm}"</h3>
            <p className="mt-2 text-gray-500">Try different search terms or clear the search.</p>
            <button
              onClick={() => setSearchTerm('')}
              className="mt-4 text-indigo-600 hover:text-indigo-500"
            >
              Clear Search
            </button>
          </div>
        )}
      </main>
    </div>
  );
}

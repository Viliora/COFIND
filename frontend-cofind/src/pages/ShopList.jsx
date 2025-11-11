import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import SearchBar from '../components/SearchBar';
import CoffeeShopCard from '../components/CoffeeShopCard';
import placesData from '../data/places.json';
import { fetchWithCache, getAllCachedCoffeeShops, initAPICache } from '../utils/apiCache';

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
  const scrollContainerRef = useRef(null);

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
    // Initialize API Cache
    initAPICache();
    
    const loadShops = async () => {
      try {
        setIsLoading(true);
        setError(null);
        
        // Strategy: API First (jika enabled), lalu Cache, lalu places.json
        if (USE_API && isOnline) {
          try {
            // Coba fetch dari API dengan caching
            const apiUrl = `${API_BASE}/api/search/coffeeshops?lat=-0.026330&lng=109.342506`;
            const result = await fetchWithCache(apiUrl);
            
            if (result.data && Array.isArray(result.data.data) && result.data.data.length > 0) {
              console.log('[ShopList] Loading from API', result.fromCache ? '(cached)' : '(network)');
              setCoffeeShops(result.data.data);
              setIsFromCache(result.fromCache);
              setIsLoading(false);
              return;
            }
          } catch (apiError) {
            console.warn('[ShopList] API fetch failed, trying cache:', apiError.message);
          }
        }
        
        // Fallback 1: Coba dari IndexedDB cache
        const cachedData = await getAllCachedCoffeeShops();
        if (cachedData && Array.isArray(cachedData.data) && cachedData.data.length > 0) {
          console.log('[ShopList] Loading from IndexedDB cache');
          setCoffeeShops(cachedData.data);
          setIsFromCache(true);
          setIsLoading(false);
          return;
        }
        
        // Fallback 2: Gunakan data dari places.json (static)
        if (placesData && Array.isArray(placesData.data) && placesData.data.length > 0) {
          console.log('[ShopList] Loading from places.json (fallback)');
          setCoffeeShops(placesData.data);
          setIsFromCache(false);
          setIsLoading(false);
          
          // Pre-cache places.json data untuk offline access
          if (USE_API) {
            const { preCacheCoffeeShops } = await import('../utils/apiCache');
            preCacheCoffeeShops(placesData);
          }
        } else {
          throw new Error('Data tidak ditemukan');
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

  const filteredShops = coffeeShops.filter(shop =>
    shop.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

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
        <div className="flex items-center justify-between mb-4 sm:mb-6">
          <h2 className="text-xl sm:text-2xl md:text-3xl font-bold text-gray-800 dark:text-gray-200 border-b pb-2 flex-1">
            Coffee Shop Catalog ({filteredShops.length})
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
                    onClick={async () => {
                      // Clear cache dan reload
                      const { clearCache } = await import('../utils/cacheManager');
                      await clearCache('content');
                      window.location.reload();
                    }}
                    className="text-sm px-3 py-1.5 bg-gray-600 hover:bg-gray-700 text-white rounded-md font-medium transition-colors"
                  >
                    Clear Cache & Reload
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

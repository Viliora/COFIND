import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import CoffeeShopCard from '../components/CoffeeShopCard';
import HeroSwiper from '../components/HeroSwiper';
import { preloadFeaturedImages } from '../utils/imagePreloader';
import { fetchWithDevCache, isDevelopmentMode } from '../utils/devCache';
import { getRecentlyViewedWithDetails } from '../utils/recentlyViewed';
import heroBgImage from '../assets/1R modern cafe 1.5.jpg';
import localPlacesData from '../data/places.json';
// Reviews sekarang hanya dari Supabase, tidak perlu import reviews.json

// Konfigurasi API (optional - bisa di-set via environment variable)
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';
const USE_API = import.meta.env.VITE_USE_API === 'true'; // Set VITE_USE_API=true untuk enable API
const USE_LOCAL_DATA = true; // Set true untuk menggunakan data lokal JSON

export default function ShopList() {
  const [searchParams] = useSearchParams();
  const [coffeeShops, setCoffeeShops] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [error, setError] = useState(null);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [activeFilter] = useState('all'); // Filter state (default: all, tidak ada UI untuk mengubahnya)
  const [selectedPills, setSelectedPills] = useState([]); // Selected quick recommendation pills (max 3)
  const featuredScrollRef = useRef(null);

  // Update search term from URL params
  useEffect(() => {
    const query = searchParams.get('search') || '';
    setSearchTerm(query);
  }, [searchParams]);

  // Listen for URL changes (from Navbar search)
  useEffect(() => {
    const handlePopState = () => {
      const params = new URLSearchParams(window.location.search);
      const query = params.get('search') || '';
      setSearchTerm(query);
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);


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
        setError(null);
        
        // Prioritaskan data lokal jika USE_LOCAL_DATA aktif
        if (USE_LOCAL_DATA) {
          console.log('[ShopList] Using local JSON data...');
          if (localPlacesData && localPlacesData.data && Array.isArray(localPlacesData.data)) {
            console.log('[ShopList] Loaded from local JSON:', localPlacesData.data.length, 'shops');
            setCoffeeShops(localPlacesData.data);
            setIsLoading(false);
            return;
          } else {
            throw new Error('Local data format is invalid');
          }
        }
        
        if (USE_API && isOnline) {
          try {
            const apiUrl = `${API_BASE}/api/search/coffeeshops?lat=-0.026330&lng=109.342506`;
            console.log('[ShopList] Loading coffee shops...');
            
            // Use dev cache in development mode for instant loading
            if (isDevelopmentMode()) {
              console.log('[ShopList] Development mode - using optimized cache');
              
              const result = await fetchWithDevCache(apiUrl);
              
              if (result.data && result.data.data && Array.isArray(result.data.data)) {
                console.log('[ShopList] Loaded:', result.data.data.length, 'shops', 
                           result.fromCache ? '(from cache)' : '(fresh)');
                
                setCoffeeShops(result.data.data);
                
                // If data is from cache (stale), keep loading indicator briefly
                // Fresh data will update in background
                if (result.stale) {
                  console.log('[ShopList] Showing cached data, fetching fresh in background...');
                  // Set loading to false immediately to show cached data
                  setIsLoading(false);
                } else {
                  setIsLoading(false);
                }
                return;
              }
            } else {
              // Production mode - direct fetch without dev cache
              console.log('[ShopList] Production mode - direct API call');
              setIsLoading(true);
              
              const response = await fetch(apiUrl);
              
              if (!response.ok) {
                throw new Error(`API returned status ${response.status}`);
              }
              
              const result = await response.json();
              
              if (result.data && Array.isArray(result.data) && result.data.length > 0) {
                console.log('[ShopList] Loaded from API:', result.data.length, 'shops');
                setCoffeeShops(result.data);
                setIsLoading(false);
                return;
              }
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

  // Dapatkan Coffee Shop Terbaru (rating bagus tapi review masih sedikit)
  const newestShops = useMemo(() => {
    if (coffeeShops.length === 0) return [];
    
    return coffeeShops
      .filter(shop => shop.rating >= 4.0 && (shop.user_ratings_total || 0) < 100)
      .sort((a, b) => {
        // Sort berdasarkan rating tertinggi (descending), lalu review paling sedikit (ascending)
        const ratingA = parseFloat(a.rating) || 0;
        const ratingB = parseFloat(b.rating) || 0;
        const reviewsA = a.user_ratings_total || 0;
        const reviewsB = b.user_ratings_total || 0;
        
        // Jika rating berbeda, urutkan berdasarkan rating tertinggi
        if (ratingB !== ratingA) {
          return ratingB - ratingA;
        }
        // Jika rating sama, urutkan berdasarkan review paling sedikit
        return reviewsA - reviewsB;
      })
      .slice(0, 5);
  }, [coffeeShops]);


  // Dapatkan Top Rated Coffee Shops (rating 4.8-5.0)
  const topRatedShops = useMemo(() => {
    if (coffeeShops.length === 0) return [];
    
    return coffeeShops
      .filter(shop => {
        const rating = parseFloat(shop.rating) || 0;
        return rating >= 4.8 && rating <= 5.0;
      })
      .sort((a, b) => {
        // Sort berdasarkan rating (descending), lalu jumlah review (descending)
        const ratingA = parseFloat(a.rating) || 0;
        const ratingB = parseFloat(b.rating) || 0;
        if (ratingB !== ratingA) {
          return ratingB - ratingA;
        }
        return (b.user_ratings_total || 0) - (a.user_ratings_total || 0);
      });
  }, [coffeeShops]);

  // Dapatkan Recently Viewed Coffee Shops
  const recentlyViewedShops = useMemo(() => {
    return getRecentlyViewedWithDetails(coffeeShops);
  }, [coffeeShops]);

  // Filter berdasarkan kategori
  const getFilteredShopsByCategory = (shops) => {
    switch (activeFilter) {
      case 'top-rated':
        // Filter coffee shop dengan rating 4.8-5.0
        return shops.filter(shop => {
          const rating = parseFloat(shop.rating) || 0;
          return rating >= 4.8 && rating <= 5.0;
        }).sort((a, b) => {
          // Sort berdasarkan rating (descending), lalu jumlah review (descending)
          const ratingA = parseFloat(a.rating) || 0;
          const ratingB = parseFloat(b.rating) || 0;
          if (ratingB !== ratingA) {
            return ratingB - ratingA;
          }
          return (b.user_ratings_total || 0) - (a.user_ratings_total || 0);
        });
      case 'popular':
        // Filter coffee shop dengan review di atas 1000
        return shops
          .filter(shop => (shop.user_ratings_total || 0) > 1000)
          .sort((a, b) => (b.user_ratings_total || 0) - (a.user_ratings_total || 0));
      case 'newest':
        // Coffee shop terbaru: rating bagus (>= 4.0) tapi review masih sedikit (< 100)
        // Menandakan tempat baru yang berkualitas
        return shops
          .filter(shop => shop.rating >= 4.0 && (shop.user_ratings_total || 0) < 100)
          .sort((a, b) => (a.user_ratings_total || 0) - (b.user_ratings_total || 0));
      default:
        return shops;
    }
  };

  // Quick recommendation fields (sama dengan LLMAnalyzer)
  const recommendationFields = [
    { label: '🛋️ Cozy', value: 'cozy' },
    { label: '📚 Belajar', value: 'belajar' },
    { label: '📶 WiFi', value: 'wifi stabil' },
    { label: '🔌 Stopkontak', value: 'stopkontak' },
    { label: '🕌 Musholla', value: 'musholla' },
    { label: '🛋️ Sofa', value: 'sofa' },
    { label: '❄️ Dingin', value: 'dingin' },
    { label: '📸 Aesthetic', value: 'aesthetic' },
    { label: '🎵 Live Music', value: 'live music' },
    { label: '🅿️ Parkir Luas', value: 'parkiran luas' },
    { label: '🌙 24 jam', value: '24 jam' },
  ];

  // Handle pill click - toggle selection (max 3)
  const handlePillClick = (pillValue) => {
    setSelectedPills(prev => {
      if (prev.includes(pillValue)) {
        // Jika sudah dipilih, hapus
        return prev.filter(p => p !== pillValue);
      } else {
        // Jika belum dipilih dan belum mencapai max 3, tambahkan
        if (prev.length < 3) {
          return [...prev, pillValue];
        } else {
          // Sudah mencapai max 3, tidak bisa tambah lagi
          return prev;
        }
      }
    });
  };

  // Filter coffee shops berdasarkan selected pills
  // NOTE: Filtering berdasarkan reviews sekarang tidak tersedia karena reviews hanya dari Supabase
  // Filtering akan menggunakan data dari places.json (amenities/features) jika tersedia
  // Atau bisa diimplementasikan dengan fetch reviews dari Supabase untuk filtering (future enhancement)
  const filterShopsByPills = (shops) => {
    if (selectedPills.length === 0) {
      return shops;
    }

    // TODO: Implement filtering dengan fetch reviews dari Supabase jika diperlukan
    // Untuk sekarang, return semua shops jika ada pill yang dipilih
    // (atau bisa filter berdasarkan amenities di places.json jika ada)
    console.log('[ShopList] Pill filtering tidak tersedia - reviews sekarang hanya dari Supabase');
    return shops;
  };

  // Filter berdasarkan search, kategori, dan pills
  const filteredShops = getFilteredShopsByCategory(
    filterShopsByPills(
      coffeeShops.filter(shop =>
        shop.name.toLowerCase().includes(searchTerm.toLowerCase())
      )
    )
  );

  // Statistics
  const stats = {
    total: coffeeShops.length,
    avgRating: coffeeShops.length > 0 
      ? (coffeeShops.reduce((sum, shop) => sum + (shop.rating || 0), 0) / coffeeShops.length).toFixed(1)
      : 0,
    topRated: coffeeShops.filter(shop => {
      const rating = parseFloat(shop.rating) || 0;
      return rating >= 4.8 && rating <= 5.0;
    }).length,
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

  if (isLoading && coffeeShops.length === 0) {
    return (
      <div className="text-center p-8 sm:p-12 md:p-16">
        <h1 className="text-xl sm:text-2xl md:text-3xl text-indigo-600 font-semibold px-4">Loading Coffee Shops in Pontianak...</h1>
        <div className="mt-4 flex justify-center">
          <div className="animate-spin rounded-full h-10 w-10 sm:h-12 sm:w-12 border-b-2 border-indigo-600"></div>
        </div>
        {isDevelopmentMode() && (
          <p className="mt-4 text-sm text-gray-500">
            💡 Development mode: Data akan di-cache untuk 5 menit
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="w-full pb-6 sm:pb-8">
      {/* Hero Swiper - Auto-playing carousel */}
      {!error && !isLoading && coffeeShops.length > 0 && !searchTerm && (
        <HeroSwiper coffeeShops={coffeeShops} />
      )}

      <main className="w-full py-4 sm:py-6 md:py-8 px-4 sm:px-6">
        
        {/* Statistics Cards */}
        {!error && !isLoading && coffeeShops.length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4 mb-6 sm:mb-8">
            <div className="bg-gradient-to-br from-indigo-500 to-indigo-600 rounded-xl p-4 sm:p-5 text-white shadow-lg hover:shadow-xl transition-shadow">
              <div className="text-2xl sm:text-3xl font-bold mb-1">{stats.total}</div>
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
              <div className="text-xs mt-1 opacity-75">rating ≥ 4.8</div>
            </div>
            
            <div className="bg-gradient-to-br from-purple-500 to-pink-600 rounded-xl p-4 sm:p-5 text-white shadow-lg hover:shadow-xl transition-shadow">
              <div className="text-2xl sm:text-3xl font-bold mb-1">{stats.totalReviews.toLocaleString()}</div>
              <div className="text-xs sm:text-sm opacity-90">Total Reviews</div>
              <div className="text-xs mt-1 opacity-75">dari pengguna</div>
            </div>
          </div>
        )}

        {/* Quick Recommendation Pills */}
        {!error && !isLoading && coffeeShops.length > 0 && !searchTerm && (
          <div className="mb-6 sm:mb-8">
            <div className="mb-3">
              <h3 className="text-sm sm:text-base font-semibold text-gray-700 dark:text-gray-300 mb-2">
                Cari berdasarkan preferensi:
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                Pilih maksimal 3 preferensi untuk menemukan coffee shop yang sesuai
              </p>
            </div>
            <div className="flex flex-wrap gap-2 sm:gap-3">
              {recommendationFields.map((field) => {
                const isSelected = selectedPills.includes(field.value);
                const isDisabled = !isSelected && selectedPills.length >= 3;
                
                return (
                  <button
                    key={field.value}
                    onClick={() => handlePillClick(field.value)}
                    disabled={isDisabled}
                    className={`
                      px-3 sm:px-4 py-2 rounded-full text-sm font-medium
                      transition-all duration-200
                      ${
                        isSelected
                          ? 'bg-indigo-600 text-white shadow-md hover:bg-indigo-700 scale-105'
                          : isDisabled
                          ? 'bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-500 cursor-not-allowed opacity-50'
                          : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-600 hover:border-indigo-400 hover:text-indigo-600 dark:hover:text-indigo-400 hover:shadow-sm'
                      }
                    `}
                    title={isDisabled ? 'Maksimal 3 preferensi yang bisa dipilih' : isSelected ? 'Klik untuk menghapus' : 'Klik untuk memilih'}
                  >
                    {field.label}
                    {isSelected && (
                      <span className="ml-1.5 text-xs">✓</span>
                    )}
                  </button>
                );
              })}
            </div>
            {selectedPills.length > 0 && (
              <div className="mt-3 flex items-center gap-2">
                <button
                  onClick={() => setSelectedPills([])}
                  className="px-3 sm:px-4 py-2 rounded-full text-sm font-medium bg-indigo-600 text-white shadow-md hover:bg-indigo-700 transition-all duration-200"
                >
                  Hapus semua filter
                </button>
              </div>
            )}
          </div>
        )}

        {/* Featured Coffee Shops */}
        {!error && !isLoading && featuredShops.length > 0 && !searchTerm && !selectedPills.length && (
          <div className="mb-8 sm:mb-10">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl sm:text-2xl md:text-3xl font-bold text-gray-800 dark:text-gray-200 flex items-center gap-2">
                <span className="text-2xl">🏆</span>
                Featured Coffee Shops
              </h2>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Dipilih berdasarkan rating tinggi, popularitas, dan kelengkapan informasi
            </p>
            
            <div className="relative">
              <div
                ref={featuredScrollRef}
                className="flex gap-4 overflow-x-auto scroll-smooth pb-4 snap-x snap-mandatory"
                style={{ paddingLeft: '16px', paddingRight: '16px' }}
              >
                {featuredShops.map((shop, index) => (
                  <div
                    key={shop.place_id}
                    className="relative block hover:shadow-2xl transition duration-300 w-[240px] sm:w-[280px] md:w-[300px] shrink-0 snap-start group overflow-hidden"
                  >
                    <div className="absolute top-2 left-2 z-20 bg-gradient-to-r from-yellow-400 to-orange-500 text-white w-10 h-10 rounded-full flex items-center justify-center font-bold text-lg shadow-lg">
                      {index + 1}
                    </div>
                    <div className="relative w-full h-full">
                      <CoffeeShopCard shop={shop} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Modern Hero Banner with Background Image - Dipindahkan ke antara Featured dan Terbaru */}
        {!error && !isLoading && coffeeShops.length > 0 && !searchTerm && !selectedPills.length && (
          <div className="relative h-48 sm:h-56 md:h-64 flex items-center justify-center mb-6 sm:mb-8 overflow-hidden w-full">
            {/* Background Image with Overlay */}
            <div 
              className="absolute inset-0 bg-cover bg-center"
              style={{
                backgroundImage: `url(${heroBgImage})`,
              }}
            >
              {/* Dark Overlay for better text readability */}
              <div className="absolute inset-0 bg-gradient-to-b from-black/60 via-black/50 to-black/70"></div>
            </div>
            
            {/* Content */}
            <div className="relative z-10 text-center px-4 sm:px-6 max-w-4xl mx-auto">
              {/* Main Heading */}
              <h1 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-extrabold text-white mb-3 sm:mb-4 leading-tight">
                <span className="block mb-1 sm:mb-2 bg-gradient-to-r from-amber-400 via-orange-400 to-amber-500 bg-clip-text text-transparent drop-shadow-lg">
                  Temukan Coffee Shop
                </span>
                <span className="block text-white drop-shadow-2xl">
                  Yang Sesuai Dengan Keinginan Anda!
                </span>
              </h1>
              
              {/* Subtitle */}
              <p className="text-sm sm:text-base md:text-lg text-gray-200 font-medium drop-shadow-lg">
                Jelajahi <span className="text-amber-400 font-bold">{coffeeShops.length}</span> coffee shop di Pontianak
              </p>
            </div>
            
            {/* Bottom Gradient Fade */}
            <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-gray-50 dark:from-zinc-900 to-transparent"></div>
          </div>
        )}

        {/* Top Rated Coffee Shops (4.8-5.0) */}
        {!error && !isLoading && topRatedShops.length > 0 && !searchTerm && !selectedPills.length && (
          <div className="mb-8 sm:mb-10">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl sm:text-2xl md:text-3xl font-bold text-gray-800 dark:text-gray-200 flex items-center gap-2">
                <span className="text-2xl">⭐</span>
                Top Rated Coffee Shops
              </h2>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Coffee shop dengan rating tertinggi - pilihan terbaik dalam pengalaman ngopi
            </p>
            
            <div className="relative">
              <div className="flex gap-4 overflow-x-auto scroll-smooth pb-4 snap-x snap-mandatory">
                {topRatedShops.map((shop) => (
                  <div
                    key={shop.place_id}
                    className="relative block hover:shadow-2xl transition duration-300 w-[240px] sm:w-[280px] md:w-[300px] shrink-0 snap-start group"
                  >
                    <div className="relative">
                      <CoffeeShopCard shop={shop} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Newest Coffee Shops */}
        {!error && !isLoading && newestShops.length > 0 && !searchTerm && !selectedPills.length && (
          <div className="mb-8 sm:mb-10">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl sm:text-2xl md:text-3xl font-bold text-gray-800 dark:text-gray-200 flex items-center gap-2">
                <span className="text-2xl">💎</span>
                Hidden Gem Coffee Shops
              </h2>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Coffee shop Hidden Gem (rating tinggi dengan sedikit review)
            </p>
            
            <div className="relative">
              <div className="flex gap-4 overflow-x-auto scroll-smooth pb-4 snap-x snap-mandatory">
                {newestShops.map((shop) => (
                  <div
                    key={shop.place_id}
                    className="relative block hover:shadow-2xl transition duration-300 w-[240px] sm:w-[280px] md:w-[300px] shrink-0 snap-start group"
                  >
                    <div className="relative">
                      <CoffeeShopCard shop={shop} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Recently Viewed Coffee Shops - Tampilkan di atas All Coffee Shops */}
        {!error && !isLoading && recentlyViewedShops.length > 0 && !searchTerm && !selectedPills.length && (
          <div className="mb-8 sm:mb-10">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl sm:text-2xl md:text-3xl font-bold text-gray-800 dark:text-gray-200 flex items-center gap-2">
                <span className="text-2xl">🕒</span>
                Just Seen Coffee Shops
              </h2>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Coffee shop yang baru saja Anda lihat
            </p>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 sm:gap-6">
              {recentlyViewedShops.map((shop) => (
                <div key={shop.place_id} className="block hover:shadow-2xl transition duration-300">
                  <CoffeeShopCard shop={shop} />
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex items-center justify-between mb-4 sm:mb-6 flex-wrap gap-2">
          <h2 className="text-xl sm:text-2xl md:text-3xl font-bold text-gray-800 dark:text-gray-200 border-b pb-2 flex-1">
            {selectedPills.length > 0 ? 'Hasil Pencarian' :
             activeFilter === 'all' ? 'All Coffee Shops' : 
             activeFilter === 'top-rated' ? '⭐ Top Rated Coffee Shops' :
             activeFilter === 'newest' ? '💎 Hidden Gem Coffee Shops' : 'Coffee Shop Catalog'} ({filteredShops.length})
            {searchTerm && <span className="block sm:inline text-gray-500 dark:text-gray-400 text-sm sm:text-base md:text-lg mt-1 sm:mt-0"> - Search: "{searchTerm}"</span>}
          </h2>
          <div className="flex items-center gap-2">
            {!isOnline && !isLoading && (
              <span className="px-2 py-1 text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200 rounded-full">
                📡 Offline
              </span>
            )}
          </div>
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
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 sm:gap-6">
            {filteredShops.map((shop) => (
              <Link
                key={shop.place_id}
                to={`/shop/${shop.place_id}`}
                className="block hover:shadow-2xl transition duration-300"
              >
                <CoffeeShopCard shop={shop} />
              </Link>
            ))}
          </div>
        )}

        {!error && !isLoading && filteredShops.length === 0 && searchTerm === '' && selectedPills.length === 0 && (
          <div className="text-center py-12">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M12 20a8 8 0 100-16 8 8 0 000 16z" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-gray-100">No coffee shops found</h3>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Check if the backend is returning data correctly.</p>
          </div>
        )}
        
        {!error && !isLoading && filteredShops.length === 0 && selectedPills.length > 0 && (
          <div className="text-center py-12">
            <svg className="mx-auto h-12 w-12 text-gray-400 dark:text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M12 20a8 8 0 100-16 8 8 0 000 16z" />
            </svg>
            <h3 className="mt-2 text-lg font-medium text-gray-900 dark:text-gray-100">
              Tidak ada coffee shop yang sesuai
            </h3>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Tidak ada coffee shop yang memiliki review sesuai dengan preferensi yang Anda pilih.
            </p>
            <button
              onClick={() => setSelectedPills([])}
              className="mt-4 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              Hapus Filter
            </button>
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

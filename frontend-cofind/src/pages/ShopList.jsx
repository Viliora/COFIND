import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import CoffeeShopCard from '../components/CoffeeShopCard';
import HeroSwiper from '../components/HeroSwiper';
import CoffeeShopMap from '../components/CoffeeShopMap';
import CoffeeShopRadiusMap from '../components/CoffeeShopRadiusMap';
import { preloadFeaturedImages } from '../utils/imagePreloader';
import { ensureCoffeeShopImageMap } from '../utils/coffeeShopImages';
import { getRecentlyViewedWithDetails } from '../utils/recentlyViewed';
import heroBgImage from '../assets/1R modern cafe 1.5.jpg';
import { useAuth } from '../context/authContext';
import { authService } from '../services/authService';

// API Configuration
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';

export default function ShopList() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { loading: authLoading, isAuthenticated, user } = useAuth();
  const [coffeeShops, setCoffeeShops] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [error, setError] = useState(null);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [activeFilter] = useState('all');
  const [selectedPills, setSelectedPills] = useState([]);
  const [confirmedPills, setConfirmedPills] = useState([]);
  const [llmRecommendations, setLlmRecommendations] = useState([]);
  const [pillRecommendLoading, setPillRecommendLoading] = useState(false);
  const featuredScrollRef = useRef(null);
  const hasLoadedRef = useRef(false);

  // Modal saran preferensi
  const [showSuggestModal, setShowSuggestModal] = useState(false);
  const [showLoginPrompt, setShowLoginPrompt] = useState(false);
  const [preferenceInput, setPreferenceInput] = useState('');
  const [reasonInput, setReasonInput] = useState('');
  const [submitLoading, setSubmitLoading] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState('');
  const [submitError, setSubmitError] = useState('');

  // Lokasi saat ini & radius dalam meter (untuk katalog "coffee shop dalam radius")
  const [userLocation, setUserLocation] = useState(null);
  const [radiusMeters, setRadiusMeters] = useState(2000);
  const [locationLoading, setLocationLoading] = useState(false);
  const [locationError, setLocationError] = useState(null);
  const [showStatsInfoBubble, setShowStatsInfoBubble] = useState(false);

  // Title halaman
  useEffect(() => {
    document.title = 'Beranda - Cofind';
    return () => { document.title = 'Cofind'; };
  }, []);

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
    let isMounted = true;
    const timeoutId = setTimeout(() => {
      if (isMounted && !hasLoadedRef.current) {
        console.error('[ShopList] ❌ Timeout after 10 seconds - Backend is not responding');
        if (isMounted) {
          setCoffeeShops([]);
          setIsLoading(false);
          setError('⚠️ Backend server is not responding. Please check your connection.');
          hasLoadedRef.current = true;
        }
      }
    }, 10000); // 10 second timeout

    const loadShops = async () => {
      try {
        setError(null);
        
        if (authLoading) {
          console.log('[ShopList] Waiting for auth to complete...');
          return;
        }
        
        if (hasLoadedRef.current) {
          console.log('[ShopList] Already loaded, skipping');
          return;
        }
        
        console.log('[ShopList] Loading coffee shops from backend API...');
        
        const response = await fetch(`${API_BASE}/api/coffeeshops`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          }
        });
        
        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.status === 'success' && result.data) {
          console.log('[ShopList] ✅ Loaded from backend:', result.data.length, 'shops');
          ensureCoffeeShopImageMap(result.data);
          setCoffeeShops(result.data);
          setIsLoading(false);
          hasLoadedRef.current = true;
        } else {
          throw new Error(result.message || 'Failed to load shops');
        }
        
      } catch (err) {
        console.error('[ShopList] Error loading data:', err);
        if (isMounted) {
          setError(err.message || 'Failed to load coffee shops');
          setCoffeeShops([]);
          setIsLoading(false);
          hasLoadedRef.current = true;
        }
      }
    };

    loadShops();

    return () => {
      isMounted = false;
      clearTimeout(timeoutId);
    };
  }, [authLoading]);

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


  // Dapatkan Top Rated Coffee Shops (rating 4.5-5.0)
  const topRatedShops = useMemo(() => {
    if (coffeeShops.length === 0) return [];
    
    return coffeeShops
      .filter(shop => {
        const rating = parseFloat(shop.rating) || 0;
        return rating >= 4.5 && rating <= 5.0;
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
        // Filter coffee shop dengan rating 4.5-5.0
        return shops.filter(shop => {
          const rating = parseFloat(shop.rating) || 0;
          return rating >= 4.5 && rating <= 5.0;
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

  // Jarak Haversine (km) antara dua koordinat
  const haversineKm = (lat1, lng1, lat2, lng2) => {
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
      Math.sin(dLng / 2) * Math.sin(dLng / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  };

  // Coffee shop dalam radius (hanya ada setelah user dapat lokasi, radius dalam meter)
  const shopsInRadius = useMemo(() => {
    if (!userLocation || !coffeeShops.length) return [];
    const radiusKm = radiusMeters / 1000;
    return coffeeShops
      .filter(shop => shop.latitude != null && shop.longitude != null)
      .map(shop => ({
        ...shop,
        _distanceKm: haversineKm(
          userLocation.lat,
          userLocation.lng,
          shop.latitude,
          shop.longitude
        )
      }))
      .filter(shop => shop._distanceKm <= radiusKm)
      .sort((a, b) => a._distanceKm - b._distanceKm);
  }, [coffeeShops, userLocation, radiusMeters]);

  // Ambil lokasi saat ini (Browser Geolocation API)
  const getCurrentLocation = () => {
    setLocationError(null);
    setLocationLoading(true);
    if (!navigator.geolocation) {
      setLocationError('Browser tidak mendukung geolokasi.');
      setLocationLoading(false);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setLocationError(null);
        setLocationLoading(false);
      },
      (err) => {
        setLocationError(
          err.code === 1
            ? 'Akses lokasi ditolak. Izinkan lokasi di pengaturan browser.'
            : 'Tidak dapat mengambil lokasi. Coba lagi.'
        );
        setLocationLoading(false);
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
    );
  };

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

  // Buka modal saran preferensi
  const handleOpenSuggestModal = () => {
    setSubmitSuccess('');
    setSubmitError('');
    setPreferenceInput('');
    setReasonInput('');
    setShowSuggestModal(true);
  };

  // Tutup modal saran preferensi
  const handleCloseSuggestModal = () => {
    setShowSuggestModal(false);
    setSubmitSuccess('');
    setSubmitError('');
  };

  // Submit saran preferensi (hanya jika sudah login)
  const handleSuggestSubmit = async (e) => {
    e.preventDefault();
    if (!isAuthenticated || !user?.id) {
      setShowLoginPrompt(true);
      return;
    }
    setSubmitError('');
    setSubmitSuccess('');
    const pref = preferenceInput.trim();
    const reason = reasonInput.trim();
    if (!pref) {
      setSubmitError('Preferensi tidak boleh kosong.');
      return;
    }
    if (!reason) {
      setSubmitError('Alasan tidak boleh kosong.');
      return;
    }
    setSubmitLoading(true);
    try {
      const token = authService.getToken();
      const res = await fetch(`${API_BASE}/api/preference-suggestions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ preference_text: pref, reason_text: reason }),
      });
      const data = await res.json();
      if (data.status === 'success') {
        setSubmitSuccess('Saran preferensi berhasil disimpan. Terima kasih!');
        setPreferenceInput('');
        setReasonInput('');
        setTimeout(() => {
          setShowSuggestModal(false);
          setSubmitSuccess('');
        }, 1500);
      } else {
        setSubmitError(data.message || 'Gagal menyimpan.');
        if (data.require_login) setShowLoginPrompt(true);
      }
    } catch (err) {
      setSubmitError(err.message || 'Gagal mengirim. Coba lagi.');
    } finally {
      setSubmitLoading(false);
    }
  };

  // Rekomendasi LLM: map nama toko (normalized) -> penjelasan
  const recommendationExplanationByShopName = useMemo(() => {
    const map = {};
    llmRecommendations.forEach((r) => {
      if (r.name && r.explanation) map[r.name.trim().toLowerCase()] = r.explanation;
    });
    return map;
  }, [llmRecommendations]);

  // Konfirmasi preferensi & panggil API rekomendasi LLM
  const handleConfirmPills = async () => {
    if (selectedPills.length === 0) return;
    setConfirmedPills(selectedPills);
    setPillRecommendLoading(true);
    setLlmRecommendations([]);
    try {
      const res = await fetch(`${API_BASE}/api/recommend-by-preferences`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preferences: selectedPills }),
      });
      const data = await res.json();
      if (data.status === 'success' && Array.isArray(data.recommendations)) {
        setLlmRecommendations(data.recommendations);
      } else {
        setLlmRecommendations([]);
      }
    } catch (err) {
      console.error('[ShopList] recommend-by-preferences error:', err);
      setLlmRecommendations([]);
    } finally {
      setPillRecommendLoading(false);
    }
  };

  // Filter coffee shops: jika sudah konfirmasi dan ada hasil LLM, hanya tampilkan yang direkomendasikan
  const filterShopsByPills = (shops) => {
    if (confirmedPills.length === 0 || llmRecommendations.length === 0) {
      return shops;
    }
    const namesSet = new Set(
      llmRecommendations.map((r) => (r.name || '').trim().toLowerCase())
    );
    return shops.filter((shop) =>
      namesSet.has((shop.name || '').trim().toLowerCase())
    );
  };

  // Filter berdasarkan search, kategori, dan pills
  const filteredShops = getFilteredShopsByCategory(
    filterShopsByPills(
      coffeeShops.filter(shop =>
        shop.name.toLowerCase().includes(searchTerm.toLowerCase())
      )
    )
  );

  // Statistics: dari data yang tampil (filteredShops) dan field yang dipakai aplikasi (total_reviews / user_ratings_total, rating)
  const stats = useMemo(() => {
    const list = filteredShops;
    const total = list.length;
    const sumRating = list.reduce((sum, shop) => sum + (parseFloat(shop.rating) || 0), 0);
    const avgRating = total > 0 ? (sumRating / total).toFixed(1) : '0';
    const topRated = list.filter(shop => {
      const r = parseFloat(shop.rating) || 0;
      return r >= 4.5 && r <= 5;
    }).length;
    const totalReviews = list.reduce(
      (sum, shop) => sum + (Number(shop.total_reviews) || Number(shop.user_ratings_total) || 0),
      0
    );
    return { total, avgRating, topRated, totalReviews };
  }, [filteredShops]);

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
        {import.meta.env.DEV && (
          <p className="mt-4 text-sm text-gray-500">
            💡 Development mode: Data fetched fresh from Supabase (caching disabled)
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
        
        {/* Statistics Cards - sesuai data yang tampil di aplikasi (filteredShops) */}
        {!error && !isLoading && coffeeShops.length > 0 && (
          <div className="relative grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4 mb-6 sm:mb-8">
            <div className="bg-gradient-to-br from-indigo-500 to-indigo-600 rounded-xl p-4 sm:p-5 text-white shadow-lg hover:shadow-xl transition-shadow relative">
              <button
                type="button"
                onClick={() => setShowStatsInfoBubble((v) => !v)}
                className="absolute top-2 right-2 w-5 h-5 rounded-full bg-white/25 hover:bg-white/40 flex items-center justify-center text-white text-xs font-bold focus:outline-none focus:ring-2 focus:ring-white/50"
                aria-label="Informasi sumber data"
              >
                i
              </button>
              <div className="text-2xl sm:text-3xl font-bold mb-1">{stats.total}</div>
              <div className="text-xs sm:text-sm opacity-90">Coffee Shops</div>
              <div className="text-xs mt-1 opacity-75">{searchTerm ? 'hasil pencarian' : 'di Pontianak'}</div>
            </div>

            <div className="bg-gradient-to-br from-amber-500 to-orange-600 rounded-xl p-4 sm:p-5 text-white shadow-lg hover:shadow-xl transition-shadow relative">
              <button
                type="button"
                onClick={() => setShowStatsInfoBubble((v) => !v)}
                className="absolute top-2 right-2 w-5 h-5 rounded-full bg-white/25 hover:bg-white/40 flex items-center justify-center text-white text-xs font-bold focus:outline-none focus:ring-2 focus:ring-white/50"
                aria-label="Informasi sumber data"
              >
                i
              </button>
              <div className="text-2xl sm:text-3xl font-bold mb-1 flex items-center">
                ⭐ {stats.avgRating}
              </div>
              <div className="text-xs sm:text-sm opacity-90">Rata-rata Rating</div>
              <div className="text-xs mt-1 opacity-75">tempat yang tampil</div>
            </div>

            <div className="bg-gradient-to-br from-green-500 to-emerald-600 rounded-xl p-4 sm:p-5 text-white shadow-lg hover:shadow-xl transition-shadow relative">
              <button
                type="button"
                onClick={() => setShowStatsInfoBubble((v) => !v)}
                className="absolute top-2 right-2 w-5 h-5 rounded-full bg-white/25 hover:bg-white/40 flex items-center justify-center text-white text-xs font-bold focus:outline-none focus:ring-2 focus:ring-white/50"
                aria-label="Informasi sumber data"
              >
                i
              </button>
              <div className="text-2xl sm:text-3xl font-bold mb-1">{stats.topRated}</div>
              <div className="text-xs sm:text-sm opacity-90">Top Rated</div>
              <div className="text-xs mt-1 opacity-75">rating ≥ 4.5</div>
            </div>

            <div className="bg-gradient-to-br from-purple-500 to-pink-600 rounded-xl p-4 sm:p-5 text-white shadow-lg hover:shadow-xl transition-shadow relative">
              <button
                type="button"
                onClick={() => setShowStatsInfoBubble((v) => !v)}
                className="absolute top-2 right-2 w-5 h-5 rounded-full bg-white/25 hover:bg-white/40 flex items-center justify-center text-white text-xs font-bold focus:outline-none focus:ring-2 focus:ring-white/50"
                aria-label="Informasi sumber data"
              >
                i
              </button>
              <div className="text-2xl sm:text-3xl font-bold mb-1">{stats.totalReviews.toLocaleString('id-ID')}</div>
              <div className="text-xs sm:text-sm opacity-90">Total Ulasan</div>
              <div className="text-xs mt-1 opacity-75">semua tempat yang tampil</div>
            </div>

            {/* Bubble pesan sumber data */}
            {showStatsInfoBubble && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  aria-hidden="true"
                  onClick={() => setShowStatsInfoBubble(false)}
                />
                <div className="absolute left-1/2 -translate-x-1/2 top-full mt-3 z-20 w-[min(90vw,320px)] sm:w-80 px-4 py-3 bg-white dark:bg-zinc-800 rounded-xl shadow-xl border border-gray-200 dark:border-zinc-600 text-left">
                  <p className="text-sm text-gray-700 dark:text-gray-300">
                    Data dan informasi ini berdasarkan <span className="font-semibold">Places API</span> per tahun <span className="font-semibold">2025</span>.
                  </p>
                  <button
                    type="button"
                    onClick={() => setShowStatsInfoBubble(false)}
                    className="mt-2 text-xs text-amber-600 dark:text-amber-500 hover:underline font-medium"
                  >
                    Tutup
                  </button>
                </div>
              </>
            )}
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
            <div className="flex flex-wrap gap-2 sm:gap-3 items-center">
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
              <button
                type="button"
                onClick={handleOpenSuggestModal}
                className="px-3 sm:px-4 py-2 rounded-full text-sm font-medium bg-white dark:bg-gray-800 text-indigo-600 dark:text-indigo-400 border border-dashed border-indigo-400 dark:border-indigo-500 hover:bg-indigo-50 dark:hover:bg-indigo-900/20 transition-all duration-200"
                title="Sarankan preferensi yang kamu butuhkan"
              >
                + Sarankan preferensi
              </button>
            </div>
            {selectedPills.length > 0 && (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={handleConfirmPills}
                  disabled={pillRecommendLoading}
                  className="px-3 sm:px-4 py-2 rounded-full text-sm font-medium bg-indigo-600 text-white shadow-md hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed transition-all duration-200"
                  title="Konfirmasi preferensi dan lihat rekomendasi"
                >
                  {pillRecommendLoading ? 'Menganalisis...' : 'OK'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedPills([]);
                    setConfirmedPills([]);
                    setLlmRecommendations([]);
                  }}
                  className="px-3 sm:px-4 py-2 rounded-full text-sm font-medium bg-gray-200 dark:bg-gray-600 text-gray-800 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-gray-500 transition-all duration-200"
                >
                  Hapus semua filter
                </button>
              </div>
            )}

            {/* Modal: Ingin menyarankan preferensimu? */}
            {showSuggestModal && (
              <>
                <div
                  className="fixed inset-0 bg-black/50 z-[100]"
                  aria-hidden="true"
                  onClick={handleCloseSuggestModal}
                />
                <div
                  className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[min(90vw,420px)] bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-2xl shadow-2xl z-[101]"
                  role="dialog"
                  aria-labelledby="suggest-modal-title"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="p-4 sm:p-5">
                    <div className="flex items-center justify-between mb-4">
                      <h2 id="suggest-modal-title" className="text-lg font-semibold text-gray-800 dark:text-gray-200">
                        Ingin menyarankan preferensimu?
                      </h2>
                      <button
                        type="button"
                        onClick={handleCloseSuggestModal}
                        className="p-1.5 rounded-lg text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                        aria-label="Tutup"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                    <form onSubmit={handleSuggestSubmit} className="space-y-4">
                      <div>
                        <label htmlFor="preference-input" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Apa preferensi yang kamu perlu/butuhkan?
                        </label>
                        <input
                          id="preference-input"
                          type="text"
                          value={preferenceInput}
                          onChange={(e) => setPreferenceInput(e.target.value)}
                          placeholder="Contoh: area smoking, tempat kerja kelompok"
                          className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-500 focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                        />
                      </div>
                      <div>
                        <label htmlFor="reason-input" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Alasan preferensimu perlu dipertimbangkan
                        </label>
                        <textarea
                          id="reason-input"
                          value={reasonInput}
                          onChange={(e) => setReasonInput(e.target.value)}
                          placeholder="Jelaskan mengapa preferensi ini penting untuk kamu"
                          rows={3}
                          className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-500 focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none"
                        />
                      </div>
                      {submitError && (
                        <p className="text-sm text-red-600 dark:text-red-400">{submitError}</p>
                      )}
                      {submitSuccess && (
                        <p className="text-sm text-green-600 dark:text-green-400">{submitSuccess}</p>
                      )}
                      <div className="flex gap-2 pt-1">
                        <button
                          type="submit"
                          disabled={submitLoading}
                          className="flex-1 px-4 py-2 text-sm font-medium rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          {submitLoading ? 'Menyimpan...' : 'Simpan'}
                        </button>
                        <button
                          type="button"
                          onClick={handleCloseSuggestModal}
                          className="px-4 py-2 text-sm font-medium rounded-lg bg-gray-200 dark:bg-gray-600 text-gray-800 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-gray-500 transition-colors"
                        >
                          Batal
                        </button>
                      </div>
                    </form>
                  </div>
                </div>
              </>
            )}

            {/* Popup: arahkan login saat guest mengirim saran */}
            {showLoginPrompt && (
              <>
                <div
                  className="fixed inset-0 bg-black/40 z-[102]"
                  aria-hidden="true"
                  onClick={() => setShowLoginPrompt(false)}
                />
                <div
                  className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[min(90vw,320px)] bg-white dark:bg-gray-800 border-2 border-indigo-200 dark:border-indigo-700 rounded-2xl shadow-2xl p-4 z-[103]"
                  role="alertdialog"
                  aria-labelledby="login-prompt-title"
                  aria-describedby="login-prompt-desc"
                >
                  <p id="login-prompt-title" className="text-sm font-semibold text-gray-800 dark:text-gray-200 mb-1">
                    Perlu login
                  </p>
                  <p id="login-prompt-desc" className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                    Silakan login terlebih dahulu untuk mengirim saran preferensi.
                  </p>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setShowLoginPrompt(false);
                        navigate('/login');
                      }}
                      className="flex-1 px-3 py-2 text-sm font-medium rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition-colors"
                    >
                      Login
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowLoginPrompt(false)}
                      className="px-3 py-2 text-sm font-medium rounded-lg bg-gray-200 dark:bg-gray-600 text-gray-800 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-gray-500 transition-colors"
                    >
                      Tutup
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {/* Featured Coffee Shops */}
        {!error && !isLoading && featuredShops.length > 0 && !searchTerm && !confirmedPills.length && (
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
        {!error && !isLoading && coffeeShops.length > 0 && !searchTerm && !confirmedPills.length && (
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

        {/* Top Rated Coffee Shops (4.5-5.0) */}
        {!error && !isLoading && topRatedShops.length > 0 && !searchTerm && !confirmedPills.length && (
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
        {!error && !isLoading && newestShops.length > 0 && !searchTerm && !confirmedPills.length && (
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
        {!error && !isLoading && recentlyViewedShops.length > 0 && !searchTerm && !confirmedPills.length && (
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

        {/* Coffee shop dalam radius - di atas peta All Coffee Shops */}
        {!error && !isLoading && coffeeShops.length > 0 && !searchTerm && (
          <CoffeeShopRadiusMap
            userLocation={userLocation}
            radiusMeters={radiusMeters}
            setRadiusMeters={setRadiusMeters}
            locationLoading={locationLoading}
            locationError={locationError}
            getCurrentLocation={getCurrentLocation}
            shopsInRadius={shopsInRadius}
          />
        )}

        {/* Coffee Shop Map - Tampilkan di atas judul All Coffee Shops */}
        {!error && !isLoading && coffeeShops.length > 0 && !searchTerm && (
          <CoffeeShopMap coffeeShops={coffeeShops} />
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
              <div
                key={shop.place_id}
                className="block hover:shadow-2xl transition duration-300"
              >
                <CoffeeShopCard
                  shop={shop}
                  recommendationExplanation={
                    recommendationExplanationByShopName[(shop.name || '').trim().toLowerCase()]
                  }
                />
              </div>
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
        
        {!error && !isLoading && filteredShops.length === 0 && (selectedPills.length > 0 || confirmedPills.length > 0) && (
          <div className="text-center py-12">
            <svg className="mx-auto h-12 w-12 text-gray-400 dark:text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M12 20a8 8 0 100-16 8 8 0 000 16z" />
            </svg>
            <h3 className="mt-2 text-lg font-medium text-gray-900 dark:text-gray-100">
              {pillRecommendLoading ? 'Menganalisis rekomendasi...' : 'Tidak ada coffee shop yang sesuai'}
            </h3>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              {pillRecommendLoading ? 'Tunggu sebentar.' : 'Tidak ada coffee shop yang memiliki review sesuai dengan preferensi yang Anda pilih.'}
            </p>
            <button
              onClick={() => {
                setSelectedPills([]);
                setConfirmedPills([]);
                setLlmRecommendations([]);
              }}
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

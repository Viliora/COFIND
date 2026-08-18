import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Link } from 'react-router-dom';
import CoffeeShopCard from '../components/CoffeeShopCard';
import HeroSwiper from '../components/HeroSwiper';
import CoffeeShopMap from '../components/CoffeeShopMap';
import CoffeeShopRadiusMap from '../components/CoffeeShopRadiusMap';
import RecommendationModal from '../components/RecommendationModal';
import RecommendationProgressOverlay from '../components/RecommendationProgressOverlay';
import { streamRecommendations } from '../services/recommendationStream';
import {
  CONTEXT_PILL_OPTIONS,
  CONTEXT_PILL_THEMES,
  CONTEXT_PILL_THEME_DEFAULT,
} from '../constants/reviewPills';
import { preloadFeaturedImages } from '../utils/imagePreloader';
import { ensureCoffeeShopImageMap } from '../utils/coffeeShopImages';
import { getRecentlyViewedWithDetails } from '../utils/recentlyViewed';
import heroBgImage from '../assets/1R modern cafe 1.5.jpg';
import { useAuth } from '../context/authContext';
import { authService } from '../services/authService';
// API Configuration
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';

/** Sama seperti CoffeeShopCard: rating & total ulasan dari data Google Maps */
function getGoogleRating(shop) {
  return shop?.rating != null ? Number(shop.rating) : 0;
}

function getGoogleReviewCount(shop) {
  const n = Number(shop?.total_reviews ?? shop?.user_ratings_total ?? 0);
  return Number.isFinite(n) ? n : 0;
}

function normalizeMatchText(value) {
  return String(value ?? '').trim().toLowerCase();
}

/** Urut katalog utama: rating tertinggi dulu, lalu jumlah review Google (banyak → sedikit) */
function sortShopsByGoogleMaps(shops) {
  return [...shops].sort((a, b) => {
    const rDiff = getGoogleRating(b) - getGoogleRating(a);
    if (rDiff !== 0) return rDiff;
    return getGoogleReviewCount(b) - getGoogleReviewCount(a);
  });
}

export default function ShopList() {
  const { loading: authLoading, user } = useAuth();
  const [coffeeShops, setCoffeeShops] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [selectedPills, setSelectedPills] = useState([]);
  const [confirmedPills, setConfirmedPills] = useState([]);
  const [llmRecommendations, setLlmRecommendations] = useState([]);
  const [pillRecommendLoading, setPillRecommendLoading] = useState(false);
  const [pillRecommendProgress, setPillRecommendProgress] = useState(null);
  const [pillRecommendError, setPillRecommendError] = useState('');
  const [recommendationNotification, setRecommendationNotification] = useState(null);
  const [showRecommendationModal, setShowRecommendationModal] = useState(false);
  const [showPillLoginModal, setShowPillLoginModal] = useState(false);
  const [showPreferenceSuggestModal, setShowPreferenceSuggestModal] = useState(false);
  const [suggestLabel, setSuggestLabel] = useState('');
  const [suggestDescription, setSuggestDescription] = useState('');
  const [suggestSubmitting, setSuggestSubmitting] = useState(false);
  const [suggestError, setSuggestError] = useState('');
  const [suggestSuccess, setSuggestSuccess] = useState('');
  const featuredScrollRef = useRef(null);
  const hasLoadedRef = useRef(false);

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

  const isPillPreferenceAvailable = Boolean(user) && !authLoading;

  // Pill + rekomendasi konteks hanya untuk pengguna login; bersihkan saat logout
  useEffect(() => {
    if (authLoading) return;
    if (user) return;
    setSelectedPills([]);
    setConfirmedPills([]);
    setLlmRecommendations([]);
    setPillRecommendError('');
    setShowRecommendationModal(false);
    setRecommendationNotification(null);
    setShowPillLoginModal(false);
  }, [authLoading, user]);

  useEffect(() => {
    if (user) setShowPillLoginModal(false);
  }, [user]);

  useEffect(() => {
    if (!showPillLoginModal) return undefined;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKeyDown = (e) => {
      if (e.key === 'Escape') setShowPillLoginModal(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [showPillLoginModal]);

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

  useEffect(() => {
    if (!recommendationNotification) return undefined;
    const timer = setTimeout(() => setRecommendationNotification(null), 3200);
    return () => clearTimeout(timer);
  }, [recommendationNotification]);

  // Dapatkan Featured Coffee Shops (Top 5 berdasarkan scoring) - menggunakan useMemo untuk optimasi
  const featuredShops = useMemo(() => {
    if (coffeeShops.length === 0) return [];
    
    const calculateFeaturedScore = (shop) => {
      const rating = getGoogleRating(shop);
      const reviews = getGoogleReviewCount(shop);
      const maxReviews = Math.max(...coffeeShops.map((s) => getGoogleReviewCount(s)), 0);
      const normalizedReviews = maxReviews > 0 ? reviews / maxReviews : 0;
      const hasCompleteData = shop.address && rating > 0 && reviews > 0 ? 1 : 0.5;
      
      // Scoring: rating (40%) + popularity (30%) + data completeness (30%)
      return (rating * 0.4) + (normalizedReviews * 5 * 0.3) + (hasCompleteData * 5 * 0.3);
    };

    return coffeeShops
      .filter((shop) => getGoogleRating(shop) >= 4.0) // Minimal rating Google 4.0
      .map(shop => ({ ...shop, featuredScore: calculateFeaturedScore(shop) }))
      .sort((a, b) => b.featuredScore - a.featuredScore)
      .slice(0, 5);
  }, [coffeeShops]);

  // Dapatkan Coffee Shop Terbaru (rating bagus tapi review masih sedikit)
  const newestShops = useMemo(() => {
    if (coffeeShops.length === 0) return [];
    
    return coffeeShops
      .filter(
        (shop) => getGoogleRating(shop) >= 4.0 && getGoogleReviewCount(shop) < 100
      )
      .sort((a, b) => {
        // Sort berdasarkan rating Google tertinggi, lalu review paling sedikit (hidden gem)
        const ratingA = getGoogleRating(a);
        const ratingB = getGoogleRating(b);
        const reviewsA = getGoogleReviewCount(a);
        const reviewsB = getGoogleReviewCount(b);
        
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
      .filter((shop) => {
        const rating = getGoogleRating(shop);
        return rating >= 4.5 && rating <= 5.0;
      })
      .sort((a, b) => {
        const ratingA = getGoogleRating(a);
        const ratingB = getGoogleRating(b);
        if (ratingB !== ratingA) {
          return ratingB - ratingA;
        }
        return getGoogleReviewCount(b) - getGoogleReviewCount(a);
      });
  }, [coffeeShops]);

  // Dapatkan Recently Viewed Coffee Shops
  const recentlyViewedShops = useMemo(() => {
    return getRecentlyViewedWithDetails(coffeeShops);
  }, [coffeeShops]);

  /** Daftar penuh diurutkan seperti katalog utama (Google rating + total review) — untuk hero, dll. */
  const coffeeShopsByGoogleOrder = useMemo(
    () => sortShopsByGoogleMaps(coffeeShops),
    [coffeeShops]
  );

  const getFilteredShopsByCategory = (shops) => sortShopsByGoogleMaps(shops);

  const recommendationFields = CONTEXT_PILL_OPTIONS;

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

  const pillLabelByValue = useMemo(
    () => Object.fromEntries(CONTEXT_PILL_OPTIONS.map((p) => [p.value, p.label])),
    [],
  );

  // Satu konteks aktivitas per waktu (pill tunggal)
  const handlePillClick = (pillValue) => {
    if (authLoading) return;
    if (!user) {
      setShowPillLoginModal(true);
      return;
    }
    if (pillRecommendLoading) return;
    setPillRecommendError('');
    setSelectedPills((prev) => {
      if (prev.includes(pillValue)) return [];
      return [pillValue];
    });
  };

  const openPreferenceSuggestModal = () => {
    if (authLoading) return;
    if (!user) {
      setShowPillLoginModal(true);
      return;
    }
    setSuggestError('');
    setSuggestSuccess('');
    setShowPreferenceSuggestModal(true);
  };

  const closePreferenceSuggestModal = () => {
    if (suggestSubmitting) return;
    setShowPreferenceSuggestModal(false);
    setSuggestError('');
    setSuggestSuccess('');
  };

  const handleSubmitPreferenceSuggestion = async (event) => {
    event.preventDefault();
    const label = suggestLabel.trim();
    if (!label) {
      setSuggestError('Isi nama preferensi yang ingin Anda sarankan.');
      return;
    }
    const token = authService.getToken();
    if (!token) {
      setShowPreferenceSuggestModal(false);
      setShowPillLoginModal(true);
      return;
    }

    setSuggestSubmitting(true);
    setSuggestError('');
    setSuggestSuccess('');
    try {
      const res = await fetch(`${API_BASE}/api/preference-suggestions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          label,
          description: suggestDescription.trim() || undefined,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data?.message || 'Gagal mengirim saran preferensi.');
      }
      setSuggestSuccess(data?.message || 'Saran berhasil dikirim ke admin.');
      setSuggestLabel('');
      setSuggestDescription('');
    } catch (err) {
      setSuggestError(err?.message || 'Gagal mengirim saran preferensi.');
    } finally {
      setSuggestSubmitting(false);
    }
  };

  const hasConfirmedRecommendation = useMemo(
    () => confirmedPills.length > 0,
    [confirmedPills],
  );

  const hasPendingPillChanges = useMemo(() => {
    const selectedKey = [...selectedPills].sort().join('|');
    const confirmedKey = [...confirmedPills].sort().join('|');
    return selectedKey !== confirmedKey;
  }, [selectedPills, confirmedPills]);

  const requestPillRecommendations = async (pillValues) => {
    if (!isPillPreferenceAvailable) return;
    if (!Array.isArray(pillValues) || pillValues.length === 0) return;
    const token = authService.getToken();
    if (!token) {
      setPillRecommendError('Silakan login untuk mendapatkan rekomendasi konteks.');
      setRecommendationNotification({
        type: 'error',
        message: 'Silakan login untuk mendapatkan rekomendasi konteks.',
      });
      return;
    }
    setConfirmedPills([...pillValues]);
    setPillRecommendLoading(true);
    setPillRecommendProgress(null);
    setPillRecommendError('');
    setLlmRecommendations([]);
    setShowRecommendationModal(false);
    try {
      const { statusCode, body: data } = await streamRecommendations({
        apiBase: API_BASE,
        token,
        preferences: pillValues,
        onProgress: setPillRecommendProgress,
      });

      if (statusCode < 200 || statusCode >= 300) {
        throw new Error(data?.message || 'Rekomendasi AI sedang gagal diproses. Coba lagi.');
      }
      if (!data) {
        throw new Error('Rekomendasi AI mengirim respons yang tidak bisa dibaca.');
      }

      if (data.status === 'success' && Array.isArray(data.recommendations)) {
        setLlmRecommendations(data.recommendations);
        if (data.recommendations.length === 0) {
          const emptyMessage = data?.message
            || 'Maaf, saat ini belum ada coffee shop yang cocok dengan konteks ini. Coba konteks lain.';
          setPillRecommendError(emptyMessage);
          setRecommendationNotification({
            type: 'error',
            message: emptyMessage,
          });
        }
        setShowRecommendationModal(true);
      } else {
        setPillRecommendError(data?.message || 'Rekomendasi AI belum bisa ditampilkan.');
        setLlmRecommendations([]);
        setShowRecommendationModal(false);
        if (data?.message) {
          setRecommendationNotification({
            type: 'error',
            message: data.message,
          });
        }
      }
    } catch (err) {
      console.error('[ShopList] recommend-by-preferences error:', err);
      setPillRecommendError(err.message || 'Gagal menghubungi layanan rekomendasi AI.');
      setLlmRecommendations([]);
      setShowRecommendationModal(false);
      setRecommendationNotification({
        type: 'error',
        message: err.message || 'Gagal menghubungi layanan rekomendasi AI.',
      });
    } finally {
      setPillRecommendLoading(false);
      setPillRecommendProgress(null);
    }
  };

  // Peta shop berdasarkan place_id / nama (untuk modal rekomendasi)
  const shopsByKey = useMemo(() => {
    const map = {};
    coffeeShops.forEach((shop) => {
      if (shop.place_id) map[shop.place_id] = shop;
      if (shop.name) map[normalizeMatchText(shop.name)] = shop;
    });
    return map;
  }, [coffeeShops]);

  // Konfirmasi pill konteks di beranda → POST rekomendasi review-based
  const handleConfirmPills = async () => {
    if (!isPillPreferenceAvailable || selectedPills.length === 0) return;
    await requestPillRecommendations(selectedPills);
  };

  // Katalog homepage tetap utuh; hasil AI ditampilkan lewat overlay terpisah
  const filteredShops = getFilteredShopsByCategory(coffeeShops);

  // Statistics: dari data yang tampil (filteredShops) dan field yang dipakai aplikasi (total_reviews / user_ratings_total, rating)
  const stats = useMemo(() => {
    const list = filteredShops;
    const total = list.length;
    const sumRating = list.reduce((sum, shop) => sum + getGoogleRating(shop), 0);
    const avgRating = total > 0 ? (sumRating / total).toFixed(1) : '0';
    const topRated = list.filter((shop) => {
      const r = getGoogleRating(shop);
      return r >= 4.5 && r <= 5;
    }).length;
    const totalReviews = list.reduce((sum, shop) => sum + getGoogleReviewCount(shop), 0);
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
      {recommendationNotification && (
        <div
          className={`fixed top-8 left-1/2 z-[120] -translate-x-1/2 rounded-lg px-6 py-3 text-sm font-medium text-white shadow-lg transition-all duration-300 ${
            recommendationNotification.type === 'error'
              ? 'bg-orange-500 dark:bg-orange-600'
              : 'bg-emerald-500 dark:bg-emerald-600'
          }`}
          role="alert"
          aria-live="polite"
        >
          {recommendationNotification.message}
        </div>
      )}

      {/* Hero Swiper - Auto-playing carousel */}
      {!error && !isLoading && coffeeShops.length > 0 && (
        <HeroSwiper coffeeShops={coffeeShopsByGoogleOrder} />
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
              <div className="text-xs mt-1 opacity-75">di Pontianak</div>
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

        {/* Konteks aktivitas (pill) — khusus pengguna login */}
        {!error && !isLoading && coffeeShops.length > 0 && (
          <div className="mb-6 sm:mb-8">
            <div className="mb-3">
              <h3 className="text-sm sm:text-base font-semibold text-gray-700 dark:text-gray-300 mb-2">
                Sesuaikan preferensi anda:
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                Pilih satu pill yang sesuai dengan prefrensi Coffee Shop yang ingin anda kunjungi
              </p>
            </div>
            <div className="flex flex-wrap gap-2 sm:gap-3 items-center">
              {recommendationFields.map((field) => {
                const isSelected = selectedPills.includes(field.value);
                const theme = CONTEXT_PILL_THEMES[field.value] || CONTEXT_PILL_THEME_DEFAULT;
                const pillDisabled = authLoading || pillRecommendLoading;
                return (
                  <button
                    key={field.value}
                    type="button"
                    disabled={pillDisabled}
                    onClick={() => handlePillClick(field.value)}
                    title={
                      !user && !authLoading
                        ? 'Login untuk menggunakan fitur analisis LLM'
                        : undefined
                    }
                    className={`
                      px-3 sm:px-4 py-2 rounded-full text-sm font-semibold
                      transition-shadow duration-200 ease-out
                      focus:outline-none focus-visible:ring-2 focus-visible:ring-white/80 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-900/20 dark:focus-visible:ring-offset-black/30
                      disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none
                      ${isSelected ? theme.selected : theme.idle}
                    `}
                  >
                    {field.label}
                    {isSelected && (
                      <span className="ml-1.5 text-xs opacity-95" aria-hidden>
                        ✓
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
            <div className="mt-3">
              <button
                type="button"
                onClick={openPreferenceSuggestModal}
                disabled={authLoading || pillRecommendLoading}
                className="inline-flex items-center gap-1.5 text-xs sm:text-sm font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-300 dark:hover:text-indigo-200 underline-offset-2 hover:underline disabled:opacity-50 disabled:cursor-not-allowed disabled:no-underline"
                title={
                  !user && !authLoading
                    ? 'Login untuk mengirim saran preferensi'
                    : 'Sarankan preferensi baru ke admin'
                }
              >
                Tidak ada yang cocok? Sarankan preferensi
              </button>
            </div>
            {isPillPreferenceAvailable && selectedPills.length > 0 && (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={handleConfirmPills}
                  disabled={pillRecommendLoading}
                  className="px-3 sm:px-4 py-2 rounded-full text-sm font-medium bg-indigo-600 text-white shadow-md hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed transition-all duration-200"
                  title="Konfirmasi konteks dan lihat rekomendasi"
                >
                  {pillRecommendLoading ? 'Menganalisis...' : 'OK'}
                </button>
              </div>
            )}

            {hasConfirmedRecommendation && (
              <div className="mt-3 space-y-2">
                <p className="text-sm text-gray-600 dark:text-gray-300">
                  {confirmedPills.length > 0 && (
                    <>
                      Konteks:{' '}
                      <span className="font-medium text-gray-800 dark:text-gray-100">
                        {confirmedPills.map((v) => pillLabelByValue[v] || v).join(', ')}
                      </span>
                    </>
                  )}
                </p>
                {hasPendingPillChanges && !pillRecommendLoading && (
                  <p className="text-sm text-amber-700 dark:text-amber-300">
                    Konteks pill berubah. Tekan OK lagi untuk memperbarui rekomendasi.
                  </p>
                )}
                {!!pillRecommendError && !pillRecommendLoading && (
                  <p className="text-sm text-red-600 dark:text-red-300">
                    {pillRecommendError}
                  </p>
                )}
                {!pillRecommendLoading && hasConfirmedRecommendation && (
                  <div className="flex flex-wrap items-center gap-3">
                    <p className={`text-sm ${llmRecommendations.length > 0 ? 'text-emerald-700 dark:text-emerald-300' : 'text-gray-600 dark:text-gray-300'}`}>
                      {llmRecommendations.length > 0
                        ? `Menampilkan ${llmRecommendations.length} rekomendasi (hingga 3) yang punya bukti ulasan relevan untuk konteks yang dipilih.`
                        : 'Buka overlay untuk melihat status rekomendasi terakhir Anda.'}
                    </p>
                    <button
                      type="button"
                      onClick={() => setShowRecommendationModal(true)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs sm:text-sm font-semibold bg-gradient-to-r from-indigo-500 to-violet-500 text-white shadow-sm hover:from-indigo-600 hover:to-violet-600 transition-colors"
                      title="Lihat hasil rekomendasi AI pada overlay"
                    >
                      ✨ Lihat hasil AI
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Featured Coffee Shops */}
        {!error && !isLoading && featuredShops.length > 0 && (
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
        {!error && !isLoading && coffeeShops.length > 0 && (
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
        {!error && !isLoading && topRatedShops.length > 0 && (
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
        {!error && !isLoading && newestShops.length > 0 && (
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
        {!error && !isLoading && recentlyViewedShops.length > 0 && (
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
        {!error && !isLoading && coffeeShops.length > 0 && (
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
        {!error && !isLoading && coffeeShops.length > 0 && (
          <CoffeeShopMap coffeeShops={coffeeShops} />
        )}

        <div className="flex items-center justify-between mb-4 sm:mb-6 flex-wrap gap-2">
          <h2 className="text-xl sm:text-2xl md:text-3xl font-bold text-gray-800 dark:text-gray-200 border-b pb-2 flex-1">
            All Coffee Shops ({filteredShops.length})
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
                <CoffeeShopCard shop={shop} />
              </div>
            ))}
          </div>
        )}

        {!error && !isLoading && filteredShops.length === 0 && selectedPills.length === 0 && (
          <div className="text-center py-12">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M12 20a8 8 0 100-16 8 8 0 000 16z" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-gray-100">No coffee shops found</h3>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Check if the backend is returning data correctly.</p>
          </div>
        )}
        
      </main>

      {showPillLoginModal && (
        <div
          className="fixed inset-0 z-[105] flex items-center justify-center p-4 sm:p-6"
          role="dialog"
          aria-modal="true"
          aria-labelledby="pill-login-modal-title"
        >
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            aria-hidden="true"
            onClick={() => setShowPillLoginModal(false)}
          />
          <div className="relative z-10 w-full max-w-md rounded-2xl border border-gray-200 bg-white p-6 shadow-2xl dark:border-gray-700 dark:bg-gray-900">
            <h3
              id="pill-login-modal-title"
              className="text-lg font-bold text-gray-900 dark:text-white"
            >
              Login diperlukan
            </h3>
            <p className="mt-3 text-sm leading-relaxed text-gray-600 dark:text-gray-300">
              Login untuk menggunakan fitur analisis LLM — dapatkan rekomendasi coffee shop berdasarkan konteks
              aktivitas dan ulasan pengunjung.
            </p>
            <div className="mt-6 flex flex-wrap items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowPillLoginModal(false)}
                className="rounded-full px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-800"
              >
                Tutup
              </button>
              <Link
                to="/login"
                onClick={() => setShowPillLoginModal(false)}
                className="inline-flex rounded-full bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-gray-900"
              >
                Masuk
              </Link>
            </div>
          </div>
        </div>
      )}

      {showPreferenceSuggestModal && (
        <div
          className="fixed inset-0 z-[105] flex items-center justify-center p-4 sm:p-6"
          role="dialog"
          aria-modal="true"
          aria-labelledby="preference-suggest-modal-title"
        >
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            aria-hidden="true"
            onClick={closePreferenceSuggestModal}
          />
          <div className="relative z-10 w-full max-w-md rounded-2xl border border-gray-200 bg-white p-6 shadow-2xl dark:border-gray-700 dark:bg-gray-900">
            <h3
              id="preference-suggest-modal-title"
              className="text-lg font-bold text-gray-900 dark:text-white"
            >
              Sarankan preferensi baru
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-gray-600 dark:text-gray-300">
              Tidak menemukan pill yang sesuai? Kirim saran ke admin agar preferensi tersebut dapat ditambahkan.
            </p>

            {suggestSuccess ? (
              <div className="mt-5 space-y-4">
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-800/60 dark:bg-emerald-950/40 dark:text-emerald-200">
                  {suggestSuccess}
                </div>
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={closePreferenceSuggestModal}
                    className="rounded-full bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700"
                  >
                    Tutup
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleSubmitPreferenceSuggestion} className="mt-5 space-y-4">
                <div>
                  <label
                    htmlFor="suggest-preference-label"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1"
                  >
                    Nama preferensi <span className="text-red-500">*</span>
                  </label>
                  <input
                    id="suggest-preference-label"
                    type="text"
                    value={suggestLabel}
                    onChange={(e) => setSuggestLabel(e.target.value)}
                    maxLength={80}
                    disabled={suggestSubmitting}
                    className="w-full rounded-xl border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
                  />
                </div>
                <div>
                  <label
                    htmlFor="suggest-preference-description"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1"
                  >
                    Deskripsi singkat
                  </label>
                  <textarea
                    id="suggest-preference-description"
                    value={suggestDescription}
                    onChange={(e) => setSuggestDescription(e.target.value)}
                    maxLength={500}
                    rows={3}
                    placeholder="Jelaskan preferensi yang ingin anda tambahkan..."
                    disabled={suggestSubmitting}
                    className="w-full rounded-xl border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
                  />
                </div>
                {!!suggestError && (
                  <p className="text-sm text-red-600 dark:text-red-300">{suggestError}</p>
                )}
                <div className="flex flex-wrap items-center justify-end gap-2">
                  <button
                    type="button"
                    onClick={closePreferenceSuggestModal}
                    disabled={suggestSubmitting}
                    className="rounded-full px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-60 dark:text-gray-200 dark:hover:bg-gray-800"
                  >
                    Batal
                  </button>
                  <button
                    type="submit"
                    disabled={suggestSubmitting}
                    className="inline-flex rounded-full bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-gray-900"
                  >
                    {suggestSubmitting ? 'Mengirim...' : 'Kirim saran'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      <RecommendationProgressOverlay
        open={pillRecommendLoading}
        progress={pillRecommendProgress}
      />

      <RecommendationModal
        isOpen={showRecommendationModal}
        onClose={() => setShowRecommendationModal(false)}
        recommendations={llmRecommendations}
        shopsByKey={shopsByKey}
        confirmedPills={confirmedPills}
      />
    </div>
  );
}

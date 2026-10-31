import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Link } from 'react-router-dom';
import CoffeeShopCard, { SHOP_CATALOG_GRID_CLASS, SHOP_CAROUSEL_ITEM_CLASS } from '../components/CoffeeShopCard';
import HeroSwiper from '../components/HeroSwiper';
import CoffeeShopMap from '../components/CoffeeShopMap';
import RecommendationModal from '../components/RecommendationModal';
import RecommendationProgressOverlay from '../components/RecommendationProgressOverlay';
import FacilityAttributePicker from '../components/FacilityAttributePicker';
import { streamRecommendations } from '../services/recommendationStream';
import {
  CONTEXT_PILL_OPTIONS,
  CONTEXT_PILL_THEMES,
  CONTEXT_PILL_THEME_DEFAULT,
  FACILITY_ATTRIBUTE_LABELS,
  FACILITY_ATTRIBUTE_OPTIONS,
} from '../constants/reviewPills';
import { preloadFeaturedImages } from '../utils/imagePreloader';
import { ensureCoffeeShopImageMap } from '../utils/coffeeShopImages';
import { getRecentlyViewedWithDetails } from '../utils/recentlyViewed';
import {
  applyLastRecommendationSession,
  loadLastRecommendationSession,
  saveLastRecommendationSession,
} from '../utils/lastRecommendationSession';
import heroBgImage from '../assets/1R modern cafe 1.5.jpg';
import { useAuth } from '../context/authContext';
import { authService } from '../services/authService';
import LatestReviewsAside from '../components/LatestReviewsAside';
// API Configuration
import { API_BASE } from '../config/apiBase.js';

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

const CATALOG_PAGE_SIZE = 10;

function HorizontalCatalogScroller({ children, className = '' }) {
  const scrollerRef = useRef(null);

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return undefined;

    const onWheel = (event) => {
      if (Math.abs(event.deltaX) > Math.abs(event.deltaY)) return;

      const maxScroll = el.scrollWidth - el.clientWidth;
      if (maxScroll <= 1) return;

      let delta = event.deltaY;
      if (event.deltaMode === 1) delta *= 16;
      if (event.deltaMode === 2) delta *= el.clientHeight;
      delta *= 0.28;

      const goingRight = delta > 0;
      const atStart = el.scrollLeft <= 1;
      const atEnd = el.scrollLeft >= maxScroll - 1;

      if ((goingRight && atEnd) || (!goingRight && atStart)) return;

      event.preventDefault();
      el.scrollLeft += delta;
    };

    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

  return (
    <div
      ref={scrollerRef}
      className={`flex gap-4 overflow-x-auto pb-4 snap-x snap-proximity ${className}`}
    >
      {children}
    </div>
  );
}

export default function ShopList() {
  const { loading: authLoading, user } = useAuth();
  const [coffeeShops, setCoffeeShops] = useState([]);
  /** Agregat dari DB (catalog_stats di respons /api/coffeeshops). */
  const [catalogStats, setCatalogStats] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [selectedPills, setSelectedPills] = useState([]);
  const [confirmedPills, setConfirmedPills] = useState([]);
  const [selectedAttributes, setSelectedAttributes] = useState([]);
  const [confirmedAttributes, setConfirmedAttributes] = useState([]);
  const [llmRecommendations, setLlmRecommendations] = useState([]);
  const [llmOtherOptions, setLlmOtherOptions] = useState([]);
  const [pillRecommendLoading, setPillRecommendLoading] = useState(false);
  const [pillRecommendProgress, setPillRecommendProgress] = useState(null);
  /** Timestamp ms saat overlay SSE dibuka (awal stream rekomendasi). */
  const [recommendationRunStartedAt, setRecommendationRunStartedAt] = useState(null);
  /** Total detik run terakhir yang sukses — ditampilkan di RecommendationModal. */
  const [recommendationTotalSeconds, setRecommendationTotalSeconds] = useState(null);
  const [pillRecommendError, setPillRecommendError] = useState('');
  const [recommendationNotification, setRecommendationNotification] = useState(null);
  const [showRecommendationModal, setShowRecommendationModal] = useState(false);
  const [showPillLoginModal, setShowPillLoginModal] = useState(false);
  /** 'pill' | 'free_text' — teks modal login */
  const [pillLoginModalContext, setPillLoginModalContext] = useState('pill');
  const [searchKeyword, setSearchKeyword] = useState('');
  const [confirmedSearchKeyword, setConfirmedSearchKeyword] = useState('');
  /** Pesan framing dari backend (negatif / abstention parsial), ditampilkan di modal. */
  const [recommendationResponseNotice, setRecommendationResponseNotice] = useState('');
  const hasLoadedRef = useRef(false);
  const [catalogVisibleCount, setCatalogVisibleCount] = useState(CATALOG_PAGE_SIZE);

  // Lokasi saat ini & radius (peta di atas All Coffee Shops + modal rekomendasi)
  const [userLocation, setUserLocation] = useState(null);
  const [radiusMeters, setRadiusMeters] = useState(2000);
  const [locationLoading, setLocationLoading] = useState(false);
  const [locationError, setLocationError] = useState(null);
  const [showLocationChoiceModal, setShowLocationChoiceModal] = useState(false);
  const [locationChoiceSubmitting, setLocationChoiceSubmitting] = useState(false);
  // Title halaman
  useEffect(() => {
    document.title = 'Beranda - Cofind';
    return () => { document.title = 'Cofind'; };
  }, []);

  const isPillPreferenceAvailable = Boolean(user) && !authLoading;

  useEffect(() => {
    const validActivities = new Set(CONTEXT_PILL_OPTIONS.map((p) => p.value));
    const validAttrs = new Set(FACILITY_ATTRIBUTE_OPTIONS.map((p) => p.value));
    const prune = (list, allowed) => list.filter((value) => allowed.has(value));
    setSelectedPills((prev) => prune(prev, validActivities));
    setConfirmedPills((prev) => prune(prev, validActivities));
    setSelectedAttributes((prev) => prune(prev, validAttrs));
    setConfirmedAttributes((prev) => prune(prev, validAttrs));
  }, []);

  // Pill + rekomendasi konteks hanya untuk pengguna login; bersihkan saat logout
  useEffect(() => {
    if (authLoading) return;
    if (user) return;
    setSelectedPills([]);
    setConfirmedPills([]);
    setSelectedAttributes([]);
    setConfirmedAttributes([]);
    setLlmRecommendations([]);
    setLlmOtherOptions([]);
    setPillRecommendError('');
    setShowRecommendationModal(false);
    setRecommendationNotification(null);
    setShowPillLoginModal(false);
  }, [authLoading, user]);

  useEffect(() => {
    if (user) setShowPillLoginModal(false);
  }, [user]);

  // Pulihkan rekomendasi AI terakhir (localStorage) saat user login / kembali ke beranda.
  useEffect(() => {
    if (authLoading || !user?.id) return;
    const session = loadLastRecommendationSession(user.id);
    if (!session) return;
    applyLastRecommendationSession(session, {
      setLlmRecommendations,
      setLlmOtherOptions,
      setConfirmedPills,
      setConfirmedAttributes,
      setConfirmedSearchKeyword,
      setRecommendationTotalSeconds,
    });
  }, [authLoading, user?.id]);

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
          if (result.catalog_stats && typeof result.catalog_stats === 'object') {
            setCatalogStats(result.catalog_stats);
          } else {
            setCatalogStats(null);
          }
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
          setCatalogStats(null);
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

  // Hidden gem: rating Google ≥ 4.4, total ulasan Google di bawah 100
  const newestShops = useMemo(() => {
    if (coffeeShops.length === 0) return [];
    
    return coffeeShops
      .filter(
        (shop) => getGoogleRating(shop) >= 4.4 && getGoogleReviewCount(shop) < 100
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

  const getCurrentLocationAsync = () => {
    setLocationError(null);
    setLocationLoading(true);
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        const message = 'Browser tidak mendukung geolokasi.';
        setLocationError(message);
        setLocationLoading(false);
        reject(new Error(message));
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const loc = { lat: pos.coords.latitude, lng: pos.coords.longitude };
          setUserLocation(loc);
          setLocationError(null);
          setLocationLoading(false);
          resolve(loc);
        },
        (err) => {
          const message = err.code === 1
            ? 'Akses lokasi ditolak. Izinkan lokasi di pengaturan browser.'
            : 'Tidak dapat mengambil lokasi. Coba lagi.';
          setLocationError(message);
          setLocationLoading(false);
          reject(new Error(message));
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
      );
    });
  };

  // Ambil lokasi saat ini (Browser Geolocation API) — untuk peta / kontrol cepat
  const getCurrentLocation = () => {
    getCurrentLocationAsync().catch(() => {});
  };

  // Satu konteks aktivitas per waktu (pill tunggal)
  const handlePillClick = (pillValue) => {
    if (authLoading) return;
    if (!user) {
      setPillLoginModalContext('pill');
      setShowPillLoginModal(true);
      return;
    }
    if (pillRecommendLoading) return;
    setPillRecommendError('');
    // Pill dan free text saling eksklusif: pilih pill menghapus free text aktif.
    if (searchKeyword.trim()) {
      setSearchKeyword('');
    }
    setSelectedPills((prev) => {
      if (prev.includes(pillValue)) {
        // Atribut lapis 2 hanya relevan selama ada konteks aktivitas terpilih.
        setSelectedAttributes([]);
        return [];
      }
      return [pillValue];
    });
  };

  const MAX_SEARCH_KEYWORD_CHARS = 100;
  const sanitizeFreeTextQuery = (value) =>
    String(value || '')
      .replace(/[^A-Za-z0-9, ]/g, '')
      .slice(0, MAX_SEARCH_KEYWORD_CHARS);

  // Pill dan free text saling eksklusif: isi salah satu saja per request.
  const openLoginModalForFreeText = () => {
    if (authLoading || user) return;
    setPillLoginModalContext('free_text');
    setShowPillLoginModal(true);
  };

  const handleSearchKeywordChange = (value) => {
    if (!user) return;
    const next = sanitizeFreeTextQuery(value);
    setSearchKeyword(next);
    if (next.trim() && (selectedPills.length > 0 || selectedAttributes.length > 0)) {
      setSelectedPills([]);
      setSelectedAttributes([]);
    }
  };

  const hasConfirmedRecommendation = useMemo(
    () => confirmedPills.length > 0 || confirmedSearchKeyword.trim().length > 0,
    [confirmedPills, confirmedSearchKeyword],
  );

  const hasViewableLastRecommendation = useMemo(
    () => Array.isArray(llmRecommendations) && llmRecommendations.length > 0,
    [llmRecommendations],
  );

  const hasPendingPillChanges = useMemo(() => {
    const selectedKey = [...selectedPills, ...selectedAttributes].sort().join('|');
    const confirmedKey = [...confirmedPills, ...confirmedAttributes].sort().join('|');
    return (
      selectedKey !== confirmedKey
      || searchKeyword.trim() !== confirmedSearchKeyword.trim()
    );
  }, [selectedPills, selectedAttributes, confirmedPills, confirmedAttributes, searchKeyword, confirmedSearchKeyword]);

  /** Banner + tombol utama untuk membuka modal rekomendasi tersimpan. */
  const showLastRecommendationBanner = useMemo(
    () => isPillPreferenceAvailable && hasViewableLastRecommendation,
    [isPillPreferenceAvailable, hasViewableLastRecommendation],
  );

  /**
   * Baris status hijau di bawah OK — hanya jika tidak ada banner (hindari duplikasi)
   * dan analisis masih sesuai konteks yang dikonfirmasi (bukan draft pill baru).
   */
  const showLastAnalysisStatusLine = useMemo(
    () =>
      hasViewableLastRecommendation
      && !pillRecommendLoading
      && !showRecommendationModal
      && !hasPendingPillChanges
      && !showLastRecommendationBanner,
    [
      hasViewableLastRecommendation,
      pillRecommendLoading,
      showRecommendationModal,
      hasPendingPillChanges,
      showLastRecommendationBanner,
    ],
  );

  const showRecommendationStatusSection = useMemo(
    () =>
      hasConfirmedRecommendation
      || hasViewableLastRecommendation
      || (!!pillRecommendError && !pillRecommendLoading),
    [
      hasConfirmedRecommendation,
      hasViewableLastRecommendation,
      pillRecommendError,
      pillRecommendLoading,
    ],
  );

  const openSavedRecommendationModal = () => {
    if (!hasViewableLastRecommendation) return;
    setShowRecommendationModal(true);
  };

  const requestPillRecommendations = async (pillValues, attributeValues = [], queryText = '') => {
    if (!isPillPreferenceAvailable) return;
    const trimmedQueryText = String(queryText || '').trim();
    const hasPills = Array.isArray(pillValues) && pillValues.length > 0;
    const hasQueryText = trimmedQueryText.length > 0;
    if (!hasPills && !hasQueryText) return;
    const token = authService.getToken();
    if (!token) {
      setPillRecommendError('Silakan login untuk mendapatkan rekomendasi konteks.');
      setRecommendationNotification({
        type: 'error',
        message: 'Silakan login untuk mendapatkan rekomendasi konteks.',
      });
      return;
    }
    setConfirmedPills(hasPills ? [...pillValues] : []);
    setConfirmedAttributes(hasPills ? [...attributeValues] : []);
    setConfirmedSearchKeyword(hasQueryText ? trimmedQueryText : '');
    const runStartedAt = Date.now();
    setRecommendationRunStartedAt(runStartedAt);
    setRecommendationTotalSeconds(null);
    setPillRecommendLoading(true);
    setPillRecommendProgress(null);
    setPillRecommendError('');
    setLlmRecommendations([]);
    setLlmOtherOptions([]);
    setShowRecommendationModal(false);
    try {
      const { statusCode, body: data } = await streamRecommendations({
        apiBase: API_BASE,
        token,
        preferences: hasPills ? pillValues : [],
        attributes: hasPills ? attributeValues : [],
        queryText: hasQueryText ? trimmedQueryText : '',
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
        setLlmOtherOptions(Array.isArray(data.other_options) ? data.other_options : []);
        setRecommendationResponseNotice(
          data.recommendations.length > 0 && data?.message
            ? String(data.message)
            : '',
        );
        if (data.recommendations.length === 0) {
          setRecommendationResponseNotice('');
          const emptyMessage = data?.message
            || 'Maaf, saat ini belum ada coffee shop yang cocok dengan konteks ini. Coba konteks lain.';
          setPillRecommendError(emptyMessage);
          setRecommendationNotification({
            type: 'error',
            message: emptyMessage,
          });
        } else if (user?.id) {
          const totalSec = Math.max(0, Math.round((Date.now() - runStartedAt) / 1000));
          saveLastRecommendationSession({
            userId: user.id,
            recommendations: data.recommendations,
            otherOptions: Array.isArray(data.other_options) ? data.other_options : [],
            confirmedPills: hasPills ? [...pillValues] : [],
            confirmedAttributes: hasPills ? [...attributeValues] : [],
            confirmedSearchKeyword: hasQueryText ? trimmedQueryText : '',
            totalDurationSeconds: totalSec,
          });
        }
        setRecommendationTotalSeconds(
          Math.max(0, Math.round((Date.now() - runStartedAt) / 1000)),
        );
        setShowRecommendationModal(true);
      } else {
        setPillRecommendError(data?.message || 'Rekomendasi AI belum bisa ditampilkan.');
        setLlmRecommendations([]);
        setLlmOtherOptions([]);
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
      setLlmOtherOptions([]);
      setShowRecommendationModal(false);
      setRecommendationNotification({
        type: 'error',
        message: err.message || 'Gagal menghubungi layanan rekomendasi AI.',
      });
    } finally {
      setPillRecommendLoading(false);
      setPillRecommendProgress(null);
      setRecommendationRunStartedAt(null);
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

  const closeLocationChoiceModal = () => {
    if (locationChoiceSubmitting || pillRecommendLoading) return;
    setShowLocationChoiceModal(false);
    setLocationError(null);
  };

  const hasRecommendableInput = selectedPills.length > 0 || searchKeyword.trim().length > 0;

  const handleConfirmPills = () => {
    if (!isPillPreferenceAvailable || !hasRecommendableInput) return;
    setLocationError(null);
    setShowLocationChoiceModal(true);
  };

  const handleRecommendWithLocation = async () => {
    if (!isPillPreferenceAvailable || !hasRecommendableInput) return;
    setLocationChoiceSubmitting(true);
    setLocationError(null);
    try {
      if (!userLocation) {
        await getCurrentLocationAsync();
      }
      setShowLocationChoiceModal(false);
      await requestPillRecommendations(selectedPills, selectedAttributes, searchKeyword);
    } catch (err) {
      setLocationError(err?.message || 'Tidak dapat mengambil lokasi.');
    } finally {
      setLocationChoiceSubmitting(false);
    }
  };

  const handleRecommendWithoutLocation = async () => {
    if (!isPillPreferenceAvailable || !hasRecommendableInput) return;
    setLocationChoiceSubmitting(true);
    setShowLocationChoiceModal(false);
    try {
      await requestPillRecommendations(selectedPills, selectedAttributes, searchKeyword);
    } finally {
      setLocationChoiceSubmitting(false);
    }
  };

  // Katalog homepage tetap utuh; hasil AI ditampilkan lewat overlay terpisah
  const filteredShops = getFilteredShopsByCategory(coffeeShops);

  const catalogShopsVisible = useMemo(
    () => filteredShops.slice(0, catalogVisibleCount),
    [filteredShops, catalogVisibleCount],
  );

  useEffect(() => {
    setCatalogVisibleCount(CATALOG_PAGE_SIZE);
  }, [coffeeShops.length]);

  // Statistik beranda: agregat SQL dari DB (catalog_stats), fallback dari katalog yang dimuat
  const stats = useMemo(() => {
    if (catalogStats) {
      const avg = Number(catalogStats.avg_rating);
      return {
        total: Number(catalogStats.total_shops) || 0,
        avgRating: Number.isFinite(avg) ? avg.toFixed(1) : '0',
        topRated: Number(catalogStats.top_rated) || 0,
        totalReviews: Number(catalogStats.total_cofind_reviews) || 0,
      };
    }
    const list = coffeeShops;
    const rated = list.filter((shop) => getGoogleRating(shop) > 0);
    const total = list.length;
    const sumRating = rated.reduce((sum, shop) => sum + getGoogleRating(shop), 0);
    const avgRating = rated.length > 0 ? (sumRating / rated.length).toFixed(1) : '0';
    const topRated = list.filter((shop) => {
      const r = getGoogleRating(shop);
      return r >= 4.5 && r <= 5;
    }).length;
    return { total, avgRating, topRated, totalReviews: 0 };
  }, [catalogStats, coffeeShops]);

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
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_300px] gap-6 lg:gap-8 items-start">
        <div className="min-w-0"> 
        {/* Statistics Cards - sesuai data yang tampil di aplikasi (filteredShops) */}
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
              <div className="text-xs mt-1 opacity-75">Google · tersimpan di DB</div>
            </div>

            <div className="bg-gradient-to-br from-green-500 to-emerald-600 rounded-xl p-4 sm:p-5 text-white shadow-lg hover:shadow-xl transition-shadow">
              <div className="text-2xl sm:text-3xl font-bold mb-1">{stats.topRated}</div>
              <div className="text-xs sm:text-sm opacity-90">Top Rated</div>
              <div className="text-xs mt-1 opacity-75">rating ≥ 4.5</div>
            </div>

            <div className="bg-gradient-to-br from-purple-500 to-pink-600 rounded-xl p-4 sm:p-5 text-white shadow-lg hover:shadow-xl transition-shadow">
              <div className="text-2xl sm:text-3xl font-bold mb-1">{stats.totalReviews.toLocaleString('id-ID')}</div>
              <div className="text-xs sm:text-sm opacity-90">Ulasan Cofind</div>
              <div className="text-xs mt-1 opacity-75">dari pengguna · database</div>
            </div>
          </div>
        )}

        {/* Konteks aktivitas (pill) + kata kunci — rekomendasi butuh login */}
        {!error && !isLoading && coffeeShops.length > 0 && (
          <div className="mb-6 sm:mb-8">
            <div className="mb-3">
              <h3 className="text-sm sm:text-base font-semibold text-gray-700 dark:text-gray-300 mb-2">
                Sesuaikan preferensi anda:
              </h3>
              {showLastRecommendationBanner && (
                <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between rounded-2xl border border-indigo-200/80 bg-gradient-to-r from-indigo-50 to-violet-50 px-4 py-3 dark:border-indigo-800/50 dark:from-indigo-950/40 dark:to-violet-950/30">
                  <p className="text-xs sm:text-sm text-indigo-950 dark:text-indigo-100">
                    {hasPendingPillChanges ? (
                      <>
                        Konteks di bawah berbeda dari analisis terakhir — hasil{' '}
                        {llmRecommendations.length} rekomendasi sebelumnya masih bisa dibuka
                        tanpa analisis ulang.
                      </>
                    ) : (
                      <>
                        Analisis terakhir: {llmRecommendations.length} rekomendasi dengan bukti
                        ulasan relevan untuk konteks yang Anda konfirmasi.
                      </>
                    )}
                  </p>
                  <button
                    type="button"
                    onClick={openSavedRecommendationModal}
                    disabled={pillRecommendLoading}
                    className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-full bg-indigo-600 px-4 py-2 text-xs sm:text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60 transition-colors"
                    title="Buka modal rekomendasi yang pernah Anda buat"
                  >
                    <span aria-hidden>✨</span>
                    Lihat rekomendasi terakhir
                  </button>
                </div>
              )}
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                Pilih satu pill atau isi kata kunci. Pilih pill yang sesuai dengan preferensi coffee shop yang ingin anda kunjungi.
              </p>
            </div>
            <div className="flex flex-wrap gap-2 sm:gap-3 items-center">
              {recommendationFields.map((field) => {
                const isSelected = selectedPills.includes(field.value);
                const theme = CONTEXT_PILL_THEMES[field.value] || CONTEXT_PILL_THEME_DEFAULT;
                const isFreeTextActive = searchKeyword.trim().length > 0;
                const pillDisabled = authLoading || pillRecommendLoading || isFreeTextActive;
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
            {user && selectedPills.length > 0 && (() => {
              const selectedActivity = CONTEXT_PILL_OPTIONS.find(
                (option) => selectedPills.includes(option.value),
              );
              if (!selectedActivity?.desc) return null;
              return (
                <p className="mt-2 text-xs sm:text-sm text-gray-600 dark:text-gray-300">
                  💡 <span className="font-semibold">{selectedActivity.label}:</span>{' '}
                  {selectedActivity.desc}
                </p>
              );
            })()}
            {isPillPreferenceAvailable && selectedPills.length > 0 && (
              <FacilityAttributePicker
              selected={selectedAttributes}
              onChange={setSelectedAttributes}
              disabled={authLoading || pillRecommendLoading}
            />
            )}

            <div className="mt-3">
              <label
                htmlFor="free-text-keyword-input"
                className="block text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5"
              >
                Tidak ada pill yang cocok? Isi kata kunci:
              </label>
              <div className="flex items-center gap-2 max-w-sm">
                <input
                  id="free-text-keyword-input"
                  type="text"
                  value={searchKeyword}
                  readOnly={!user}
                  onChange={(e) => handleSearchKeywordChange(e.target.value)}
                  onFocus={(e) => {
                    if (!user && !authLoading) {
                      e.target.blur();
                      openLoginModalForFreeText();
                    }
                  }}
                  onClick={() => {
                    if (!user && !authLoading) {
                      openLoginModalForFreeText();
                    }
                  }}
                  disabled={
                    authLoading
                    || pillRecommendLoading
                    || (Boolean(user) && selectedPills.length > 0)
                  }
                  maxLength={MAX_SEARCH_KEYWORD_CHARS}
                  placeholder={
                    !user && !authLoading
                      ? 'Login untuk mencari dengan kata kunci…'
                      : 'mis. wfc ruangan nyaman'
                  }
                  title={
                    !user && !authLoading
                      ? 'Login untuk menggunakan pencarian kata kunci'
                      : undefined
                  }
                  className={`w-full rounded-full border border-gray-300 bg-white px-4 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 ${!user && !authLoading ? 'cursor-pointer' : ''}`}
                />
                <span className="shrink-0 text-xs text-gray-400 tabular-nums">
                  {searchKeyword.length}/{MAX_SEARCH_KEYWORD_CHARS}
                </span>
              </div>
              <p className="mt-1.5 text-xs text-gray-500 dark:text-gray-400">
                {!user && !authLoading
                  ? 'Ketuk kolom di atas untuk masuk — setelah login Anda bisa mengetik kata kunci (maks. 100 karakter).'
                  : searchKeyword.trim()
                    ? 'Mode kata kunci aktif — pill preferensi dinonaktifkan. Hapus teks untuk kembali pilih pill.'
                    : 'Huruf, angka, spasi, dan koma. Contoh: wifi kencang, tenang buat kerja'}
              </p>
            </div>

            {isPillPreferenceAvailable && hasRecommendableInput && (
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={handleConfirmPills}
                  disabled={pillRecommendLoading || locationChoiceSubmitting}
                  className="px-4 py-2 rounded-full text-sm font-medium bg-indigo-600 text-white shadow-md hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed transition-all duration-200"
                  title="Konfirmasi konteks dan lihat rekomendasi"
                >
                  {pillRecommendLoading ? 'Menganalisis...' : 'OK'}
                </button>
                {userLocation ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 dark:border-emerald-800/60 dark:bg-emerald-950/30 dark:text-emerald-300">
                    <span aria-hidden>📍</span>
                    Lokasi aktif untuk jarak rekomendasi
                  </span>
                ) : null}
              </div>
            )}

            {showRecommendationStatusSection && (
              <div className="mt-3 space-y-2">
                {!!pillRecommendError && !pillRecommendLoading && (
                  <p className="text-sm text-red-600 dark:text-red-300">
                    {pillRecommendError}
                  </p>
                )}
                {!pillRecommendLoading
                  && !showRecommendationModal
                  && showLastAnalysisStatusLine && (
                  <p className="text-sm text-emerald-700 dark:text-emerald-300">
                    {`Analisis terakhir: ${llmRecommendations.length} rekomendasi dengan bukti ulasan relevan.`}
                  </p>
                )}
                {!pillRecommendLoading
                  && !showRecommendationModal
                  && hasConfirmedRecommendation
                  && !hasViewableLastRecommendation
                  && !pillRecommendError && (
                  <p className="text-sm text-gray-600 dark:text-gray-300">
                    Belum ada hasil rekomendasi untuk konteks ini. Tekan OK untuk memulai analisis.
                  </p>
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
            
            <div className="relative min-w-0">
              <HorizontalCatalogScroller>
                {featuredShops.map((shop, index) => (
                  <div
                    key={shop.place_id}
                    className={`${SHOP_CAROUSEL_ITEM_CLASS} hover:shadow-2xl transition duration-300 group`}
                  >
                    <div className="absolute top-2 left-2 z-20 bg-gradient-to-r from-yellow-400 to-orange-500 text-white w-10 h-10 rounded-full flex items-center justify-center font-bold text-lg shadow-lg">
                      {index + 1}
                    </div>
                    <div className="relative w-full h-full">
                      <CoffeeShopCard shop={shop} />
                    </div>
                  </div>
                ))}
              </HorizontalCatalogScroller>
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
              Coffee shop dengan rating tertinggi
            </p>
            
            <div className="relative min-w-0">
              <HorizontalCatalogScroller>
                {topRatedShops.map((shop) => (
                  <div
                    key={shop.place_id}
                    className={`${SHOP_CAROUSEL_ITEM_CLASS} hover:shadow-2xl transition duration-300 group`}
                  >
                    <div className="relative">
                      <CoffeeShopCard shop={shop} />
                    </div>
                  </div>
                ))}
              </HorizontalCatalogScroller>
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
            
            <div className="relative min-w-0">
              <HorizontalCatalogScroller>
                {newestShops.map((shop) => (
                  <div
                    key={shop.place_id}
                    className={`${SHOP_CAROUSEL_ITEM_CLASS} hover:shadow-2xl transition duration-300 group`}
                  >
                    <div className="relative">
                      <CoffeeShopCard shop={shop} />
                    </div>
                  </div>
                ))}
              </HorizontalCatalogScroller>
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
            
            <div className={SHOP_CATALOG_GRID_CLASS}>
              {recentlyViewedShops.map((shop) => (
                <div key={shop.place_id} className="block hover:shadow-2xl transition duration-300">
                  <CoffeeShopCard shop={shop} />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Peta Leaflet + lokasi — di atas All Coffee Shops */}
        {!error && !isLoading && coffeeShops.length > 0 && (
          <CoffeeShopMap
            coffeeShops={coffeeShops}
            userLocation={userLocation}
            radiusMeters={radiusMeters}
            setRadiusMeters={setRadiusMeters}
            locationLoading={locationLoading}
            locationError={locationError}
            getCurrentLocation={getCurrentLocation}
            shopsInRadius={shopsInRadius}
          />
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
          <>
            <div className={SHOP_CATALOG_GRID_CLASS}>
              {catalogShopsVisible.map((shop) => (
                <div
                  key={shop.place_id}
                  className="block hover:shadow-2xl transition duration-300"
                >
                  <CoffeeShopCard shop={shop} />
                </div>
              ))}
            </div>
            {catalogVisibleCount < filteredShops.length && (
              <div className="mt-8 flex flex-col items-center gap-2">
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Menampilkan {catalogShopsVisible.length} dari {filteredShops.length} coffee shop
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setCatalogVisibleCount((prev) =>
                      Math.min(prev + CATALOG_PAGE_SIZE, filteredShops.length),
                    );
                  }}
                  className="px-6 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm shadow-md transition-colors"
                >
                  See more
                </button>
              </div>
            )}
          </>
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
        
        </div>
        <LatestReviewsAside className="lg:sticky lg:top-24" />
        </div>
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
              {pillLoginModalContext === 'free_text' ? (
                <>
                  Masuk ke akun Cofind untuk menggunakan pencarian kata kunci dan mendapatkan rekomendasi
                  coffee shop dari analisis ulasan (BM25 + semantic search).
                </>
              ) : (
                <>
                  Login untuk menggunakan fitur analisis LLM — dapatkan rekomendasi coffee shop berdasarkan
                  konteks aktivitas dan ulasan pengunjung.
                </>
              )}
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

      {showLocationChoiceModal && (
        <div
          className="fixed inset-0 z-[105] flex items-center justify-center p-4 sm:p-6"
          role="dialog"
          aria-modal="true"
          aria-labelledby="location-choice-modal-title"
        >
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            aria-hidden="true"
            onClick={closeLocationChoiceModal}
          />
          <div className="relative z-10 w-full max-w-md rounded-2xl border border-gray-200 bg-white p-6 shadow-2xl dark:border-gray-700 dark:bg-gray-900">
            <h3
              id="location-choice-modal-title"
              className="text-lg font-bold text-gray-900 dark:text-white"
            >
              Gunakan lokasi untuk rekomendasi?
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-gray-600 dark:text-gray-300">
              Lokasi membantu menampilkan perkiraan jarak ke coffee shop yang direkomendasikan
              dan menyaring peta di beranda. Anda tetap bisa melihat rekomendasi tanpa membagikan lokasi.
            </p>
            {!!locationError && (
              <div
                role="alert"
                className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-200"
              >
                {locationError}
              </div>
            )}
            <div className="mt-6 space-y-2.5">
              <button
                type="button"
                onClick={handleRecommendWithLocation}
                disabled={locationChoiceSubmitting || locationLoading || pillRecommendLoading}
                className="flex w-full items-center gap-3 rounded-xl border border-indigo-200 bg-indigo-600 px-4 py-3.5 text-left text-white shadow-md transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60 dark:border-indigo-500/40 dark:shadow-indigo-950/30 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-gray-900"
              >
                <span
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white/15 text-lg"
                  aria-hidden
                >
                  📍
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold leading-snug">
                    {locationLoading || locationChoiceSubmitting
                      ? 'Mendeteksi lokasi...'
                      : 'Gunakan lokasi saat ini'}
                  </span>
                  <span className="mt-0.5 block text-xs font-normal text-indigo-100/90">
                    Jarak ke coffee shop & peta di beranda lebih relevan
                  </span>
                </span>
              </button>
              <button
                type="button"
                onClick={handleRecommendWithoutLocation}
                disabled={locationChoiceSubmitting || locationLoading || pillRecommendLoading}
                className="flex w-full items-center gap-3 rounded-xl border border-gray-200 bg-gray-50 px-4 py-3.5 text-left transition hover:border-gray-300 hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-600 dark:bg-gray-800/80 dark:hover:border-gray-500 dark:hover:bg-gray-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-400 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-gray-900"
              >
                <span
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white text-lg shadow-sm dark:bg-gray-700"
                  aria-hidden
                >
                  ☕
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold text-gray-900 dark:text-gray-100">
                    Lanjutkan tanpa lokasi
                  </span>
                  <span className="mt-0.5 block text-xs text-gray-600 dark:text-gray-400">
                    Rekomendasi tetap ditampilkan tanpa jarak
                  </span>
                </span>
              </button>
              <div className="flex justify-center pt-1">
                <button
                  type="button"
                  onClick={closeLocationChoiceModal}
                  disabled={locationChoiceSubmitting || locationLoading}
                  className="rounded-full px-4 py-2 text-sm font-medium text-gray-500 hover:text-gray-800 hover:bg-gray-100 disabled:opacity-60 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:bg-gray-800"
                >
                  Batal
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <RecommendationProgressOverlay
        open={pillRecommendLoading}
        progress={pillRecommendProgress}
        startedAtMs={recommendationRunStartedAt}
      />

      <RecommendationModal
        isOpen={showRecommendationModal}
        onClose={() => setShowRecommendationModal(false)}
        recommendations={llmRecommendations}
        otherOptions={llmOtherOptions}
        shopsByKey={shopsByKey}
        confirmedPills={confirmedPills}
        confirmedAttributes={confirmedAttributes}
        confirmedSearchKeyword={confirmedSearchKeyword}
        userLocation={userLocation}
        totalDurationSeconds={recommendationTotalSeconds}
        responseNotice={recommendationResponseNotice}
      />
    </div>
  );
}

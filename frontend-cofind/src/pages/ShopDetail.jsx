import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useParams, Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/authContext';
// Supabase removed - use local backend only
import OptimizedImage from '../components/OptimizedImage';
import FacilitiesTab from '../components/FacilitiesTab';
import ReviewList from '../components/ReviewList';
import CoffeeShopCard from '../components/CoffeeShopCard';
import ShopVotesSummary from '../components/ShopVotesSummary';
import ShopVoteModal from '../components/ShopVoteModal';
import ShopOverallExperience from '../components/ShopOverallExperience';
import ShopProsCons from '../components/ShopProsCons';
import facilitiesData from '../data/facilities.json';
import { addToRecentlyViewed } from '../utils/recentlyViewed';
import { getCoffeeShopImage, ensureCoffeeShopImageMap } from '../utils/coffeeShopImages';

// API Configuration (samakan sumber data dengan homepage)
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';
// Using Supabase only - photos stored in Supabase Storage
const MIN_REVIEWS = 15; // Maksimal jumlah reviews yang ditampilkan

function ShopDetail() {
  const { id: routeParam } = useParams(); // place_id dari URL
  const placeIdFromRoute = useMemo(
    () => (routeParam ? decodeURIComponent(String(routeParam)).trim() : ''),
    [routeParam],
  );
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth();
  const [shop, setShop] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isFavorite, setIsFavorite] = useState(false);
  const [isWantToVisit, setIsWantToVisit] = useState(false);
  const [notification, setNotification] = useState(null);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [pendingAction, setPendingAction] = useState(null); // 'favorite' or 'wantToVisit'
  const [newReview, setNewReview] = useState(null); // For triggering ReviewList update
  const [mapError, setMapError] = useState(false); // Track map load errors
  const [voteSummary, setVoteSummary] = useState(null);
  const [myVote, setMyVote] = useState(null);
  const [isVoteModalOpen, setIsVoteModalOpen] = useState(false);
  const [isSubmittingVote, setIsSubmittingVote] = useState(false);
  const reviewFormRef = useRef(null); // Ref untuk scroll ke review form
  const locationSectionRef = useRef(null); // Ref untuk scroll ke section lokasi

  const placeIdForApi = useMemo(() => {
    if (shop?.place_id != null && String(shop.place_id).trim() !== '') {
      return String(shop.place_id).trim();
    }
    return placeIdFromRoute;
  }, [shop?.place_id, placeIdFromRoute]);

  const goldOverview = useMemo(() => {
    const pid = placeIdForApi || shop?.place_id;
    if (!pid || !facilitiesData?.facilities_by_place_id?.[pid]) return '';

    const facs = facilitiesData.facilities_by_place_id[pid].facilities;
    const highlights = facs.highlights || {};
    const popular = facs.popular_for || {};
    const atmosphere = facs.atmosphere || [];
    const crowd = facs.crowd || [];

    const translationMap = {
      'good_coffee': 'kopi yang enak',
      'good_desserts': 'pencuci mulut yang lezat',
      'good_tea_selection': 'pilihan teh yang beragam',
      'sports': 'cocok untuk menyaksikan pertandingan olahraga',
      'live_music': 'pertunjukan musik',
      'live_performances': 'pertunjukan langsung',
      'breakfast': 'sarapan',
      'lunch': 'makan siang',
      'dinner': 'makan malam',
      'solo_dining': 'bersantai sendiri (me time)',
      'good_for_working_on_laptop': 'bekerja menggunakan laptop (wfc)',
      'berkelompok': 'keluarga, komunitas',
      'mahasiswa': 'mahasiswa',
      'ramah_keluarga': 'keluarga',
      'turis': 'turis'
    };

    const translate = (key) => translationMap[key] || key.replace(/_/g, ' ');

    const hList = Object.keys(highlights).filter(k => highlights[k]).map(translate);
    const pList = Object.keys(popular).filter(k => popular[k]).map(translate);
    const aList = atmosphere;
    const cList = crowd.map(translate);

    const hStr = hList.length > 0 ? hList.join(', ') : 'berbagai sajian';
    const pStr = pList.length > 0 ? pList.join(', ') : 'bersantai';
    const aStr = aList.length > 0 ? aList.join(', ') : 'nyaman';
    const cStr = cList.length > 0 ? cList.join(', ') : '';

    let summary = `${shop?.name || 'Tempat ini'} adalah coffee shop yang memiliki keunggulan pada ${hStr}. Tempat ini sangat populer untuk ${pStr} dengan suasana yang ${aStr}.`;
    if (cStr) {
      summary += ` Pengunjung tempat ini mayoritas seperti ${cStr}.`;
    }
    return summary;
  }, [placeIdForApi, shop?.place_id, shop?.name]);

  // Handle scroll to review form setelah login
  useEffect(() => {
    // Check if user just logged in and should scroll to review form
    const shouldScrollToReview = location.state?.scrollToReview || 
                                  new URLSearchParams(location.search).get('scrollToReview') === 'true';
    
    if (shouldScrollToReview && isAuthenticated && shop && !isLoading && reviewFormRef.current) {
      // Wait a bit for page to fully render, then scroll
      const scrollTimeout = setTimeout(() => {
        if (reviewFormRef.current) {
          // Calculate offset untuk navbar (jika ada)
          const navbarHeight = 60; // Approximate navbar height
          const elementPosition = reviewFormRef.current.getBoundingClientRect().top;
          const offsetPosition = elementPosition + window.pageYOffset - navbarHeight;
          
          window.scrollTo({
            top: offsetPosition,
            behavior: 'smooth'
          });
          
          console.log('[ShopDetail] Scrolled to review form after login');
          
          // Clear the state to prevent re-scrolling on refresh
          if (location.state?.scrollToReview) {
            window.history.replaceState({}, '', location.pathname);
          }
        }
      }, 800); // Increased timeout untuk memastikan semua content ter-render
      
      return () => clearTimeout(scrollTimeout);
    }
  }, [isAuthenticated, shop, isLoading, location]);

  // Title halaman: (nama coffee shop) - Cofind
  useEffect(() => {
    if (shop?.name) {
      document.title = `${shop.name} - Cofind`;
      return () => { document.title = 'Cofind'; };
    }
  }, [shop?.name]);

  useEffect(() => {
    const loadShop = async () => {
      try {
        setIsLoading(true);
        setError(null);
        if (!placeIdFromRoute) {
          throw new Error('place_id tidak valid.');
        }

        // ✅ PRIMARY: Fetch from local backend (same source as homepage)
        try {
          const detailUrl = `${API_BASE}/api/coffeeshops/place/${encodeURIComponent(placeIdFromRoute)}`;
          console.log('[ShopDetail] Fetching from backend:', detailUrl);

          const response = await fetch(detailUrl);

          if (!response.ok) {
            throw new Error(`API returned status ${response.status}`);
          }

          const payload = await response.json();

          if (payload?.status === 'success' && payload?.data) {
            const detail = payload.data;
            const normalized = {
              place_id: detail.place_id,
              name: detail.name,
              address: detail.address,
              rating: detail.rating,
              user_ratings_total: detail.user_ratings_total,
              total_reviews: detail.total_reviews ?? detail.user_ratings_total,
              price_level: detail.price_level || null,
              location: detail.location || null,
              photos: [],
              business_status: detail.business_status || null,
              map_embed_url: detail.map_embed_url || null,
              opening_hours_display: detail.opening_hours_display ?? '',
            };

            setShop(normalized);
            addToRecentlyViewed(normalized);
            setIsLoading(false);
            return;
          }
        } catch (apiErr) {
          console.error('[ShopDetail] Failed to load from backend:', apiErr?.message);
        }

        // If all methods fail
        throw new Error('Tidak dapat memuat detail coffee shop. Pastikan koneksi internet dan konfigurasi database sudah benar.');
      } catch (err) {
        console.error("Load Error:", err);
        setError(err.message || 'Gagal memuat detail toko');
        setShop(null);
        setIsLoading(false);
      }
    };

    loadShop();
  }, [placeIdFromRoute]);

  // Check if shop is favorited or in want-to-visit (local backend or localStorage)
  useEffect(() => {
    const checkFavoriteStatus = async () => {
      const pid = placeIdForApi;
      if (!pid) return;

      if (isAuthenticated && user?.id) {
        const uid = Number(user.id);
        try {
          const response = await fetch(
            `${API_BASE}/api/coffeeshops/${encodeURIComponent(pid)}/favorite-status?user_id=${uid}`,
          );
          if (response.ok) {
            const payload = await response.json();
            setIsFavorite(!!payload?.is_favorite);
          } else {
            setIsFavorite(false);
          }
        } catch (err) {
          console.error('[ShopDetail] Error checking favorite status:', err);
          setIsFavorite(false);
        }

        try {
          const response = await fetch(
            `${API_BASE}/api/coffeeshops/${encodeURIComponent(pid)}/want-to-visit-status?user_id=${uid}`,
          );
          if (response.ok) {
            const payload = await response.json();
            setIsWantToVisit(!!payload?.is_want_to_visit);
          } else {
            setIsWantToVisit(false);
          }
        } catch (err) {
          console.error('[ShopDetail] Error checking want-to-visit status:', err);
          setIsWantToVisit(false);
        }
        return;
      }

      // Guest mode: use localStorage
      const favorites = JSON.parse(localStorage.getItem('favoriteShops') || '[]');
      setIsFavorite(favorites.includes(pid));

      const wantToVisit = JSON.parse(localStorage.getItem('wantToVisitShops') || '[]');
      setIsWantToVisit(wantToVisit.includes(pid));
    };
    
    checkFavoriteStatus();
  }, [placeIdForApi, isAuthenticated, user?.id]);

  // Fetch vote summary (agregat semua user) untuk coffee shop ini
  const fetchVoteSummary = async (pid) => {
    if (!pid) return;
    try {
      const response = await fetch(`${API_BASE}/api/coffeeshops/${encodeURIComponent(pid)}/votes/summary`);
      if (response.ok) {
        const payload = await response.json();
        if (payload?.status === 'success') {
          setVoteSummary(payload);
        }
      }
    } catch (err) {
      console.error('[ShopDetail] Error fetching vote summary:', err);
    }
  };

  // Fetch vote milik user yang sedang login untuk coffee shop ini
  const fetchMyVote = async (pid) => {
    if (!pid || !isAuthenticated || !user?.id) {
      setMyVote(null);
      return;
    }
    try {
      const response = await fetch(
        `${API_BASE}/api/coffeeshops/${encodeURIComponent(pid)}/votes/me?user_id=${Number(user.id)}`,
      );
      if (response.ok) {
        const payload = await response.json();
        setMyVote(payload?.vote || null);
      }
    } catch (err) {
      console.error('[ShopDetail] Error fetching my vote:', err);
    }
  };

  useEffect(() => {
    if (!placeIdForApi) return;
    fetchVoteSummary(placeIdForApi);
    fetchMyVote(placeIdForApi);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [placeIdForApi, isAuthenticated, user?.id]);

  const openVoteModal = () => {
    if (!isAuthenticated || !user?.id) {
      setPendingAction('vote');
      setShowLoginModal(true);
      return;
    }
    setIsVoteModalOpen(true);
  };

  const handleSubmitVote = async (voteData) => {
    const pid = placeIdForApi;
    if (!pid || !user?.id) return;

    setIsSubmittingVote(true);
    try {
      const response = await fetch(`${API_BASE}/api/coffeeshops/${encodeURIComponent(pid)}/votes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: Number(user.id), ...voteData }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload?.status !== 'success') {
        setNotification({ type: 'error', message: payload?.message || 'Gagal menyimpan vote' });
        return;
      }
      setNotification({ type: 'added', message: 'Vote berhasil disimpan!' });
      setIsVoteModalOpen(false);
      await Promise.all([fetchVoteSummary(pid), fetchMyVote(pid)]);
    } catch (err) {
      console.error('[ShopDetail] Error submitting vote:', err);
      setNotification({ type: 'error', message: 'Terjadi kesalahan saat menyimpan vote' });
    } finally {
      setIsSubmittingVote(false);
    }
  };

  // Klik langsung pada opsi rating/status kunjungan di ShopVotesSummary:
  // submit vote saat itu juga tanpa membuka ShopVoteModal. Klik ulang pada
  // opsi yang sama akan membatalkan (unset) pilihan tersebut.
  const handleQuickVote = async (field, key) => {
    if (!isAuthenticated || !user?.id) {
      setPendingAction('vote');
      setShowLoginModal(true);
      return;
    }
    const pid = placeIdForApi;
    if (!pid || isSubmittingVote) return;

    const nextValue = myVote?.[field] === key ? null : key;
    const voteData = {
      presence: myVote?.presence ?? null,
      rating: myVote?.rating ?? null,
      best_for: myVote?.best_for || [],
      pelayanan: myVote?.pelayanan ?? null,
      kebersihan: myVote?.kebersihan ?? null,
      kenyamanan: myVote?.kenyamanan ?? null,
      harga: myVote?.harga ?? null,
      [field]: nextValue,
    };

    setIsSubmittingVote(true);
    try {
      const response = await fetch(`${API_BASE}/api/coffeeshops/${encodeURIComponent(pid)}/votes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: Number(user.id), ...voteData }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload?.status !== 'success') {
        setNotification({ type: 'error', message: payload?.message || 'Gagal menyimpan vote' });
        return;
      }
      setNotification({ type: 'added', message: 'Vote berhasil disimpan!' });
      await Promise.all([fetchVoteSummary(pid), fetchMyVote(pid)]);
    } catch (err) {
      console.error('[ShopDetail] Error submitting quick vote:', err);
      setNotification({ type: 'error', message: 'Terjadi kesalahan saat menyimpan vote' });
    } finally {
      setIsSubmittingVote(false);
    }
  };

  const toggleFavorite = async () => {
    // If guest, show login modal
    if (!isAuthenticated || !user?.id) {
      setPendingAction('favorite');
      setShowLoginModal(true);
      return;
    }

    const pid = placeIdForApi;
    if (!pid) {
      setNotification({ type: 'error', message: 'Data toko belum siap. Tunggu sebentar lalu coba lagi.' });
      return;
    }
    const uid = Number(user.id);

    try {
      if (isFavorite) {
        const response = await fetch(`${API_BASE}/api/favorites/${encodeURIComponent(pid)}`, {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: uid }),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          setNotification({
            type: 'error',
            message: payload.message || 'Gagal menghapus dari favorit',
          });
          return;
        }
        setNotification({ type: 'removed', message: 'Dihapus dari favorit' });
      } else {
        const response = await fetch(`${API_BASE}/api/favorites`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: uid, place_id: pid }),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          setNotification({
            type: 'error',
            message: payload.message || 'Gagal menambahkan ke favorit',
          });
          return;
        }
        setNotification({ type: 'added', message: 'Ditambahkan ke favorit!' });
      }

      setIsFavorite(!isFavorite);
    } catch (err) {
      console.error('[ShopDetail] Error toggling favorite:', err);
      setNotification({ type: 'error', message: 'Terjadi kesalahan saat mengubah favorit' });
    }
  };

  const toggleWantToVisit = async () => {
    // If guest, show login modal
    if (!isAuthenticated || !user?.id) {
      setPendingAction('wantToVisit');
      setShowLoginModal(true);
      return;
    }

    const pid = placeIdForApi;
    if (!pid) {
      setNotification({ type: 'error', message: 'Data toko belum siap. Tunggu sebentar lalu coba lagi.' });
      return;
    }
    const uid = Number(user.id);

    try {
      if (isWantToVisit) {
        const response = await fetch(`${API_BASE}/api/want-to-visit/${encodeURIComponent(pid)}`, {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: uid }),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          setNotification({
            type: 'error',
            message: payload.message || 'Gagal menghapus dari want to visit',
          });
          return;
        }
        setNotification({ type: 'removed', message: 'Dihapus dari want to visit' });
      } else {
        const response = await fetch(`${API_BASE}/api/want-to-visit`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: uid, place_id: pid }),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          setNotification({
            type: 'error',
            message: payload.message || 'Gagal menambahkan ke want to visit',
          });
          return;
        }
        setNotification({ type: 'added', message: 'Ditambahkan ke want to visit!' });
      }
      setIsWantToVisit(!isWantToVisit);
    } catch (err) {
      console.error('[ShopDetail] Error toggling want to visit:', err);
      setNotification({ type: 'error', message: 'Terjadi kesalahan saat mengubah want to visit' });
    }
  };

  const scrollToLocationSection = () => {
    if (!locationSectionRef.current) return;
    const navbarHeight = 70;
    const elementPosition = locationSectionRef.current.getBoundingClientRect().top;
    const offsetPosition = elementPosition + window.pageYOffset - navbarHeight;
    window.scrollTo({
      top: offsetPosition,
      behavior: 'smooth',
    });
  };

  // Auto-hide notification setelah 3 detik
  useEffect(() => {
    if (notification) {
      const timer = setTimeout(() => setNotification(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [notification]);

  if (isLoading) return (
    <div className="text-center mt-8 sm:mt-10 px-4">
      <p className="text-lg sm:text-xl text-indigo-600 dark:text-indigo-400">Memuat Detail Toko...</p>
    </div>
  );
  if (error) return (
    <div className="text-center mt-8 sm:mt-10 px-4">
      <p className="text-lg sm:text-xl text-red-600 dark:text-red-400">{error}</p>
    </div>
  );
  if (!shop) return (
    <div className="text-center mt-8 sm:mt-10 px-4">
      <p className="text-lg sm:text-xl text-red-600 dark:text-red-400">Data Toko tidak tersedia.</p>
    </div>
  );

  return (
    <div className="w-full py-4 sm:py-6 md:py-8 px-4 sm:px-6 relative">
      {/* Notification Toast */}
      {notification && (
        <div
          data-testid="shop-notification"
          className={`fixed top-8 left-1/2 transform -translate-x-1/2 px-6 py-3 rounded-lg shadow-lg text-white font-medium z-50 transition-all duration-300 animate-fade-in ${
          notification.type === 'added' 
            ? 'bg-green-500 dark:bg-green-600' 
            : 'bg-orange-500 dark:bg-orange-600'
        }`}>
          {notification.message}
        </div>
      )}
      
      <div className="flex items-center justify-between mb-4">
        <Link 
          to="/" 
          className="inline-flex items-center gap-2 px-4 py-2 bg-gray-100 dark:bg-zinc-700 hover:bg-gray-200 dark:hover:bg-zinc-600 text-gray-700 dark:text-gray-200 font-medium rounded-lg shadow-sm hover:shadow-md transition-all duration-200"
        >
          <svg className="w-5 h-5" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
            <path d="M10 19l-7-7m0 0l7-7m-7 7h18"></path>
          </svg>
          <span>Kembali ke Daftar</span>
        </Link>
      </div>
      <div className="bg-white dark:bg-zinc-800 p-4 sm:p-6 md:p-8 rounded-xl shadow-2xl border border-gray-200 dark:border-zinc-700">
        {/* Foto Coffee Shop - dari Supabase Storage dengan fallback ke local assets */}
        <div className="mb-6 rounded-xl overflow-hidden shadow-lg">
          <div className="w-full h-56 sm:h-64 md:h-80">
            <OptimizedImage
              src={getCoffeeShopImage(shop.place_id || shop.name)}
              alt={shop.name}
              className="w-full h-full object-cover object-center"
              fallbackColor={(() => {
                const seed = (shop.name || 'Coffee Shop').length % 10;
                const colors = ['#4F46E5', '#7C3AED', '#EC4899', '#F59E0B', '#10B981', '#3B82F6', '#8B5CF6', '#F97316', '#06B6D4', '#6366F1'];
                return colors[seed % colors.length];
              })()}
              shopName={shop.name}
            />
          </div>
        </div>

        {/* Nama Coffee Shop */}
        <div className="mb-6">
          <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold text-gray-900 dark:text-white mb-3 break-words">
            {shop.name}
          </h1>
          <div className="flex items-center gap-2">
            <div className="flex items-center bg-amber-50 dark:bg-amber-900/20 px-3 py-1.5 rounded-lg">
              <span className="text-amber-500 text-lg">⭐</span>
              <span className="ml-1.5 text-lg font-semibold text-gray-900 dark:text-white">
                {shop.rating || 'N/A'}
              </span>
            </div>
          </div>
        </div>

        {/* Overview gold summary non-LLM untuk pembanding evaluasi summary */}
        {goldOverview && (
          <section className="mb-6 rounded-xl border border-amber-200 bg-amber-50/70 p-4 sm:p-5 dark:border-amber-900/40 dark:bg-amber-950/20">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-amber-500 text-white shadow-sm" aria-hidden>
                <svg className="h-5 w-5" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
                  <path d="M4 19.5A2.5 2.5 0 016.5 17H20"></path>
                  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"></path>
                </svg>
              </span>
              <div className="min-w-0">
                <h2 className="text-lg sm:text-xl font-bold text-gray-900 dark:text-white">
                  Overview
                </h2>
                <p className="mt-2 text-sm sm:text-base leading-7 text-gray-700 dark:text-gray-300">
                  {goldOverview}
                </p>
              </div>
            </div>
          </section>
        )}

        {/* Informasi Utama */}
        <div className="space-y-4">
          {/* Alamat */}
          <div className="flex items-start gap-3 p-4 bg-gray-50 dark:bg-zinc-700/50 rounded-lg">
            <svg className="w-5 h-5 text-gray-600 dark:text-gray-400 mt-0.5 flex-shrink-0" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
              <path d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
            </svg>
            <p className="text-sm sm:text-base text-gray-700 dark:text-gray-300 break-words flex-1">
              {shop.address}
            </p>
          </div>

          {/* Jam Operasional */}
          <div className="flex items-start gap-3 p-4 bg-amber-50/50 dark:bg-amber-900/10 rounded-lg border border-amber-100 dark:border-amber-900/30">
            <span className="text-lg flex-shrink-0" aria-hidden>🕐</span>
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Jam Operasional</p>
              <p className="text-sm sm:text-base text-gray-700 dark:text-gray-300 whitespace-pre-line">
                {shop.opening_hours_display || 'Jam operasional belum diisi'}
              </p>
            </div>
          </div>

          {/* Kontak & Website */}
          <div className="flex flex-col sm:flex-row gap-3">
            {shop.phone && (
              <div className="flex items-center gap-3 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg flex-1">
                <svg className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
                  <path d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path>
                </svg>
                <a href={`tel:${shop.phone}`} className="text-sm sm:text-base text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors break-all">
                  {shop.phone}
                </a>
              </div>
            )}
            
            {shop.website && (
              <a 
                href={shop.website} 
                target="_blank" 
                rel="noopener noreferrer" 
                className="flex items-center justify-center gap-2 px-6 py-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-medium rounded-lg shadow-md hover:shadow-lg transition-all duration-200 flex-1"
              >
                <svg className="w-5 h-5" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
                  <path d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"></path>
                </svg>
                <span>Kunjungi Website</span>
                <svg className="w-4 h-4" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
                  <path d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
                </svg>
              </a>
            )}
          </div>
        </div>
      </div>

      {/* Votes Section */}
      {shop?.place_id && (
        <div className="mt-6 sm:mt-8">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-rose-400 to-pink-500 text-white shadow-md text-lg">
                  🗳️
                </span>
                Votes Pengunjung
              </h2>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-2 max-w-2xl">
                Klik langsung salah satu opsi rating atau status kunjungan untuk vote instan. Gunakan tombol di kanan untuk mengatur detail vote lainnya (best for & slider).
              </p>
            </div>
            <button
              type="button"
              onClick={openVoteModal}
              className="flex-shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-sm font-semibold shadow-sm transition-colors cursor-pointer"
            >
              <span>⭐</span>
              <span>{myVote ? 'Edit My Vote' : 'My Votes'}</span>
            </button>
          </div>
          <ShopVotesSummary
            summary={voteSummary}
            myVote={myVote}
            onSelectRating={(key) => handleQuickVote('rating', key)}
            onSelectPresence={(key) => handleQuickVote('presence', key)}
            isSubmitting={isSubmittingVote}
          />
        </div>
      )}

      {/* Ringkasan facilities (popular_for, highlights, atmosphere, amenities) */}
      {shop?.place_id && facilitiesData?.facilities_by_place_id?.[shop.place_id] && (
        <div className="mt-6 sm:mt-8">
          <div className="mb-4">
            <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 text-white shadow-md">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20" aria-hidden>
                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                </svg>
              </span>
              Fasilitas & Suasana
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-2 max-w-2xl">
              Populer, keunggulan, dan suasana yang dirasakan pengunjung.
            </p>
          </div>
          <FacilitiesTab facilities={facilitiesData.facilities_by_place_id[shop.place_id].facilities} />
        </div>
      )}

      {/* Overall Experience (rata-rata pelayanan, kebersihan, kenyamanan, harga) */}
      <ShopOverallExperience
        summary={voteSummary}
        myVote={myVote}
        isAuthenticated={isAuthenticated}
        onSubmit={handleSubmitVote}
        onRequireLogin={() => {
          setPendingAction('vote');
          setShowLoginModal(true);
        }}
      />

      {/* Pros & Cons (What People Say) */}
      {shop?.place_id && (
        <ShopProsCons
          placeId={placeIdForApi}
          user={user}
          isAuthenticated={isAuthenticated}
          onRequireLogin={() => {
            setPendingAction('vote');
            setShowLoginModal(true);
          }}
        />
      )}

      {/* Static Map */}
      <div className="mt-6 sm:mt-8" ref={locationSectionRef}>
        <div className="bg-white dark:bg-zinc-800 p-4 sm:p-6 rounded-xl shadow border border-gray-200 dark:border-zinc-700">
          <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white mb-4">
            📍 Lokasi
          </h2>
          
          {/* Coba tampilkan embed maps, jika error tampilkan fallback */}
          {shop.map_embed_url && !mapError ? (
            <div className="rounded-lg overflow-hidden">
              <iframe
                src={shop.map_embed_url}
                width="100%"
                height="400"
                style={{ border: 0, borderRadius: '0.5rem' }}
                allowFullScreen=""
                loading="lazy"
                referrerPolicy="no-referrer-when-downgrade"
                onError={() => {
                  console.warn('[ShopDetail] Map embed failed, showing fallback');
                  setMapError(true);
                }}
              ></iframe>
            </div>
          ) : shop.location ? (
            <div className="rounded-lg overflow-hidden">
              {(() => {
                const lat = shop.location.lat;
                const lng = shop.location.lng;
                const googleMapsUrl = `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`;
                
                return (
                  <div className="w-full h-64 sm:h-80 bg-gradient-to-br from-gray-100 to-gray-200 dark:from-zinc-700 dark:to-zinc-800 rounded-lg flex items-center justify-center flex-col gap-3">
                    <div className="text-center">
                      <p className="text-4xl mb-3">📍</p>
                      <p className="text-gray-600 dark:text-gray-400 text-sm mb-1">Koordinat Lokasi:</p>
                      <p className="text-lg font-mono font-semibold text-gray-900 dark:text-white">
                        {lat.toFixed(6)}, {lng.toFixed(6)}
                      </p>
                      <a
                        href={googleMapsUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-2 mt-4 px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 transition shadow-md"
                      >
                        <svg className="w-4 h-4" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
                          <path d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
                          <path d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
                        </svg>
                        Buka di Google Maps
                      </a>
                    </div>
                  </div>
                );
              })()}
            </div>
          ) : (
            <div className="w-full h-64 sm:h-80 bg-gray-100 dark:bg-zinc-700 rounded-lg flex items-center justify-center">
              <p className="text-gray-500 dark:text-gray-400">Lokasi tidak tersedia</p>
            </div>
          )}
        </div>
      </div>


      {/* Reviews Section */}
      <div className="mt-6 sm:mt-8 space-y-6" ref={reviewFormRef}>
        {shop?.place_id && (
          <div>
            <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white mb-4">
              Review Pengunjung
            </h2>
            <ReviewList
              placeId={shop.place_id}
              shopName={shop.name}
              newReview={newReview}
              onReviewSubmitted={(review) => {
                console.log('[ShopDetail] Review submitted:', review);
                setNewReview(review);
              }}
            />
          </div>
        )}
      </div>

      {/* Floating Action Buttons - pojok kanan bawah (untuk semua user, termasuk guest) */}
      <div className="fixed bottom-8 right-8 flex flex-col gap-4 z-40">
        {/* Go To Location Button */}
        <button
          onClick={scrollToLocationSection}
          className="relative transition-all duration-200 hover:scale-110 focus:outline-none bg-transparent border-0 p-0 group"
          aria-label="Menuju lokasi"
        >
          <span className="pointer-events-none absolute right-full mr-3 top-1/2 -translate-y-1/2 whitespace-nowrap rounded-full bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white shadow-lg opacity-0 -translate-x-1 transition-all duration-200 group-hover:opacity-100 group-hover:translate-x-0">
            Menuju lokasi
          </span>
          <svg
            width="48"
            height="48"
            viewBox="0 0 512 512"
            xmlns="http://www.w3.org/2000/svg"
            clipRule="evenodd"
            fillRule="evenodd"
          >
            <circle
              cx="256"
              cy="256"
              r="256"
              fill="#10b981"
              className="group-hover:fill-emerald-600 transition-colors duration-200"
            />
            <path
              d="M256 120c-64.12 0-116 51.88-116 116 0 76.24 101.12 175.74 110.6 184.88a8 8 0 0010.8 0C270.88 411.74 372 312.24 372 236c0-64.12-51.88-116-116-116zm0 156a40 40 0 1140-40 40.05 40.05 0 01-40 40z"
              fill="#ffffff"
              className="group-hover:fill-emerald-100 transition-colors duration-200"
            />
          </svg>
        </button>

        {/* Want to Visit Button */}
        <button
          onClick={toggleWantToVisit}
          className="relative transition-all duration-200 hover:scale-110 focus:outline-none bg-transparent border-0 p-0 group"
        >
          <span className="pointer-events-none absolute right-full mr-3 top-1/2 -translate-y-1/2 whitespace-nowrap rounded-full bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white shadow-lg opacity-0 -translate-x-1 transition-all duration-200 group-hover:opacity-100 group-hover:translate-x-0">
            {isWantToVisit ? 'Hapus simpan' : 'Simpan tempat ini'}
          </span>
          <svg
            width="48"
            height="48"
            viewBox="0 0 512 512"
            xmlns="http://www.w3.org/2000/svg"
            clipRule="evenodd"
            fillRule="evenodd"
          >
            {isWantToVisit ? (
              // After click: lingkaran putih + border blue + bookmark blue (filled)
              <>
                <circle 
                  cx="256" 
                  cy="256" 
                  r="256" 
                  fill="#ffffff"
                  className="group-hover:fill-blue-100 transition-colors duration-200"
                />
                <circle 
                  cx="256" 
                  cy="256" 
                  r="240" 
                  fill="none"
                  stroke="#3b82f6"
                  strokeWidth="30"
                  className="group-hover:stroke-blue-600 transition-colors duration-200"
                />
                <path
                  d="M170 140c0-11.046 8.954-20 20-20h132c11.046 0 20 8.954 20 20v232l-86-43-86 43V140z"
                  fill="#3b82f6"
                  className="group-hover:fill-blue-600 transition-colors duration-200"
                />
              </>
            ) : (
              // Default: lingkaran blue + bookmark putih
              <>
                <circle 
                  cx="256" 
                  cy="256" 
                  r="256" 
                  fill="#3b82f6"
                  className="group-hover:fill-blue-500 transition-colors duration-200"
                />
                <path
                  d="M170 140c0-11.046 8.954-20 20-20h132c11.046 0 20 8.954 20 20v232l-86-43-86 43V140z"
                  fill="#ffffff"
                  className="group-hover:fill-blue-200 transition-colors duration-200"
                />
              </>
            )}
          </svg>
        </button>

        {/* Favorite Button */}
        <button
          type="button"
          data-testid="shop-toggle-favorite"
          onClick={toggleFavorite}
          className="relative transition-all duration-200 hover:scale-110 focus:outline-none bg-transparent border-0 p-0 group"
        >
          <span className="pointer-events-none absolute right-full mr-3 top-1/2 -translate-y-1/2 whitespace-nowrap rounded-full bg-pink-600 px-3 py-1.5 text-xs font-semibold text-white shadow-lg opacity-0 -translate-x-1 transition-all duration-200 group-hover:opacity-100 group-hover:translate-x-0">
            {isFavorite ? 'Hapus favorit' : 'Tambah favorit'}
          </span>
          <svg
            width="48"
            height="48"
            viewBox="0 0 512 512"
            xmlns="http://www.w3.org/2000/svg"
            clipRule="evenodd"
            fillRule="evenodd"
          >
            {isFavorite ? (
              // After click: lingkaran putih + border pink + hati pink
              <>
                <circle 
                  cx="256" 
                  cy="256" 
                  r="256" 
                  fill="#ffffff"
                  className="group-hover:fill-pink-100 transition-colors duration-200"
                />
                <circle 
                  cx="256" 
                  cy="256" 
                  r="240" 
                  fill="none"
                  stroke="#ec4899"
                  strokeWidth="30"
                  className="group-hover:stroke-pink-600 transition-colors duration-200"
                />
                <path
                  d="m269.581 163.595c29.629-32.044 78.207-32.153 107.937 0 29.685 32.105 29.686 84.633.002 116.737-37.898 40.988-75.79 81.972-113.688 122.959-2.092 2.263-4.747 3.424-7.831 3.424s-5.738-1.161-7.831-3.424c-37.897-40.986-75.793-81.971-113.69-122.957-29.683-32.103-29.683-84.633 0-116.735 29.685-32.105 78.255-32.105 107.938-.002l13.581 14.688z"
                  fill="#ec4899"
                  className="group-hover:fill-pink-600 transition-colors duration-200"
                />
              </>
            ) : (
              // Default: lingkaran rose + hati putih
              <>
                <circle 
                  cx="256" 
                  cy="256" 
                  r="256" 
                  fill="#f43f5e"
                  className="group-hover:fill-rose-500 transition-colors duration-200"
                />
                <path
                  d="m269.581 163.595c29.629-32.044 78.207-32.153 107.937 0 29.685 32.105 29.686 84.633.002 116.737-37.898 40.988-75.79 81.972-113.688 122.959-2.092 2.263-4.747 3.424-7.831 3.424s-5.738-1.161-7.831-3.424c-37.897-40.986-75.793-81.971-113.69-122.957-29.683-32.103-29.683-84.633 0-116.735 29.685-32.105 78.255-32.105 107.938-.002l13.581 14.688z"
                  fill="#ffffff"
                  className="group-hover:fill-rose-200 transition-colors duration-200"
                />
              </>
            )}
          </svg>
        </button>
      </div>

      {/* Vote Modal */}
      <ShopVoteModal
        isOpen={isVoteModalOpen}
        onClose={() => setIsVoteModalOpen(false)}
        shopName={shop?.name}
        summary={voteSummary}
        myVote={myVote}
        onSubmit={handleSubmitVote}
        isSubmitting={isSubmittingVote}
      />

      {/* Login Modal untuk Guest */}
      {showLoginModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-zinc-800 rounded-xl p-6 max-w-md w-full shadow-2xl">
            <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              Login Diperlukan
            </h3>
            <p className="text-gray-700 dark:text-gray-300 mb-6">
              Untuk {pendingAction === 'favorite'
                ? 'menambahkan ke favorit'
                : pendingAction === 'vote'
                  ? 'memberikan vote'
                  : 'menambahkan ke want to visit'}, 
              Anda perlu login terlebih dahulu. Apakah Anda ingin login sekarang?
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowLoginModal(false);
                  setPendingAction(null);
                }}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-zinc-700 rounded-lg hover:bg-gray-200 dark:hover:bg-zinc-600 transition-colors"
              >
                Tidak
              </button>
              <button
                onClick={() => {
                  setShowLoginModal(false);
                  setPendingAction(null);
                  // Navigate to login dengan state untuk redirect kembali
                  navigate('/login', { 
                    state: { 
                      redirectTo: placeIdFromRoute ? `/shop/${placeIdFromRoute}` : '/',
                      scrollToReview: false
                    } 
                  });
                }}
                className="px-4 py-2 text-sm font-medium text-white bg-amber-600 rounded-lg hover:bg-amber-700 transition-colors"
              >
                Ya, Login
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ShopDetail;

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
import { addToRecentlyViewed } from '../utils/recentlyViewed';
import { getCoffeeShopImage } from '../utils/coffeeShopImages';
import ShopPlacesMetaChips from '../components/ShopPlacesMetaChips';
import ShopOpeningHoursBlock from '../components/ShopOpeningHoursBlock';
import { parseJsonField, resolveShopPlacesMeta } from '../utils/googlePlacesDisplay';

// API Configuration (samakan sumber data dengan homepage)
import { API_BASE } from '../config/apiBase.js';
import { authService } from '../services/authService';
// Using Supabase only - photos stored in Supabase Storage
const MIN_REVIEWS = 15; // Maksimal jumlah reviews yang ditampilkan

/** Map bintang 1–5 (reviews.rating) ke bucket tampilan love/like/… */
function starCountsToRatingCounts(starCounts) {
  const stars = starCounts || {};
  return {
    love: Number(stars['5']) || 0,
    like: Number(stars['4']) || 0,
    ok: Number(stars['3']) || 0,
    dislike: Number(stars['2']) || 0,
    hate: Number(stars['1']) || 0,
  };
}

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
  const [voteSummary, setVoteSummary] = useState(null);
  const [reviewRatingSummary, setReviewRatingSummary] = useState(null);
  const [myVote, setMyVote] = useState(null);
  const [isVoteModalOpen, setIsVoteModalOpen] = useState(false);
  const [isSubmittingVote, setIsSubmittingVote] = useState(false);
  const reviewFormRef = useRef(null); // Ref untuk scroll ke review form

  const placeIdForApi = useMemo(() => {
    if (shop?.place_id != null && String(shop.place_id).trim() !== '') {
      return String(shop.place_id).trim();
    }
    return placeIdFromRoute;
  }, [shop?.place_id, placeIdFromRoute]);

  const reviewRatingVoteSummary = useMemo(
    () => ({
      rating_counts: starCountsToRatingCounts(reviewRatingSummary?.star_counts),
    }),
    [reviewRatingSummary],
  );

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
            const googleSnapshot = parseJsonField(detail.google_places_snapshot);
            const facilities = parseJsonField(detail.facilities);
            const placesMeta = resolveShopPlacesMeta(
              { ...detail, opening_hours: googleSnapshot?.opening_hours },
              googleSnapshot,
            );
            const normalized = {
              place_id: detail.place_id,
              name: detail.name,
              address: detail.address,
              rating: placesMeta.rating,
              user_ratings_total: placesMeta.userRatingsTotal,
              total_reviews: placesMeta.userRatingsTotal,
              price_level_label: placesMeta.priceLevelLabel,
              location: detail.location || null,
              photos: [],
              business_status_label: placesMeta.businessStatusLabel,
              phone: detail.phone || googleSnapshot?.phone || null,
              website: detail.website || googleSnapshot?.website || null,
              google_maps_url: detail.google_maps_url || googleSnapshot?.google_maps_url || null,
              map_embed_url: detail.map_embed_url || null,
              opening_hours_display: detail.opening_hours_display ?? '',
              opening_hours:
                googleSnapshot?.opening_hours
                ?? (placesMeta.openNow !== undefined ? { open_now: placesMeta.openNow } : null),
              placesMeta,
              facilities,
              google_places_snapshot: googleSnapshot,
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
            { headers: authService.getAuthHeaders() },
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
            { headers: authService.getAuthHeaders() },
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

  const fetchReviewRatingSummary = async (pid) => {
    if (!pid) return;
    try {
      const response = await fetch(
        `${API_BASE}/api/coffeeshops/${encodeURIComponent(pid)}/reviews/rating-summary`,
      );
      if (!response.ok) {
        setReviewRatingSummary(null);
        return;
      }
      const payload = await response.json();
      if (payload?.status === 'success') {
        setReviewRatingSummary({
          star_counts: payload.star_counts || {},
          review_star_total: payload.review_star_total ?? 0,
          average_rating: payload.average_rating ?? null,
        });
      }
    } catch (err) {
      console.error('[ShopDetail] Error fetching review rating summary:', err);
      setReviewRatingSummary(null);
    }
  };

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
        { headers: authService.getAuthHeaders() },
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
    fetchReviewRatingSummary(placeIdForApi);
    fetchMyVote(placeIdForApi);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [placeIdForApi, isAuthenticated, user?.id]);

  useEffect(() => {
    if (!placeIdForApi || !newReview) return;
    fetchReviewRatingSummary(placeIdForApi);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [newReview, placeIdForApi]);

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
        headers: authService.getAuthHeaders({ 'Content-Type': 'application/json' }),
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
          headers: authService.getAuthHeaders({ 'Content-Type': 'application/json' }),
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
          headers: authService.getAuthHeaders({ 'Content-Type': 'application/json' }),
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
          headers: authService.getAuthHeaders({ 'Content-Type': 'application/json' }),
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
          headers: authService.getAuthHeaders({ 'Content-Type': 'application/json' }),
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
          <ShopPlacesMetaChips meta={shop.placesMeta} />
        </div>

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

          {/* Jam Operasional — hari ini + jadwal lengkap (dropdown) */}
          <ShopOpeningHoursBlock shop={shop} />

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
            
            {shop.google_maps_url && (
              <a
                href={shop.google_maps_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 px-6 py-4 bg-white dark:bg-zinc-800 border border-gray-200 dark:border-zinc-600 text-gray-800 dark:text-gray-100 font-medium rounded-lg shadow-sm hover:shadow transition-all duration-200 flex-1"
              >
                <span>Kunjungi di Google Maps</span>
              </a>
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
          <h2 className="mb-4 text-xl sm:text-2xl font-bold text-gray-900 dark:text-white">
            Ratings
          </h2>
          <ShopVotesSummary
            summary={reviewRatingVoteSummary}
            readOnly
            hidePresence
          />
        </div>
      )}

      {/* Ringkasan facilities (popular_for, highlights, atmosphere, amenities) */}
      {shop?.place_id && (shop.facilities || shop.google_places_snapshot) && (
        <div className="mt-6 sm:mt-8">
          <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white mb-4">
            Fasilitas
          </h2>
          <FacilitiesTab
            facilities={shop.facilities}
            googleSnapshot={shop.google_places_snapshot}
          />
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

      {/* Reviews Section */}
      <div className="mt-6 sm:mt-8 space-y-6" ref={reviewFormRef}>
        {shop?.place_id && (
          <div>
            <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white mb-4">
              Reviews
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

import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { supabase, isSupabaseConfigured } from '../lib/supabase';
import OptimizedImage from '../components/OptimizedImage';
import SmartReviewSummary from '../components/SmartReviewSummary';
import FacilitiesTab from '../components/FacilitiesTab';
import ReviewForm from '../components/ReviewForm';
import ReviewList from '../components/ReviewList';
import localPlacesData from '../data/places.json';
import facilitiesData from '../data/facilities.json';
import { getCoffeeShopImage } from '../utils/coffeeShopImages';
import { addToRecentlyViewed } from '../utils/recentlyViewed';

// Konfigurasi API (mengikuti ShopList)
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';
const USE_API = import.meta.env.VITE_USE_API === 'true';
const USE_LOCAL_DATA = true; // Set true untuk menggunakan data lokal JSON
const MIN_REVIEWS = 15; // Maksimal jumlah reviews yang ditampilkan

function ShopDetail() {
  const { id } = useParams();  // id akan mengambil place_id
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth();
  const [shop, setShop] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [isFavorite, setIsFavorite] = useState(false);
  const [isWantToVisit, setIsWantToVisit] = useState(false);
  const [notification, setNotification] = useState(null);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [pendingAction, setPendingAction] = useState(null); // 'favorite' or 'wantToVisit'
  const [newReview, setNewReview] = useState(null); // For triggering ReviewList update
  const reviewFormRef = useRef(null); // Ref untuk scroll ke review form

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

  useEffect(() => {
    const loadShop = async () => {
      try {
        setIsLoading(true);
        setError(null);

        // Prioritaskan data lokal jika USE_LOCAL_DATA aktif
        if (USE_LOCAL_DATA) {
          console.log('[ShopDetail] Using local JSON data for place_id:', id);
          
          if (localPlacesData && localPlacesData.data && Array.isArray(localPlacesData.data)) {
            const foundShop = localPlacesData.data.find(shop => shop.place_id === id);
            
            if (foundShop) {
              console.log('[ShopDetail] Found shop in local data:', foundShop.name);
              const normalized = {
                place_id: foundShop.place_id,
                name: foundShop.name,
                address: foundShop.address,
                rating: foundShop.rating,
                price_level: foundShop.price_level,
                user_ratings_total: foundShop.user_ratings_total,
                location: foundShop.location,
                photos: Array.isArray(foundShop.photos) ? foundShop.photos : [],
                business_status: foundShop.business_status,
                map_embed_url: foundShop.map_embed_url || null,
              };
              setShop(normalized);
              
              // Simpan ke recently viewed
              addToRecentlyViewed(normalized);
              
              // Reviews sekarang hanya dari Supabase (via ReviewList component)
              // Tidak perlu load dari reviews.json lagi
              setReviews([]);
              setIsLoading(false);
              return;
            } else {
              throw new Error('Coffee shop tidak ditemukan dalam data lokal.');
            }
          } else {
            throw new Error('Format data lokal tidak valid.');
          }
        }

        // Direct API call without caching
        if (USE_API) {
          try {
            const detailUrl = `${API_BASE}/api/coffeeshops/detail/${id}`;
            console.log('[ShopDetail] Fetching from API:', detailUrl);
            
            const response = await fetch(detailUrl);
            
            if (!response.ok) {
              throw new Error(`API returned status ${response.status}`);
            }
            
            const payload = await response.json();
            
            if (payload?.status === 'success' && payload?.data) {
              const detail = payload.data;
              // Normalisasi sebagian field agar konsisten dengan list
              const normalized = {
                place_id: id,
                name: detail.name,
                address: detail.formatted_address,
                rating: detail.rating,
                price_level: detail.price_level,
                phone: detail.formatted_phone_number,
                website: detail.website,
                location: detail.geometry?.location,
                photos: Array.isArray(detail.photos)
                  ? detail.photos.slice(0, 5) // Foto sudah dalam format URL string langsung
                  : [],
              };
              setShop(normalized);
              
              // Simpan ke recently viewed
              addToRecentlyViewed(normalized);
              
              // Hanya tampilkan komentar yang punya teks, dan batasi maksimal 10 reviews
              const reviewsWithText = Array.isArray(detail.reviews)
                ? detail.reviews
                    .filter((r) => (r?.text || '').trim().length > 0)
                    .slice(0, MIN_REVIEWS)
                : [];
              setReviews(reviewsWithText);
              setIsLoading(false);
              return;
            }
          } catch (apiErr) {
            console.error('[ShopDetail] Failed to load from API:', apiErr?.message);
            throw new Error(`Unable to load coffee shop details. Please ensure the backend is running and you have internet connection.`);
          }
        }

        // If API is disabled, show error
        throw new Error(`API is disabled. Please enable it to view shop details.`);
      } catch (err) {
        console.error("Load Error:", err);
        setError(err.message || 'Gagal memuat detail toko');
        setShop(null);
        setReviews([]);
        setIsLoading(false);
      }
    };

    loadShop();
  }, [id]);

  // Check if shop is favorited or in want-to-visit (from Supabase or localStorage)
  useEffect(() => {
    const checkFavoriteStatus = async () => {
      if (!id) return;
      
      // If user is authenticated and Supabase is configured, check from Supabase
      if (isAuthenticated && user?.id && isSupabaseConfigured && supabase) {
        try {
          // Check favorite
          const { data: favoriteData, error: favoriteError } = await supabase
            .from('favorites')
            .select('id')
            .eq('user_id', user.id)
            .eq('place_id', id)
            .maybeSingle();
          
          if (!favoriteError && favoriteData) {
            setIsFavorite(true);
          } else {
            setIsFavorite(false);
          }
          
          // Check want to visit
          const { data: wantToVisitData, error: wantToVisitError } = await supabase
            .from('want_to_visit')
            .select('id')
            .eq('user_id', user.id)
            .eq('place_id', id)
            .maybeSingle();
          
          if (!wantToVisitError && wantToVisitData) {
            setIsWantToVisit(true);
          } else {
            setIsWantToVisit(false);
          }
        } catch (err) {
          console.error('[ShopDetail] Error checking favorite/want to visit status:', err);
          // Fallback to localStorage
          const favorites = JSON.parse(localStorage.getItem('favoriteShops') || '[]');
          setIsFavorite(favorites.includes(id));
          
          const wantToVisit = JSON.parse(localStorage.getItem('wantToVisitShops') || '[]');
          setIsWantToVisit(wantToVisit.includes(id));
        }
      } else {
        // Guest mode: use localStorage
        const favorites = JSON.parse(localStorage.getItem('favoriteShops') || '[]');
        setIsFavorite(favorites.includes(id));
        
        const wantToVisit = JSON.parse(localStorage.getItem('wantToVisitShops') || '[]');
        setIsWantToVisit(wantToVisit.includes(id));
      }
    };
    
    checkFavoriteStatus();
  }, [id, isAuthenticated, user?.id]);

  const toggleFavorite = async () => {
    // If guest, show login modal
    if (!isAuthenticated || !user?.id) {
      setPendingAction('favorite');
      setShowLoginModal(true);
      return;
    }
    
    try {
      // If user is authenticated and Supabase is configured, save to Supabase
      if (isSupabaseConfigured && supabase) {
        if (isFavorite) {
          // Remove from favorites in Supabase
          const { error } = await supabase
            .from('favorites')
            .delete()
            .eq('user_id', user.id)
            .eq('place_id', id);
          
          if (error) {
            console.error('[ShopDetail] Error removing favorite:', error);
            setNotification({ type: 'error', message: 'Gagal menghapus dari favorit' });
            return;
          }
          
          setNotification({ type: 'removed', message: 'Dihapus dari favorit' });
        } else {
          // Add to favorites in Supabase
          const { error } = await supabase
            .from('favorites')
            .insert({ user_id: user.id, place_id: id });
          
          if (error) {
            console.error('[ShopDetail] Error adding favorite:', error);
            setNotification({ type: 'error', message: 'Gagal menambahkan ke favorit' });
            return;
          }
          
          setNotification({ type: 'added', message: 'Ditambahkan ke favorit!' });
        }
        
        setIsFavorite(!isFavorite);
      } else {
        // Guest mode: use localStorage
        const favorites = JSON.parse(localStorage.getItem('favoriteShops') || '[]');
        if (isFavorite) {
          // Remove from favorites
          const updated = favorites.filter(fav => fav !== id);
          localStorage.setItem('favoriteShops', JSON.stringify(updated));
          setNotification({ type: 'removed', message: 'Dihapus dari favorit' });
        } else {
          // Add to favorites
          if (!favorites.includes(id)) {
            favorites.push(id);
            localStorage.setItem('favoriteShops', JSON.stringify(favorites));
          }
          setNotification({ type: 'added', message: 'Ditambahkan ke favorit!' });
        }
        setIsFavorite(!isFavorite);
      }
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
    
    try {
      // If user is authenticated and Supabase is configured, save to Supabase
      if (isSupabaseConfigured && supabase) {
        if (isWantToVisit) {
          // Remove from want to visit in Supabase
          const { error } = await supabase
            .from('want_to_visit')
            .delete()
            .eq('user_id', user.id)
            .eq('place_id', id);
          
          if (error) {
            console.error('[ShopDetail] Error removing want to visit:', error);
            setNotification({ type: 'error', message: 'Gagal menghapus dari want to visit' });
            return;
          }
          
          setNotification({ type: 'removed', message: 'Dihapus dari want to visit' });
        } else {
          // Add to want to visit in Supabase
          const { error } = await supabase
            .from('want_to_visit')
            .insert({ user_id: user.id, place_id: id });
          
          if (error) {
            console.error('[ShopDetail] Error adding want to visit:', error);
            setNotification({ type: 'error', message: 'Gagal menambahkan ke want to visit' });
            return;
          }
          
          setNotification({ type: 'added', message: 'Ditambahkan ke want to visit!' });
        }
        
        setIsWantToVisit(!isWantToVisit);
      } else {
        // Guest mode: use localStorage
        const wantToVisit = JSON.parse(localStorage.getItem('wantToVisitShops') || '[]');
        if (isWantToVisit) {
          // Remove from want-to-visit
          const updated = wantToVisit.filter(item => item !== id);
          localStorage.setItem('wantToVisitShops', JSON.stringify(updated));
          setNotification({ type: 'removed', message: 'Dihapus dari want to visit' });
        } else {
          // Add to want-to-visit
          if (!wantToVisit.includes(id)) {
            wantToVisit.push(id);
            localStorage.setItem('wantToVisitShops', JSON.stringify(wantToVisit));
          }
          setNotification({ type: 'added', message: 'Ditambahkan ke want to visit!' });
        }
        setIsWantToVisit(!isWantToVisit);
      }
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
        <div className={`fixed top-8 left-1/2 transform -translate-x-1/2 px-6 py-3 rounded-lg shadow-lg text-white font-medium z-50 transition-all duration-300 animate-fade-in ${
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
        {/* Foto Coffee Shop - dengan optimasi loading */}
        <div className="mb-6 rounded-xl overflow-hidden shadow-lg">
          <div className="w-full h-56 sm:h-64 md:h-80">
            <OptimizedImage
              src={getCoffeeShopImage(shop.place_id || shop.name)}
              alt={shop.name}
              className="w-full h-full object-cover"
              fallbackColor={(() => {
                const seed = (shop.name || 'Coffee Shop').length % 10;
                const colors = ['#4F46E5', '#7C3AED', '#EC4899', '#F59E0B', '#10B981', '#3B82F6', '#8B5CF6', '#F97316', '#06B6D4', '#6366F1'];
                return colors[seed % colors.length];
              })()}
              shopName={shop.name}
            />
          </div>
        </div>

        {/* Informasi Utama */}
        <div className="space-y-4">
          <div>
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

      {/* Smart Review Summary - AI Analysis */}
      {/* Reviews sekarang hanya dari Supabase, SmartReviewSummary akan fetch sendiri */}
      {shop?.place_id && (
        <div className="mt-6 sm:mt-8">
          <SmartReviewSummary 
            shopName={shop.name}
            placeId={shop.place_id}
          />
        </div>
      )}

      {/* Facilities Section */}
      {shop?.place_id && facilitiesData?.facilities_by_place_id?.[shop.place_id] && (
        <div className="mt-6 sm:mt-8">
          <div className="mb-4">
            <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <svg className="w-6 h-6 text-amber-600 dark:text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
              Fasilitas & Layanan
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
              Informasi lengkap tentang fasilitas, layanan, dan amenitas yang tersedia
            </p>
          </div>
          <FacilitiesTab 
            facilities={facilitiesData.facilities_by_place_id[shop.place_id].facilities}
          />
        </div>
      )}

      {/* Static Map */}
      <div className="mt-6 sm:mt-8">
        <div className="bg-white dark:bg-zinc-800 p-4 sm:p-6 rounded-xl shadow border border-gray-200 dark:border-zinc-700">
          <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white mb-4">
            📍 Lokasi
          </h2>
          {/* Prioritaskan iframe embed jika tersedia */}
          {shop.map_embed_url ? (
            <div className="rounded-lg overflow-hidden">
              <iframe
                src={shop.map_embed_url}
                width="100%"
                height="320"
                style={{ border: 0 }}
                allowFullScreen=""
                loading="lazy"
                referrerPolicy="no-referrer-when-downgrade"
                className="w-full h-64 sm:h-80 rounded-lg"
                title={`Peta lokasi ${shop.name}`}
              />
              {shop.location && (
                <div className="mt-3 flex justify-center">
                  <a
                    href={`https://www.google.com/maps/search/?api=1&query=${shop.location.lat},${shop.location.lng}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 transition shadow-md"
                  >
                    <svg className="w-4 h-4" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
                      <path d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
                      <path d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
                    </svg>
                    Buka di Google Maps
                  </a>
                </div>
              )}
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
            <div className="w-full h-64 sm:h-80 bg-gray-200 dark:bg-zinc-700 rounded-lg flex items-center justify-center">
              <p className="text-gray-600 dark:text-gray-400">Lokasi tidak tersedia</p>
            </div>
          )}
        </div>
      </div>

      {/* Reviews Section */}
      <div className="mt-6 sm:mt-8 space-y-6">
        {/* Review Form */}
        <div ref={reviewFormRef}>
          <ReviewForm 
            placeId={shop.place_id}
            shopName={shop.name}
            onReviewSubmitted={(review) => {
              console.log('[ShopDetail] Review submitted:', review);
              setNewReview(review);
            }}
          />
        </div>

        {/* Review List - Only render if shop and place_id are loaded */}
        {shop?.place_id && (
          <div>
            <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white mb-4">
              Review Pengunjung
            </h2>
            <ReviewList 
              placeId={shop.place_id}
              newReview={newReview}
            />
          </div>
        )}
      </div>

      {/* Floating Action Buttons - pojok kanan bawah (untuk semua user, termasuk guest) */}
      <div className="fixed bottom-8 right-8 flex flex-col gap-4 z-40">
        {/* Want to Visit Button */}
        <button
          onClick={toggleWantToVisit}
          className="transition-all duration-200 hover:scale-110 focus:outline-none bg-transparent border-0 p-0 group"
          title={isWantToVisit ? 'Hapus dari want to visit' : 'Tambah ke want to visit'}
        >
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
          onClick={toggleFavorite}
          className="transition-all duration-200 hover:scale-110 focus:outline-none bg-transparent border-0 p-0 group"
          title={isFavorite ? 'Hapus dari favorit' : 'Tambah ke favorit'}
        >
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

      {/* Login Modal untuk Guest */}
      {showLoginModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-zinc-800 rounded-xl p-6 max-w-md w-full shadow-2xl">
            <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              Login Diperlukan
            </h3>
            <p className="text-gray-700 dark:text-gray-300 mb-6">
              Untuk {pendingAction === 'favorite' ? 'menambahkan ke favorit' : 'menambahkan ke want to visit'}, 
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
                      redirectTo: `/shop/${id}`,
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

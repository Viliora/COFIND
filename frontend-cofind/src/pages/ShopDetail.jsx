import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import OptimizedImage from '../components/OptimizedImage';

// Konfigurasi API (mengikuti ShopList)
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';
const USE_API = import.meta.env.VITE_USE_API === 'true';
const MIN_REVIEWS = 10; // Maksimal jumlah reviews yang ditampilkan

function ShopDetail() {
  const { id } = useParams();  // id akan mengambil place_id
  const [shop, setShop] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [isFavorite, setIsFavorite] = useState(false);
  const [notification, setNotification] = useState(null);

  useEffect(() => {
    const loadShop = async () => {
      try {
        setIsLoading(true);
        setError(null);

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
                  ? detail.photos
                      .slice(0, 5)
                      .map(p => p.photo_reference) // akan dipakai oleh backend jika dibutuhkan
                  : [],
              };
              setShop(normalized);
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

  // Check if shop is favorited
  useEffect(() => {
    if (id) {
      const favorites = JSON.parse(localStorage.getItem('favoriteShops') || '[]');
      setIsFavorite(favorites.includes(id));
    }
  }, [id]);

  const toggleFavorite = () => {
    try {
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
    } catch (err) {
      console.error('Error toggling favorite:', err);
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
        <Link to="/" className="text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300 font-medium inline-block text-sm sm:text-base">← Kembali ke Daftar</Link>
      </div>
      <div className="bg-white dark:bg-zinc-800 p-4 sm:p-6 md:p-8 rounded-xl shadow-2xl border border-gray-200 dark:border-zinc-700">
        <h1 className="text-2xl sm:text-3xl md:text-4xl font-extrabold text-gray-900 dark:text-white mb-2 break-words">{shop.name}</h1>
        <div className="flex flex-wrap items-center gap-2 sm:gap-3 mb-4">
          <p className="text-lg sm:text-xl text-indigo-700 dark:text-indigo-400 font-semibold">⭐ {shop.rating || 'N/A'}</p>
          {shop.price_level && (
            <>
              <p className="text-gray-400 dark:text-gray-500 hidden sm:inline"></p>
              
            </>
          )}
        </div>
        
        <p className="text-base sm:text-lg text-gray-700 dark:text-gray-300 mb-4 break-words">{shop.address}</p>
        
        {shop.phone && (
          <p className="text-sm sm:text-base text-gray-600 dark:text-gray-400 mb-2 break-all">📞 {shop.phone}</p>
        )}
        
        {shop.website && (
          <a href={shop.website} target="_blank" rel="noopener noreferrer" 
             className="text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300 mb-4 block text-sm sm:text-base break-all">
            🌐 Website
          </a>
        )}

        {/* Foto Coffee Shop - dengan optimasi loading */}
        <div className="mt-4 sm:mt-6 rounded-lg overflow-hidden">
          <div className="w-full h-48 sm:h-56 md:h-64">
            <OptimizedImage
              src={shop.photos && shop.photos.length > 0 ? shop.photos[0] : null}
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
      </div>

      {/* Static Map */}
      <div className="mt-6 sm:mt-8">
        <div className="bg-white dark:bg-zinc-800 p-4 sm:p-6 rounded-xl shadow border border-gray-200 dark:border-zinc-700">
          <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white mb-4">
            📍 Lokasi
          </h2>
          {shop.location ? (
            <div className="rounded-lg overflow-hidden">
              {(() => {
                const lat = shop.location.lat;
                const lng = shop.location.lng;
                const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;
                
                // Build static map URL
                const mapUrl = `https://maps.googleapis.com/maps/api/staticmap?center=${lat},${lng}&zoom=16&size=800x400&markers=color:red%7C${lat},${lng}&key=${apiKey}`;
                
                return (
                  <>
                    <img
                      src={mapUrl}
                      alt="Peta lokasi"
                      className="w-full h-64 sm:h-80 object-cover rounded-lg"
                      onError={(e) => {
                        console.error('Static map failed to load:', e);
                        const fallback = e.target.parentElement.querySelector('[data-fallback="true"]');
                        if (fallback) fallback.style.display = 'flex';
                        e.target.style.display = 'none';
                      }}
                    />
                    <div
                      data-fallback="true"
                      className="hidden w-full h-64 sm:h-80 bg-gradient-to-br from-gray-100 to-gray-200 dark:from-zinc-700 dark:to-zinc-800 rounded-lg items-center justify-center flex-col gap-3"
                    >
                      <div className="text-center">
                        <p className="text-2xl mb-2">📍</p>
                        <p className="text-gray-600 dark:text-gray-400 text-sm mb-1">Koordinat Lokasi:</p>
                        <p className="text-lg font-mono font-semibold text-gray-900 dark:text-white">
                          {lat.toFixed(6)}, {lng.toFixed(6)}
                        </p>
                        <a
                          href={`https://www.google.com/maps/search/${lat},${lng}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-block mt-3 px-3 py-1 bg-indigo-600 text-white text-xs rounded hover:bg-indigo-700 transition"
                        >
                          Buka di Google Maps
                        </a>
                      </div>
                    </div>
                  </>
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

      {/* Box Komentar / Reviews */}
      <div className="mt-6 sm:mt-8">
        <div className="bg-white dark:bg-zinc-800 p-4 sm:p-6 rounded-xl shadow border border-gray-200 dark:border-zinc-700">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white">
              Komentar Pengunjung
            </h2>
            {Array.isArray(reviews) && reviews.length > 0 && (
              <span className="text-sm text-gray-500 dark:text-gray-400">
                Menampilkan {reviews.length} dari {reviews.length} komentar
              </span>
            )}
          </div>

          {/* Bila ada reviews dari Google Places */}
          {Array.isArray(reviews) && reviews.length > 0 ? (
            <ul className="space-y-4">
              {reviews.map((rev, idx) => (
                <li key={idx} className="border-b last:border-b-0 border-gray-100 dark:border-zinc-700 pb-4">
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-10 h-10 rounded-full bg-indigo-100 dark:bg-indigo-900/40 flex items-center justify-center text-indigo-700 dark:text-indigo-300 font-semibold">
                      {(rev.author_name || '?').slice(0,1).toUpperCase()}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <p className="font-semibold text-gray-900 dark:text-gray-100">{rev.author_name || 'Anonim'}</p>
                        <span className="text-xs text-gray-500 dark:text-gray-400">{rev.relative_time_description || ''}</span>
                      </div>
                      {typeof rev.rating === 'number' && (
                        <p className="text-sm text-yellow-600 dark:text-yellow-400 mt-0.5">{"⭐".repeat(Math.round(rev.rating))} <span className="text-xs text-gray-500 dark:text-gray-400">({rev.rating})</span></p>
                      )}
                      <p className="text-sm text-gray-700 dark:text-gray-300 mt-2 whitespace-pre-line">{rev.text || ''}</p>
                      {rev.author_url && (
                        <a
                          href={rev.author_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-block mt-2 text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
                        >
                          Lihat profil di Google
                        </a>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Belum ada komentar yang tersedia.
              {!USE_API && ' Aktifkan API untuk menampilkan komentar dari Google Places.'}
            </p>
          )}
        </div>
      </div>

      {/* Floating Favorite Button - pojok kanan bawah */}
      <button
        onClick={toggleFavorite}
        className="fixed bottom-8 right-8 transition-all duration-200 hover:scale-110 focus:outline-none bg-transparent border-0 p-0 group z-40"
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
  );
}

export default ShopDetail;

import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import placesData from '../data/places.json';

function ShopDetail() {
  const { id } = useParams();  // id akan mengambil place_id
  const [shop, setShop] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Cari shop berdasarkan place_id dari places.json
    const loadShop = () => {
      try {
        setIsLoading(true);
        setError(null);
        
        // Cari shop dengan place_id yang sesuai
        const foundShop = placesData?.data?.find(shop => shop.place_id === id);
        
        if (foundShop) {
          setShop(foundShop);
          setError(null);
        } else {
          throw new Error(`Coffee shop dengan ID "${id}" tidak ditemukan`);
        }
      } catch (err) {
        console.error("Load Error:", err);
        setError(err.message);
        setShop(null); 
      } finally {
        setIsLoading(false);
      }
    };
    
    loadShop();
  }, [id]);

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
    <div className="w-full py-4 sm:py-6 md:py-8 px-4 sm:px-6">
      <Link to="/" className="text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300 font-medium mb-4 inline-block text-sm sm:text-base">← Kembali ke Daftar</Link>
      <div className="bg-white dark:bg-zinc-800 p-4 sm:p-6 md:p-8 rounded-xl shadow-2xl border border-gray-200 dark:border-zinc-700">
        <h1 className="text-2xl sm:text-3xl md:text-4xl font-extrabold text-gray-900 dark:text-white mb-2 break-words">{shop.name}</h1>
        <div className="flex flex-wrap items-center gap-2 sm:gap-3 mb-4">
          <p className="text-lg sm:text-xl text-indigo-700 dark:text-indigo-400 font-semibold">⭐ {shop.rating || 'N/A'}</p>
          {shop.price_level && (
            <>
              <p className="text-gray-400 dark:text-gray-500 hidden sm:inline">|</p>
              <p className="text-base sm:text-lg text-green-600 dark:text-green-400">{'💰'.repeat(shop.price_level)}</p>
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

        {/* Foto Coffee Shop - menggunakan SVG placeholder inline (tidak perlu network request) */}
        <div className="mt-4 sm:mt-6">
          {(() => {
            // Generate SVG placeholder inline - tidak perlu network request
            const shopName = shop.name || 'Coffee Shop';
            let imageSrc;
            
            if (shop.photos && shop.photos.length > 0) {
              imageSrc = shop.photos[0];
            } else {
              const seed = shopName.length % 10;
              const colors = ['4F46E5', '7C3AED', 'EC4899', 'F59E0B', '10B981', '3B82F6', '8B5CF6', 'F97316', '06B6D4', '6366F1'];
              const color = colors[seed % colors.length];
              const svg = `<svg width="1200" height="600" xmlns="http://www.w3.org/2000/svg"><rect width="1200" height="600" fill="#${color}"/><text x="50%" y="50%" font-family="Arial, sans-serif" font-size="64" fill="#FFFFFF" text-anchor="middle" dy=".3em">☕ ${shopName.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</text></svg>`;
              imageSrc = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svg)));
            }
            
            return (
              <img 
                src={imageSrc}
                alt={shop.name} 
                className="w-full h-48 sm:h-56 md:h-64 object-cover rounded-lg" 
                onError={(e) => {
                  // Fallback ke SVG placeholder jika gagal
                  e.target.onerror = null;
                  const svg = '<svg width="1200" height="600" xmlns="http://www.w3.org/2000/svg"><rect width="1200" height="600" fill="#4F46E5"/><text x="50%" y="50%" font-family="Arial, sans-serif" font-size="64" fill="#FFFFFF" text-anchor="middle" dy=".3em">☕ Coffee Shop</text></svg>';
                  e.target.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svg)));
                }}
              />
            );
          })()}
        </div>
      </div>
    </div>
  );
}

export default ShopDetail;

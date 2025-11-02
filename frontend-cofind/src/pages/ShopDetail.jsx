import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';

const API_DETAIL_URL = 'http://127.0.0.1:5000/api/coffeeshops/detail/';

function ShopDetail() {
  const { id } = useParams();  // id akan mengambil place_id
  const [shop, setShop] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchShop = async () => {
      try {
        const response = await fetch(`${API_DETAIL_URL}${id}`);
        
        if (!response.ok) {
          throw new Error(`Gagal mengambil data, status: ${response.status}`);
        }
        
        const result = await response.json();
        if (result.status === 'success') {
          setShop(result.data);
          setError(null);
        } else {
          throw new Error(result.message || 'Gagal mengambil detail coffee shop');
        }
      } catch (err) {
        console.error("Fetch Error:", err);
        setError(err.message);
        setShop(null); 
      } finally {
        setIsLoading(false);
      }
    };
    fetchShop();
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
    <div className="max-w-3xl mx-auto py-4 sm:py-6 md:py-8 px-3 sm:px-4 md:px-6">
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

        {/* Foto Coffee Shop */}
        {shop.photos && shop.photos.length > 0 && (
          <div className="mt-4 sm:mt-6">
            <img 
              src={shop.photos[0]} 
              alt={shop.name} 
              className="w-full h-48 sm:h-56 md:h-64 object-cover rounded-lg" 
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default ShopDetail;

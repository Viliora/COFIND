// src/pages/ShopDetail.jsx
import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';

// URL API untuk mengambil detail coffee shop
const API_DETAIL_URL = 'http://127.0.0.1:5000/api/coffeeshops/detail/';

function ShopDetail() {
  const { id } = useParams();
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

  if (isLoading) return <p className="text-center mt-10 text-xl text-indigo-600">Memuat Detail Toko...</p>;
  if (error) return <p className="text-center mt-10 text-xl text-red-600">{error}</p>;
  if (!shop) return <p className="text-center mt-10 text-xl text-red-600">Data Toko tidak tersedia.</p>;

  return (
    <div className="max-w-3xl mx-auto py-8">
      <Link to="/" className="text-indigo-600 hover:text-indigo-800 font-medium mb-4 inline-block">← Kembali ke Daftar</Link>
      
      <div className="bg-white p-8 rounded-xl shadow-2xl border border-gray-200">
        <h1 className="text-4xl font-extrabold text-gray-900 mb-2">{shop.name}</h1>
        <div className="flex items-center mb-4">
          <p className="text-xl text-indigo-700 font-semibold mr-3">⭐ {shop.rating || 'N/A'}</p>
          <p className="text-gray-600">|</p>
          {shop.price_level && (
            <p className="ml-3 text-green-600">{'💰'.repeat(shop.price_level)}</p>
          )}
        </div>
        
        <p className="text-lg text-gray-700 mb-4">{shop.address}</p>
        
        {shop.phone && (
          <p className="text-gray-600 mb-2">📞 {shop.phone}</p>
        )}
        
        {shop.website && (
          <a href={shop.website} target="_blank" rel="noopener noreferrer" 
             className="text-indigo-600 hover:text-indigo-800 mb-4 block">
            🌐 Website
          </a>
        )}

        {/* Jam Operasional */}
        {shop.opening_hours && shop.opening_hours.length > 0 && (
          <div className="mt-6">
            <h3 className="text-xl font-bold mb-3">Jam Operasional</h3>
            <div className="bg-gray-50 p-4 rounded-lg">
              {shop.opening_hours.map((hours, index) => (
                <p key={index} className="text-gray-700">{hours}</p>
              ))}
            </div>
          </div>
        )}

        {/* Ulasan */}
        <h3 className="text-2xl font-bold mt-8 mb-4 border-b pb-2">Ulasan Pengunjung</h3>
        <div className="space-y-4 mb-8">
          {shop.reviews && shop.reviews.length > 0 ? (
            shop.reviews.map((review, index) => (
              <div key={index} className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                <div className="flex items-center mb-2">
                  <p className="text-yellow-500">{'⭐'.repeat(review.rating)}</p>
                  <p className="ml-2 text-gray-500 text-sm">{review.relative_time_description}</p>
                </div>
                <p className="font-semibold text-gray-700">{review.author_name}</p>
                <p className="text-gray-600 mt-2">{review.text}</p>
              </div>
            ))
          ) : (
            <p className="text-gray-500">Belum ada ulasan untuk coffee shop ini.</p>
          )}
        </div>
        
      </div>
    </div>
  );
}

export default ShopDetail;
// src/pages/ShopDetail.jsx
import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';

// Ubah URL API untuk mengambil detail spesifik
const API_BASE_URL = 'http://127.0.0.1:5000/api/coffeeshops/'; 

function ShopDetail() {
  const { id } = useParams();
  const [shop, setShop] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchShop = async () => {
      try {
        // Menggunakan endpoint baru: /api/coffeeshops/1
        const response = await fetch(`${API_BASE_URL}${id}`);
        
        if (response.status === 404) {
             throw new Error("Toko tidak ditemukan.");
        }
        if (!response.ok) {
            throw new Error(`Gagal mengambil data, status: ${response.status}`);
        }
        
        const data = await response.json();
        setShop(data);
        setError(null);
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
        <h1 className="text-4xl font-extrabold text-gray-900 mb-2">{shop.nama}</h1>
        <p className="text-xl text-indigo-700 font-semibold mb-4">⭐ {shop.rating} / 5.0 | {shop.alamat}</p>

        {/* Tampilan Tags/Fitur Utama hasil Analisis LLaMA */}
        <h3 className="text-xl font-bold mt-6 mb-3">Fitur Utama (Hasil LLaMA):</h3>
        <div className="flex flex-wrap gap-2 mb-6">
            {shop.tags_llm.map(tag => (
                <span 
                    key={tag} 
                    className="bg-green-100 text-green-700 text-sm font-semibold px-3 py-1 rounded-full"
                >
                    {tag.replace('_', ' ')}
                </span>
            ))}
        </div>

        {/* Daftar Ulasan yang Ditarik dari Google Places API */}
        <h3 className="text-2xl font-bold mt-8 mb-4 border-b pb-2">Ulasan Google (UGC)</h3>
        <div className="space-y-4 mb-8">
            {shop.reviews && shop.reviews.length > 0 ? (
                shop.reviews.map((review, index) => (
                    <div key={index} className="bg-gray-50 p-4 rounded border border-gray-200">
                        <p className="italic text-gray-700 mb-2">"{review}"</p>
                        {/* Status LLaMA akan ditampilkan di sini */}
                        <span className="text-xs font-semibold text-blue-600">
                            Status LLaMA: Sentimen Positif
                        </span>
                    </div>
                ))
            ) : (
                <p className="text-gray-500">Belum ada ulasan yang diunduh untuk toko ini.</p>
            )}
        </div>
        
      </div>
    </div>
  );
}

export default ShopDetail;
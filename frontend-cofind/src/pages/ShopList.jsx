// src/pages/ShopList.jsx
import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import SearchBar from '../components/SearchBar'; 
import CoffeeShopCard from '../components/CoffeeShopCard'; 

// URL API Flask untuk mengambil semua data coffee shop
const API_URL = 'http://127.0.0.1:5000/api/coffeeshops';

function ShopList() {
  // State untuk menyimpan daftar toko
  const [coffeeShops, setCoffeeShops] = useState([]);
  // State untuk melacak status loading
  const [isLoading, setIsLoading] = useState(true);
  // State untuk fitur Search Bar (walaupun filter logikanya belum dibuat)
  const [searchTerm, setSearchTerm] = useState('');
  // State untuk menangani error koneksi API
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchShops = async () => {
      try {
        const response = await fetch(API_URL);
        
        // Periksa apakah respons HTTP berhasil (status 200)
        if (!response.ok) {
             throw new Error(`Gagal mengambil data, status: ${response.status}`);
        }
        
        const data = await response.json();
        setCoffeeShops(data);
        setError(null); // Hapus error sebelumnya jika berhasil
      } catch (err) {
        console.error("Gagal mengambil data dari API Flask:", err);
        setError("Gagal terhubung ke server backend (Port 5000). Pastikan server Flask berjalan.");
        setCoffeeShops([]);
      } finally {
        setIsLoading(false);
      }
    };
    fetchShops();
  }, []); // [] memastikan fungsi hanya dijalankan sekali

  // LOGIKA PENCARIAN (Filtering): NANTINYA akan disempurnakan untuk memfilter berdasarkan tags_llm
  const filteredShops = coffeeShops.filter(shop =>
    shop.nama.toLowerCase().includes(searchTerm.toLowerCase())
    // Di masa depan, filter bisa diperluas ke: || shop.tags_llm.some(tag => tag.includes(searchTerm.toLowerCase()))
  );


  // Tampilan Loading
  if (isLoading) {
    return (
        <div className="text-center p-16">
            <h1 className="text-3xl text-indigo-600 font-semibold">Memuat Coffee Shop Pontianak...</h1>
            <p className="mt-2 text-gray-500">Menghubungkan ke server backend...</p>
        </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      
      {/* HEADER/BANNER (Mirip Gaya Awal TripAdvisor) */}
      <div className="bg-indigo-700 h-40 flex items-center justify-center text-white mb-6 rounded-lg shadow-lg">
          <h1 className="text-4xl font-extrabold tracking-tight">Temukan Coffee Shop Terbaik di Pontianak</h1>
      </div>

      {/* Search Bar (Ditempatkan secara strategis) */}
      {/* setSearchTerm dihubungkan ke komponen SearchBar untuk memperbarui state pencarian */}
      <SearchBar setSearchTerm={setSearchTerm} />

      <main className="max-w-4xl mx-auto py-8">
        <h2 className="text-3xl font-bold text-gray-800 mb-6 border-b pb-2">Katalog Coffee Shop ({filteredShops.length} ditemukan)</h2>
        
        {/* Tampilan Error Koneksi */}
        {error && (
            <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-6">
                <strong className="font-bold">Error:</strong>
                <span className="block sm:inline"> {error}</span>
            </div>
        )}

        {/* Tampilan Daftar Katalog (Grid) */}
        {!error && filteredShops.length > 0 && (
          // Menggunakan grid untuk tata letak yang menarik (2 kolom di layar menengah/besar)
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6"> 
            {filteredShops.map((shop) => (
              // Link membungkus CoffeeShopCard untuk navigasi
              <Link key={shop.id} to={`/shop/${shop.id}`} className="block hover:shadow-2xl transition duration-300"> 
                <CoffeeShopCard shop={shop} />
              </Link>
            ))}
          </div>
        )}
        
        {/* Tampilan Jika Data Kosong/Tidak Ditemukan setelah pencarian */}
        {!error && !isLoading && filteredShops.length === 0 && searchTerm === '' && (
            <p className="text-center text-xl text-red-500 mt-10">Data Coffee Shop kosong. Pastikan data fiktif ada di app.py.</p>
        )}
        {!error && !isLoading && filteredShops.length === 0 && searchTerm !== '' && (
             <p className="text-center text-xl text-gray-500 mt-10">Tidak ada hasil ditemukan untuk "{searchTerm}".</p>
        )}
      </main>
    </div>
  );
}

export default ShopList;
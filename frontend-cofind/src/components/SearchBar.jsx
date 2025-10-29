// src/components/SearchBar.jsx
import React from 'react';

// Komponen SearchBar menerima setSearchTerm melalui props
const SearchBar = ({ setSearchTerm }) => {
  
  // Fungsi handleSubmit mencegah halaman me-reload ketika tombol submit ditekan
  const handleSubmit = (e) => {
    e.preventDefault();
  };
  
  return (
    <div className="bg-white p-6 shadow-xl rounded-2xl max-w-2xl mx-auto -mt-10 mb-8 border border-gray-100 z-20 relative">
      
      {/* Form menggunakan handleSubmit agar tidak me-reload halaman */}
      <form onSubmit={handleSubmit}>
        <div className="relative flex items-center">
          
          {/* Ikon Pencarian SVG */}
          <svg className="w-5 h-5 text-gray-400 absolute ml-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
          </svg>
          
          {/* Input Text */}
          <input
            type="text"
            placeholder="Kriteria coffee shop yang ingin dituju..."
            className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500 text-gray-700"
            
            // AKTIVASI FUNGSI PENCARIAN
            // Setiap kali nilai input berubah, setSearchTerm akan dipanggil,
            // memperbarui state searchTerm di komponen ShopList.
            onChange={(e) => setSearchTerm(e.target.value)} 
          />
        </div>
        
        {/* Tombol Submit Tersembunyi (hanya untuk fungsionalitas form) */}
        <button type="submit" className="hidden">Cari</button>
      </form>
    </div>
  );
};

export default SearchBar;
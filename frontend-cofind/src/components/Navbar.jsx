// src/components/Navbar.jsx
import React from 'react';
import { Link } from 'react-router-dom';

const Navbar = () => {
  return (
    <nav className="bg-white shadow-lg fixed w-full z-10 top-0">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          
          {/* Logo/Nama Proyek */}
          <div className="flex-shrink-0">
            <Link to="/" className="text-2xl font-bold text-indigo-700 hover:text-indigo-800">
              Cofind
            </Link>
          </div>

          {/* Navigasi (Minimalis) */}
          <div className="hidden md:block">
            <div className="ml-10 flex items-baseline space-x-4">
              <span className="text-gray-600 hover:text-indigo-600 px-3 py-2 rounded-md text-sm font-medium">
                Pontianak
              </span>
              <span className="text-gray-600 hover:text-indigo-600 px-3 py-2 rounded-md text-sm font-medium">
                Tentang Skripsi
              </span>
            </div>
          </div>

          {/* Profil/Tombol Login (Simulasi) */}
          <div className="flex items-center">
            <button className="bg-indigo-600 text-white px-4 py-1.5 rounded-full text-sm hover:bg-indigo-700 transition duration-150">
              Masuk
            </button>
          </div>

        </div>
      </div>
    </nav>
  );
};

export default Navbar;
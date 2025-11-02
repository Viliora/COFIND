// src/components/Footer.jsx
import React from 'react';

const Footer = () => {
  return (
    <footer className="bg-gray-800 text-white mt-8 sm:mt-12 pt-6 sm:pt-8 pb-4">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8 border-b border-gray-700 pb-4 sm:pb-6">
          <div>
            <h4 className="text-base sm:text-lg font-bold mb-2 sm:mb-3 text-indigo-400">Cofind Project</h4>
            <p className="text-xs sm:text-sm text-gray-400 leading-relaxed">
              Proyek Skripsi: Implementasi LLaMA pada Analisis User-Generated Content (UGC) untuk Rekomendasi Coffee Shop di Pontianak.
            </p>
          </div>
          <div>
            <h4 className="text-base sm:text-lg font-bold mb-2 sm:mb-3 text-indigo-400">Teknologi</h4>
            <ul className="space-y-1 sm:space-y-2 text-xs sm:text-sm text-gray-400">
              <li>Python (Flask, LLaMA)</li>
              <li>React, Tailwind CSS, PostgreSQL</li>
            </ul>
          </div>
          <div className="sm:col-span-2 lg:col-span-1">
            <h4 className="text-base sm:text-lg font-bold mb-2 sm:mb-3 text-indigo-400">Kontak Akademik</h4>
            <p className="text-xs sm:text-sm text-gray-400">Universitas Anda</p>
            <p className="text-xs sm:text-sm text-gray-400 break-all">Email: nama.mahasiswa@email.com</p>
          </div>
        </div>
        <div className="mt-4 sm:mt-6 text-center text-xs sm:text-sm text-gray-500">
          &copy; {new Date().getFullYear()} Cofind Project. All Rights Reserved.
        </div>
      </div>
    </footer>
  );
};

export default Footer;
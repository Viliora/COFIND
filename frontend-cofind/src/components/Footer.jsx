// src/components/Footer.jsx
import React from 'react';

const Footer = () => {
  return (
    <footer className="bg-gray-800 text-white mt-12 pt-8 pb-4">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 border-b border-gray-700 pb-6">
          <div>
            <h4 className="text-lg font-bold mb-3 text-indigo-400">Cofind Project</h4>
            <p className="text-sm text-gray-400">
              Proyek Skripsi: Implementasi LLaMA pada Analisis User-Generated Content (UGC) untuk Rekomendasi Coffee Shop di Pontianak.
            </p>
          </div>
          <div>
            <h4 className="text-lg font-bold mb-3 text-indigo-400">Teknologi</h4>
            <ul className="space-y-2 text-sm text-gray-400">
              <li>Python (Flask, LLaMA)</li>
              <li>React, Tailwind CSS, PostgreSQL</li>
            </ul>
          </div>
          <div>
            <h4 className="text-lg font-bold mb-3 text-indigo-400">Kontak Akademik</h4>
            <p className="text-sm text-gray-400">Universitas Anda</p>
            <p className="text-sm text-gray-400">Email: nama.mahasiswa@email.com</p>
          </div>
        </div>
        <div className="mt-6 text-center text-sm text-gray-500">
          &copy; {new Date().getFullYear()} Cofind Project. All Rights Reserved.
        </div>
      </div>
    </footer>
  );
};

export default Footer;
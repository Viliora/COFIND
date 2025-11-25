// src/components/Footer.jsx
import React from 'react';
import cofindImg from '../assets/cofind.svg?url';

const Footer = () => {
  return (
    <footer className="bg-gray-100 dark:bg-zinc-900 border-t border-gray-200 dark:border-zinc-800 mt-8 sm:mt-12 py-6 w-full transition-colors duration-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4">
          {/* Copyright Text */}
          <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
            <span className="font-medium">Copyright © COFIND 2025</span>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
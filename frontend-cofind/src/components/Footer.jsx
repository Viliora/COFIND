// src/components/Footer.jsx
import React from 'react';

const Footer = () => {
  return (
    <footer className="border-t border-cofind-rule bg-cofind-paper mt-8 sm:mt-12 py-6 w-full">
      <div className="max-w-cofind mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4">
          <div className="flex items-center gap-2 text-sm text-cofind-muted font-sans">
            <span className="font-medium">Copyright © COFIND 2025</span>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;

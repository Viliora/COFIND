// src/main.jsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import './index.css';
import { BrowserRouter } from 'react-router-dom'; // IMPORT INI
import { registerServiceWorker } from './utils/sw-register'; // Service Worker Registration

/**
 * ⚠️ PENTING: Error AUTOFILL BUKAN dari aplikasi ini!
 * 
 * Error "[AUTOFILL] Missing typeId or itemId from URL params" berasal dari 
 * EXTENSION BROWSER (password manager, autofill tools, dll), BUKAN dari kode aplikasi.
 * 
 * ✅ KONFIRMASI: Aplikasi ini TIDAK menggunakan typeId atau itemId di URL.
 *    Aplikasi hanya menggunakan parameter 'search' untuk pencarian.
 * 
 * ✅ ERROR INI TIDAK MEMPENGARUHI aplikasi sama sekali:
 *    - Tidak merusak fungsionalitas
 *    - Tidak memengaruhi performa
 *    - Tidak terlihat oleh pengguna akhir
 *    - Hanya muncul di console developer
 * 
 * ✅ BISA DIBIARKAN SAJA - tidak perlu diperbaiki karena bukan dari kode aplikasi.
 * 
 * Filter ini mencoba menyembunyikan error extension, tapi karena extension
 * berjalan di context terpisah, mungkin tidak 100% efektif.
 */
const isExtensionMessage = (message, source = '') => {
  if (!message) return false;
  
  const messageStr = typeof message === 'string' ? message : 
                     (message?.message || message?.toString() || '');
  const sourceStr = source || message?.filename || message?.source || message?.stack || '';
  
  // Filter semua pesan dari extension autofill (termasuk log, error, warn)
  const autofillPatterns = [
    '[AUTOFILL]',
    '[Autofill]',
    'Missing typeId or itemId',
    'typeId or itemId',
    'params from url',
    'Calling initialize',
    'Starting loadData',
    'Loading data with typeId',
    'No data loaded, skipping initialization'
  ];
  
  if (autofillPatterns.some(pattern => messageStr.includes(pattern))) {
    return true;
  }
  
  // Filter berdasarkan source file
  if (sourceStr.includes('autofill') ||
      sourceStr.includes('autofill.') ||
      sourceStr.includes('extension://') ||
      sourceStr.includes('chrome-extension://') ||
      sourceStr.includes('moz-extension://') ||
      sourceStr.includes('safari-extension://')) {
    return true;
  }
  
  // Filter error dari extension lainnya yang umum
  if (sourceStr.includes('extension') && 
      (sourceStr.includes('.js') || sourceStr.includes('.jsx'))) {
    return true;
  }
  
  return false;
};

// Global error handler untuk menyembunyikan error dari extension browser
// Menggunakan capture phase (true) untuk menangkap error sebelum extension memprosesnya
window.addEventListener('error', (event) => {
  // Cek berdasarkan message dan filename
  const message = event.message || '';
  const filename = event.filename || '';
  
  if (isExtensionMessage(message, filename) || 
      filename.includes('autofill.') ||
      filename.includes('element.b')) {
    // Sembunyikan error dari extension
    event.preventDefault();
    event.stopPropagation();
    return false;
  }
}, true);

// Handler untuk unhandled promise rejection dari extension
window.addEventListener('unhandledrejection', (event) => {
  const error = event.reason;
  const errorMessage = typeof error === 'string' ? error : error?.message || '';
  const errorStack = error?.stack || '';
  
  if (isExtensionMessage(errorMessage, errorStack)) {
    // Sembunyikan error dari extension
    event.preventDefault();
  }
});

/**
 * Override console methods untuk menyembunyikan log/error dari extension browser
 * Ini mencegah log extension mengganggu debugging aplikasi yang sebenarnya
 */
const originalConsoleError = console.error;
const originalConsoleLog = console.log;
const originalConsoleWarn = console.warn;

// Filter function untuk semua console methods
const shouldSuppressMessage = (...args) => {
  const message = args.map(arg => 
    typeof arg === 'string' ? arg : 
    (arg?.toString ? arg.toString() : JSON.stringify(arg))
  ).join(' ');
  
  // Cek berdasarkan message content
  if (isExtensionMessage(message)) {
    return true;
  }
  
  // Cek berdasarkan stack trace jika ada
  const stack = new Error().stack || '';
  if (stack.includes('autofill.') || stack.includes('element.b')) {
    return true;
  }
  
  return false;
};

// Override console.error
console.error = (...args) => {
  if (shouldSuppressMessage(...args)) {
    return; // Sembunyikan error dari extension
  }
  originalConsoleError.apply(console, args);
};

// Override console.log untuk menyembunyikan log AUTOFILL
console.log = (...args) => {
  if (shouldSuppressMessage(...args)) {
    return; // Sembunyikan log dari extension
  }
  originalConsoleLog.apply(console, args);
};

// Override console.warn untuk menyembunyikan warning dari extension
console.warn = (...args) => {
  if (shouldSuppressMessage(...args)) {
    return; // Sembunyikan warning dari extension
  }
  originalConsoleWarn.apply(console, args);
};

// Daftarkan Service Worker
registerServiceWorker();

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {/* Menggunakan BrowserRouter untuk mengaktifkan routing */}
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
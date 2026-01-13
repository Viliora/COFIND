// src/components/LLMAnalysisModal.jsx
import React, { useState, useEffect, useRef } from 'react';
import reviewsData from '../data/reviews.json';

const LLMAnalysisModal = ({ isOpen, onClose, shop, buttonRef }) => {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [position, setPosition] = useState({ 
    top: 0, 
    left: 0, 
    viewportTop: 0, 
    viewportLeft: 0 
  });
  const lastShopIdRef = useRef(null); // Track shop ID terakhir untuk reset saat shop berubah
  const progressIntervalRef = useRef(null);
  const bubbleRef = useRef(null);
  
  const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';

  const fetchLLMAnalysis = async () => {
    if (!shop || !shop.place_id) {
      setError('Data coffee shop tidak lengkap');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Ambil reviews untuk coffee shop ini
      const reviewsByPlaceId = reviewsData?.reviews_by_place_id || {};
      const shopReviews = reviewsByPlaceId[shop.place_id] || [];
      
      // Ambil beberapa review untuk dianalisis
      const reviewsText = shopReviews.slice(0, 10)
        .map(r => r.text)
        .filter(text => text && text.trim().length > 20)
        .join(' ');

      // Buat prompt untuk summary 1 kalimat murni dari review (tanpa nama coffee shop)
      const inputText = `Berdasarkan review pengunjung berikut, buat 1 kalimat ringkas (maksimal 25 kata) yang merangkum karakteristik dan kesan umum coffee shop ini. JANGAN sebutkan nama coffee shop, rating, atau alamat. Hanya fokus pada karakteristik tempat berdasarkan review. Format: "coffee shop yang [karakteristik]". Review: ${reviewsText.substring(0, 800)}. Jawab HANYA dengan 1 kalimat tanpa penjelasan tambahan.`;

      const response = await fetch(`${API_BASE}/api/llm/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text: inputText,
          task: 'summarize',
          location: 'Pontianak',
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        if (response.status === 402 || data.error_code === 'QUOTA_EXCEEDED') {
          throw new Error('Kuota token LLM telah habis. Silakan cek akun Hugging Face Anda.');
        } else if (response.status === 503) {
          throw new Error('Layanan LLM sedang tidak tersedia. Silakan coba lagi nanti.');
        } else {
          throw new Error(data.message || 'Terjadi kesalahan saat menganalisis coffee shop');
        }
      }

      setTimeout(() => {
        setAnalysis(data);
        setLoading(false);
      }, 300);
      
    } catch (err) {
      setError(err.message || 'Gagal menganalisis coffee shop');
      console.error('LLM Analysis Error:', err);
      setLoading(false);
    }
  };

  // Update position ketika modal dibuka - HANYA SEKALI saat pertama kali dibuka
  useEffect(() => {
    if (isOpen && buttonRef?.current) {
      // Simpan posisi absolut dengan menambahkan scroll offset
      // Ini memastikan posisi tetap sama meskipun halaman di-scroll
      const buttonRect = buttonRef.current.getBoundingClientRect();
      const scrollX = window.scrollX || window.pageXOffset;
      const scrollY = window.scrollY || window.pageYOffset;
      
      // Simpan posisi absolut (relatif terhadap document, bukan viewport)
      // Dengan fixed positioning, kita perlu menggunakan posisi viewport TAPI
      // kita akan update posisi ini saat scroll untuk menjaga bubble tetap di tempat yang sama
      const initialPosition = {
        top: buttonRect.top + scrollY - 10, // 10px di atas button (absolute position)
        left: buttonRect.left + scrollX + buttonRect.width / 2, // Tengah button (absolute position)
        viewportTop: buttonRect.top - 10, // Posisi viewport untuk fixed positioning
        viewportLeft: buttonRect.left + buttonRect.width / 2,
      };
      
      setPosition(initialPosition);
      
      // Fetch analysis setiap kali modal dibuka (jika shop ada)
      const currentShopId = shop?.place_id;
      if (currentShopId) {
        // Reset state sebelum fetch baru
        if (currentShopId !== lastShopIdRef.current) {
          setAnalysis(null);
          setError(null);
          lastShopIdRef.current = currentShopId;
        }
        fetchLLMAnalysis();
      }
    } else if (!isOpen) {
      // Reset state ketika modal ditutup
      setAnalysis(null);
      setError(null);
    }

    return () => {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, shop, buttonRef]);

  // State untuk z-index bubble (akan berubah saat melewati navbar)
  const [bubbleZIndex, setBubbleZIndex] = useState(40); // Default lebih rendah dari navbar

  // Update posisi saat scroll agar bubble tetap di posisi absolut yang sama
  useEffect(() => {
    if (!isOpen || !position.top || !position.left) return;

    // Dapatkan tinggi navbar secara dinamis dari DOM
    const getNavbarHeight = () => {
      const navbar = document.querySelector('nav');
      if (navbar) {
        return navbar.offsetHeight || navbar.getBoundingClientRect().height;
      }
      // Fallback: berdasarkan pt-14 sm:pt-16 di App.jsx
      return window.innerWidth >= 640 ? 64 : 56;
    };

    const handleScroll = () => {
      const scrollX = window.scrollX || window.pageXOffset;
      const scrollY = window.scrollY || window.pageYOffset;
      
      // Update posisi viewport berdasarkan posisi absolut dan scroll saat ini
      // Ini memastikan bubble tetap di posisi absolut yang sama
      const viewportTop = position.top - scrollY;
      
      setPosition(prev => ({
        ...prev,
        viewportTop: viewportTop,
        viewportLeft: prev.left - scrollX,
      }));

      // Dapatkan tinggi navbar secara dinamis
      const navbarHeight = getNavbarHeight();
      
      // Cek apakah bubble melewati navbar menggunakan posisi aktual dari DOM
      if (bubbleRef.current) {
        const bubbleRect = bubbleRef.current.getBoundingClientRect();
        // Bagian atas bubble (karena transform translate(-50%, -100%), top adalah posisi bawah)
        // Tapi getBoundingClientRect() memberikan posisi aktual setelah transform
        const bubbleTopEdge = bubbleRect.top;
        
        // Jika bagian atas bubble berada di area navbar atau di atas navbar, set z-index lebih rendah
        // Tambahkan margin 10px untuk memastikan deteksi lebih akurat
        if (bubbleTopEdge <= navbarHeight + 10) {
          // Bubble melewati navbar, set z-index lebih rendah dari navbar (z-50)
          setBubbleZIndex(40); // Di bawah navbar (z-50)
        } else {
          // Bubble tidak melewati navbar, set z-index normal
          setBubbleZIndex(60); // Di atas konten normal
        }
      } else {
        // Fallback: gunakan perhitungan estimasi jika ref belum tersedia
        const estimatedBubbleHeight = 150;
        const bubbleTopEdge = viewportTop - estimatedBubbleHeight;
        
        if (bubbleTopEdge <= navbarHeight + 10) {
          setBubbleZIndex(40);
        } else {
          setBubbleZIndex(60);
        }
      }
    };

    // Panggil sekali untuk set initial z-index
    handleScroll();

    window.addEventListener('scroll', handleScroll, { passive: true });
    window.addEventListener('resize', handleScroll, { passive: true });

    return () => {
      window.removeEventListener('scroll', handleScroll);
      window.removeEventListener('resize', handleScroll);
    };
  }, [isOpen, position.top, position.left]);

  if (!isOpen) return null;

  // Clean analysis text - remove nama coffee shop, rating, alamat jika ada
  const cleanAnalysis = (text) => {
    if (!text) return '';
    // Remove patterns like "1. **Nama**", "Rating: X.X", "Alamat:", etc.
    let cleaned = text
      .replace(/\d+\.\s*\*\*[^*]+\*\*/g, '') // Remove numbered headers
      .replace(/Rating[:\s]+\d+\.?\d*/gi, '') // Remove rating
      .replace(/Alamat[:\s]+[^\n]+/gi, '') // Remove address
      .replace(/Google Maps[:\s]+[^\n]+/gi, '') // Remove Google Maps
      .replace(/Berdasarkan Ulasan Pengunjung[:\s]*/gi, '') // Remove label
      .replace(/\[Verifikasi:[^\]]+\]/g, '') // Remove verification
      .trim();
    
    // Extract first sentence if multiple sentences
    const firstSentence = cleaned.split(/[.!?]/)[0].trim();
    return firstSentence || cleaned;
  };

  const handleBackdropClick = (e) => {
    // Tutup modal jika klik di backdrop atau di luar bubble
    e.preventDefault();
    e.stopPropagation();
    onClose();
  };

  return (
    <div 
      className="fixed inset-0" 
      onClick={handleBackdropClick}
      onMouseDown={(e) => {
        // Prevent all mouse down events from propagating
        e.preventDefault();
        e.stopPropagation();
      }}
      style={{ 
        pointerEvents: 'auto',
        zIndex: bubbleZIndex < 50 ? 30 : 50 // Backdrop juga perlu z-index yang sesuai
      }}
    >
      <div 
        ref={bubbleRef}
        className="fixed bg-white dark:bg-gray-800 rounded-lg shadow-2xl max-w-xs w-full border border-gray-200 dark:border-gray-700"
        style={{
          top: `${position.viewportTop || position.top}px`,
          left: `${position.viewportLeft || position.left}px`,
          transform: 'translate(-50%, -100%)',
          marginTop: '-8px',
          pointerEvents: 'auto',
          zIndex: bubbleZIndex
        }}
        onClick={(e) => {
          e.stopPropagation();
          e.preventDefault();
          // Jangan tutup modal jika klik di dalam bubble
        }}
        onMouseDown={(e) => {
          e.stopPropagation();
          e.preventDefault();
        }}
      >
        {/* Chat Bubble Arrow */}
        <div 
          className="absolute bottom-0 left-1/2 transform -translate-x-1/2 translate-y-full"
          style={{
            width: 0,
            height: 0,
            borderLeft: '8px solid transparent',
            borderRight: '8px solid transparent',
            borderTop: '8px solid white',
          }}
        />
        <div 
          className="absolute bottom-0 left-1/2 transform -translate-x-1/2 translate-y-full dark:hidden"
          style={{
            width: 0,
            height: 0,
            borderLeft: '8px solid transparent',
            borderRight: '8px solid transparent',
            borderTop: '8px solid white',
            marginTop: '-1px'
          }}
        />
        <div 
          className="hidden dark:block absolute bottom-0 left-1/2 transform -translate-x-1/2 translate-y-full"
          style={{
            width: 0,
            height: 0,
            borderLeft: '8px solid transparent',
            borderRight: '8px solid transparent',
            borderTop: '8px solid rgb(31 41 55)', // dark:bg-gray-800
          }}
        />

        {/* Content */}
        <div className="p-3 relative">
          {loading && (
            <div className="flex items-center justify-center gap-2 py-1">
              <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-indigo-600"></div>
              <span className="text-xs text-gray-600 dark:text-gray-400">Menganalisis...</span>
            </div>
          )}

          {error && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded p-2">
              <p className="text-xs text-red-800 dark:text-red-200">{error}</p>
            </div>
          )}

          {analysis && !loading && (
            <p className="text-xs text-gray-700 dark:text-gray-300 leading-relaxed">
              {cleanAnalysis(analysis.analysis || analysis.summary || 'Tidak ada analisis tersedia.')}
            </p>
          )}

          {!loading && !error && !analysis && (
            <div className="text-center py-1 text-xs text-gray-500 dark:text-gray-400">
              Memuat analisis...
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default LLMAnalysisModal;


// src/components/LLMAnalysisModal.jsx
import React, { useState, useEffect, useRef } from 'react';
import reviewsData from '../data/reviews.json';

const LLMAnalysisModal = ({ isOpen, onClose, shop, buttonRef }) => {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(0);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const progressIntervalRef = useRef(null);
  const bubbleRef = useRef(null);
  
  const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';

  // Update position ketika modal dibuka
  useEffect(() => {
    if (isOpen && buttonRef?.current) {
      const buttonRect = buttonRef.current.getBoundingClientRect();
      setPosition({
        top: buttonRect.top - 10, // 10px di atas button
        left: buttonRect.left + buttonRect.width / 2, // Tengah button
      });
      fetchLLMAnalysis();
    } else {
      // Reset state ketika modal ditutup
      setAnalysis(null);
      setError(null);
      setProgress(0);
    }

    return () => {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = null;
      }
    };
  }, [isOpen, shop, buttonRef]);

  const fetchLLMAnalysis = async () => {
    if (!shop || !shop.place_id) {
      setError('Data coffee shop tidak lengkap');
      return;
    }

    setLoading(true);
    setError(null);
    setProgress(0);

    // Simulasi progress bar
    const intervalTime = 100;
    progressIntervalRef.current = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 90) return prev;
        return prev + Math.random() * 10;
      });
    }, intervalTime);

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

      // Set progress ke 100% saat selesai
      setProgress(100);
      
      setTimeout(() => {
        setAnalysis(data);
        setLoading(false);
        setProgress(0);
      }, 300);
      
    } catch (err) {
      setError(err.message || 'Gagal menganalisis coffee shop');
      console.error('LLM Analysis Error:', err);
      setLoading(false);
      setProgress(0);
    } finally {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = null;
      }
    }
  };

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
      className="fixed inset-0 z-50" 
      onClick={handleBackdropClick}
      onMouseDown={(e) => {
        // Prevent all mouse down events from propagating
        e.preventDefault();
        e.stopPropagation();
      }}
      style={{ pointerEvents: 'auto' }}
    >
      <div 
        ref={bubbleRef}
        className="absolute bg-white dark:bg-gray-800 rounded-lg shadow-2xl max-w-xs w-full border border-gray-200 dark:border-gray-700 z-[60]"
        style={{
          top: `${position.top}px`,
          left: `${position.left}px`,
          transform: 'translate(-50%, -100%)',
          marginTop: '-8px',
          pointerEvents: 'auto'
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


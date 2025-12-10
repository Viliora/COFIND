import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import reviewsData from '../data/reviews.json';

const LLMAnalyzer = () => {
  const [input, setInput] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(0);

  const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';
  const FIXED_LOCATION = 'Pontianak'; // Lokasi fixed, tidak bisa diubah user
  const FIXED_TASK = 'recommend'; // Task fixed: hanya rekomendasi
  
  const progressIntervalRef = useRef(null);

  // Function untuk capitalize each word
  const capitalizeWords = (str) => {
    if (!str) return '';
    return str.replace(/\b\w/g, (char) => char.toUpperCase());
  };

  // Function untuk parse coffee shops dari response LLM
  const parseCoffeeShops = (text) => {
    if (!text) return [];
    
    // Cek jika backend mengembalikan pesan "tidak ada coffee shop"
    if (text.toLowerCase().includes('maaf') && text.toLowerCase().includes('tidak ada coffee shop')) {
      return [];
    }

    // Split berdasarkan pattern nomor (1., 2., 3., dst) diikuti dengan **Nama**
    const shopPattern = /(\d+)\.\s*\*\*([^*]+)\*\*/g;
    const matches = [...text.matchAll(shopPattern)];
    
    if (matches.length === 0) return [];

    const shops = [];
    
    matches.forEach((match, index) => {
      const number = match[1];
      const name = match[2].trim();
      const startIndex = match.index;
      const endIndex = index < matches.length - 1 ? matches[index + 1].index : text.length;
      const content = text.substring(startIndex, endIndex).trim();
      
      // Extract rating (format: Rating: X.X atau Rating X.X)
      const ratingMatch = content.match(/Rating[:\s]+(\d+\.?\d*)/i);
      const rating = ratingMatch ? ratingMatch[1] : null;
      
      // Extract review text (cari "Berdasarkan Ulasan Pengunjung:" atau ambil semua setelah rating)
      let reviewText = '';
      const reviewMatch = content.match(/Berdasarkan Ulasan Pengunjung:\s*(.+?)(?=\n\n|\[Verifikasi:|$)/is);
      if (reviewMatch) {
        reviewText = reviewMatch[1].trim();
      } else {
        // Fallback: ambil semua teks setelah rating
        const afterRating = content.split(/Rating[:\s]+\d+\.?\d*/i)[1];
        if (afterRating) {
          reviewText = afterRating
            .replace(/Alamat[:\s]+[^\n]+/gi, '') // Remove alamat
            .replace(/\[Verifikasi:[^\]]+\]/g, '') // Remove verifikasi
            .replace(/Berdasarkan Ulasan Pengunjung:/gi, '') // Remove label
            .trim();
        }
      }
      
      // Clean emoji dari review text
      // eslint-disable-next-line no-misleading-character-class
      reviewText = reviewText.replace(/[🏆📍📝🗺️⭐]/gu, '').trim();
      
      // Extract verification link
      const verifyMatch = content.match(/\[Verifikasi:\s*(https?:\/\/[^\]]+)\]/);
      const verifyLink = verifyMatch ? verifyMatch[1] : null;
      
      // Extract alamat jika ada
      const addressMatch = content.match(/Alamat:\s*([^\n]+)/i);
      let address = addressMatch ? addressMatch[1].trim() : null;
      
      // Extract Google Maps URL jika ada
      const mapsMatch = content.match(/Google Maps:\s*(https?:\/\/[^\s\n]+)/i);
      const mapsUrl = mapsMatch ? mapsMatch[1] : null;
      
      // Try to get place_id dari Google Maps URL atau dari localStorage
      let placeId = null;
      if (mapsUrl && mapsUrl.includes('place_id:')) {
        const placeIdMatch = mapsUrl.match(/place_id:([A-Za-z0-9_-]+)/);
        if (placeIdMatch) {
          placeId = placeIdMatch[1];
        }
      }
      
      // Fallback: cari di localStorage berdasarkan nama
      if (!placeId) {
        try {
          const cachedShops = localStorage.getItem('coffeeShops');
          if (cachedShops) {
            const shops = JSON.parse(cachedShops);
            const foundShop = shops.find(s => 
              s.name && name && s.name.toLowerCase().includes(name.toLowerCase())
            );
            if (foundShop) {
              placeId = foundShop.place_id;
              // Jika address belum ada, ambil dari localStorage
              if (!address && foundShop.address) {
                address = foundShop.address;
              }
            }
          }
        } catch (e) {
          console.error('Error finding place_id from localStorage:', e);
        }
      }
      
      shops.push({
        number,
        name,
        rating,
        reviewText, // Review dari LLM (untuk referensi, tapi tidak ditampilkan)
        verifyLink,
        placeId,
        mapsUrl,
        address
      });
    });
    
    // Batasi maksimal 3 coffee shop
    return shops.slice(0, 3);
  };

  // Function untuk render text dengan markdown bold dan clickable URL
  const renderTextWithBold = (text) => {
    if (!text) return null;
    
    // Split by **word** pattern untuk bold, URL pattern untuk links, dan [Verifikasi: URL] pattern
    // Regex: (\*\*[^*]+\*\*) untuk bold, (\[Verifikasi: https?://[^\]]+\]) untuk verifikasi link, (https?://[^\s\]]+) untuk URL biasa
    const parts = text.split(/(\*\*[^*]+\*\*|\[Verifikasi: https?:\/\/[^\]]+\]|https?:\/\/[^\s\]]+)/g);
    
    return parts.map((part, index) => {
      // Check jika part adalah bold (diapit **)
      if (part.startsWith('**') && part.endsWith('**')) {
        const boldText = part.slice(2, -2); // Remove ** dari kedua sisi
        return (
          <strong key={index} className="font-bold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-900/30 px-1 rounded">
            {boldText}
          </strong>
        );
      }
      // Check jika part adalah [Verifikasi: URL]
      if (part.startsWith('[Verifikasi:') && part.endsWith(']')) {
        const url = part.match(/https?:\/\/[^\]]+/)?.[0];
        if (url) {
          return (
            <a 
              key={index} 
              href={url} 
              target="_blank" 
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 px-2 py-0.5 rounded-full hover:bg-green-200 dark:hover:bg-green-900/50 transition-colors duration-200 ml-1"
              title="Klik untuk verifikasi review asli di Google Maps"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
              </svg>
              Verifikasi
            </a>
          );
        }
      }
      // Check jika part adalah URL biasa (http atau https)
      if (part.match(/^https?:\/\/[^\s\]]+$/)) {
        return (
          <a 
            key={index} 
            href={part} 
            target="_blank" 
            rel="noopener noreferrer"
            className="text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 underline font-medium transition-colors duration-200"
          >
            {part}
          </a>
        );
      }
      return <span key={index}>{part}</span>;
    });
  };

  const handleAnalyze = async () => {
    if (!input.trim()) {
      setError('Silakan masukkan preferensi coffee shop Anda');
      return;
    }

    // Validasi panjang input (maksimal 100 karakter)
    if (input.length > 100) {
      setError('Input maksimal 100 karakter. Silakan perpendek kalimat Anda.');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    setProgress(0);

    // Simulasi progress bar (estimasi 20 detik untuk LLM response)
    const totalDuration = 20000; // 20 detik
    const intervalTime = 100; // Update setiap 100ms
    const incrementPerInterval = (100 / (totalDuration / intervalTime));
    
    progressIntervalRef.current = setInterval(() => {
      setProgress(prev => {
        const newProgress = prev + incrementPerInterval;
        // Cap at 95% sampai response benar-benar selesai
        return newProgress >= 95 ? 95 : newProgress;
      });
    }, intervalTime);

    try {
      const response = await fetch(`${API_BASE}/api/llm/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text: input,
          task: FIXED_TASK,
          location: FIXED_LOCATION,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || 'Terjadi kesalahan');
      }

      // Set progress ke 100% saat selesai
      setProgress(100);
      
      // Delay sedikit untuk menampilkan 100% sebelum menghilangkan loading
      setTimeout(() => {
        setResult(data);
        setLoading(false);
        setProgress(0);
      }, 300);
      
    } catch (err) {
      setError(err.message || 'Gagal menganalisis teks');
      console.error('LLM Error:', err);
      setLoading(false);
      setProgress(0);
    } finally {
      // Clear interval
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = null;
      }
    }
  };
  
  // Cleanup interval on unmount
  useEffect(() => {
    return () => {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
      }
    };
  }, []);

  const handleClear = () => {
    setInput('');
    setResult(null);
    setError(null);
  };

  // Quick recommendation fields
  const recommendationFields = [
    { label: '🛋️ Cozy', value: 'cozy' },
    { label: '📚 Belajar', value: 'belajar' },
    { label: '📶 WiFi', value: 'wifi stabil' },
    { label: '🔌 Stopkontak', value: 'stopkontak' },
    { label: '🕌 Musholla', value: 'musholla' },
    { label: '🛋️ Sofa', value: 'sofa' },
    { label: '❄️ Dingin', value: 'dingin' },
    { label: '📸 Aesthetic', value: 'aesthetic' },
    { label: '🎵 Live Music', value: 'live music' },
    { label: '🅿️ Parkir Luas', value: 'parkiran luas' },
    { label: '🌙 24 jam', value: '24 jam' },
  ];

  // Handle field click - append to input (dengan batasan 100 karakter)
  const handleFieldClick = (fieldValue) => {
    let newInput = '';
    if (input.trim()) {
      // Jika sudah ada input, tambahkan dengan koma
      newInput = input + ', ' + fieldValue;
    } else {
      // Jika kosong, langsung set
      newInput = fieldValue;
    }
    
    // Batasi maksimal 100 karakter
    if (newInput.length > 100) {
      setError(`Input maksimal 100 karakter. Tidak bisa menambahkan "${fieldValue}"`);
      return;
    }
    
    setInput(newInput);
    setError(null); // Clear error jika berhasil
  };

  return (
    <div className="w-full max-w-2xl mx-auto p-4 sm:p-6">
      <div className="bg-white dark:bg-zinc-800 rounded-xl shadow-lg border border-gray-200 dark:border-zinc-700 p-6">
        {/* Header */}
        <div className="mb-6">
          <h2 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white mb-2">
            ☕ Rekomendasi Coffee Shop AI
          </h2>
          <p className="text-gray-600 dark:text-gray-400 text-sm">
            Jelaskan preferensi Anda, dan AI akan memberikan rekomendasi coffee shop terbaik di <span className="font-semibold text-indigo-600 dark:text-indigo-400">Pontianak</span> <span className="font-semibold text-green-600 dark:text-green-400">berdasarkan ulasan pengunjung yang relevan</span> (nama + komentar asli)
          </p>
        </div>

        {/* Quick Recommendation Fields */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-900 dark:text-white mb-3">
            ⚡ Rekomendasi Cepat - Klik untuk menambahkan:
          </label>
          <div className="flex flex-wrap gap-2 mb-4 p-4 bg-gradient-to-br from-indigo-50 to-purple-50 dark:from-indigo-900/20 dark:to-purple-900/20 rounded-lg border border-indigo-200 dark:border-indigo-800">
            {recommendationFields.map((field, index) => (
              <button
                key={index}
                onClick={() => handleFieldClick(field.value)}
                className="px-3 py-1.5 bg-white dark:bg-zinc-700 hover:bg-indigo-100 dark:hover:bg-indigo-800 text-gray-700 dark:text-gray-200 text-xs sm:text-sm font-medium rounded-full border border-gray-300 dark:border-zinc-600 hover:border-indigo-400 dark:hover:border-indigo-500 transition-all duration-200 shadow-sm hover:shadow-md transform hover:scale-105"
              >
                {field.label}
              </button>
            ))}
          </div>
        </div>

        {/* Input Area - Natural Language atau Keywords */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
            💬 Jelaskan Preferensi Anda (Bahasa Indonesia):
          </label>
          <div className="relative">
            <textarea
              value={input}
              onChange={(e) => {
                // Batasi input maksimal 100 karakter
                const newValue = e.target.value.slice(0, 100);
                setInput(newValue);
                // Clear error jika user mulai mengetik lagi
                if (error && error.includes('100 karakter')) {
                  setError(null);
                }
              }}
              placeholder="Contoh: 'Saya ingin coffee shop yang cozy dengan wifi kencang dan cocok untuk kerja' atau 'wifi bagus, terminal banyak, cozy'"
              maxLength={100}
              className={`w-full p-4 border rounded-lg bg-white dark:bg-zinc-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-indigo-600 focus:border-transparent outline-none resize-none h-24 sm:h-28 ${
                input.length >= 100 
                  ? 'border-amber-500 dark:border-amber-600' 
                  : 'border-gray-300 dark:border-zinc-600'
              }`}
            />
            {/* Character Counter */}
            <div className={`absolute bottom-2 right-2 text-xs px-2 py-1 rounded font-medium ${
              input.length >= 100 
                ? 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20' 
                : input.length >= 80
                ? 'text-orange-500 dark:text-orange-400 bg-orange-50 dark:bg-orange-900/20'
                : 'text-gray-500 dark:text-gray-400 bg-white dark:bg-zinc-700'
            }`}>
              {input.length}/100
            </div>
          </div>
          <div className="mt-2 flex items-start gap-2 text-xs text-gray-600 dark:text-gray-400">
            <span className="flex-shrink-0">💡</span>
            <div className="space-y-1">
              <p className="font-medium">Tips: Gunakan bahasa Indonesia natural atau kata kunci dipisah koma</p>
              <p className="text-gray-500 dark:text-gray-500">• Contoh kalimat: "Saya ingin tempat yang cozy dengan wifi kencang"</p>
              <p className="text-gray-500 dark:text-gray-500">• Contoh keywords: "wifi bagus, terminal banyak, cozy"</p>
              <p className="text-gray-500 dark:text-gray-500">• Atau klik tombol rekomendasi cepat di atas</p>
            </div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-red-700 dark:text-red-300 text-sm">
              ❌ {error}
            </p>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-3 mb-6">
          <button
            onClick={handleAnalyze}
            disabled={loading || !input.trim()}
            className="relative flex-1 px-6 py-3 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors duration-200 flex items-center justify-center gap-2 shadow-md hover:shadow-lg overflow-hidden"
          >
            {/* Progress Bar Background */}
            {loading && (
              <div 
                className="absolute inset-0 bg-indigo-800 transition-all duration-300 ease-out"
                style={{ width: `${progress}%` }}
              ></div>
            )}
            
            {/* Button Content */}
            <div className="relative z-10 flex items-center gap-2">
              {loading ? (
                <>
                  {/* Spinner SVG Animation */}
                  <svg 
                    className="animate-spin h-5 w-5 text-white" 
                    xmlns="http://www.w3.org/2000/svg" 
                    fill="none" 
                    viewBox="0 0 24 24"
                  >
                    <circle 
                      className="opacity-25" 
                      cx="12" 
                      cy="12" 
                      r="10" 
                      stroke="currentColor" 
                      strokeWidth="4"
                    ></circle>
                    <path 
                      className="opacity-75" 
                      fill="currentColor" 
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    ></path>
                  </svg>
                  <span className="font-bold">{Math.round(progress)}%</span>
                  <span className="hidden sm:inline">- Menganalisis...</span>
                </>
              ) : (
                <>
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                  </svg>
                  <span>Dapatkan Rekomendasi</span>
                </>
              )}
            </div>
          </button>
          <button
            onClick={handleClear}
            className="px-6 py-3 bg-gray-300 dark:bg-zinc-600 hover:bg-gray-400 dark:hover:bg-zinc-500 text-gray-900 dark:text-white font-semibold rounded-lg transition-colors duration-200"
          >
            🗑️ Hapus
          </button>
        </div>

        {/* Result Display */}
        {result && (
          <div className="mt-6 space-y-4">
            {/* Header */}
            <div className="bg-gradient-to-r from-indigo-50 to-purple-50 dark:from-indigo-900/20 dark:to-purple-900/20 p-5 rounded-xl border border-indigo-200 dark:border-indigo-800 shadow-md">
              <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-3">
                Rekomendasi Coffee Shop untuk Anda
              </h3>
              <div className="flex flex-wrap items-center gap-2 text-xs mb-3">
                <span className="px-3 py-1 bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 rounded-full font-medium">
                  Pontianak
                </span>
                <span className="px-3 py-1 bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 rounded-full font-semibold">
                  Berdasarkan Ulasan Pengunjung
                </span>
              </div>
              <p className="text-sm text-gray-700 dark:text-gray-300 bg-white dark:bg-zinc-800/50 p-3 rounded-lg">
                <span className="font-semibold">Preferensi Anda:</span>{' '}
                <span className="italic">
                  {result.input}
                </span>
              </p>
            </div>

            {/* Coffee Shop Cards */}
            {(() => {
              const shops = parseCoffeeShops(result.analysis);
              
              // Parse kata kunci dari input user untuk filter
              const userInput = result?.input || '';
              const keywords = userInput
                .split(',')
                .map(kw => kw.trim().toLowerCase())
                .filter(kw => kw.length > 0);
              
              // Helper function untuk cek apakah shop memiliki review relevan
              const hasRelevantReview = (shop) => {
                const reviewsByPlaceId = reviewsData?.reviews_by_place_id || {};
                const shopReviews = shop.placeId ? reviewsByPlaceId[shop.placeId] : [];
                
                if (!shopReviews || shopReviews.length === 0) {
                  return false;
                }
                
                // Filter review yang relevan dengan keywords
                const relevantReviews = shopReviews.filter(review => {
                  const reviewText = (review?.text || '').toLowerCase();
                  if (reviewText.trim().length < 20) {
                    return false;
                  }
                  
                  // Jika ada keywords, cek apakah review mengandung minimal salah satu keyword
                  // Termasuk expanded keywords (sinonim) untuk matching yang lebih baik
                  if (keywords.length > 0) {
                    return keywords.some(keyword => {
                      if (keyword.length >= 3) {
                        const keywordLower = keyword.toLowerCase().trim();
                        // Cek substring match (termasuk untuk multi-word keywords seperti "live music")
                        // Contoh: "live music" akan match dengan "live music-nya", "live music", "musik", dll
                        return reviewText.includes(keywordLower);
                      }
                      return false;
                    });
                  }
                  
                  // Jika tidak ada keywords, anggap relevan (untuk safety)
                  return true;
                });
                
                return relevantReviews.length > 0;
              };
              
              // Filter shops: hanya tampilkan yang memiliki review relevan
              const shopsWithRelevantReviews = shops.filter(shop => hasRelevantReview(shop));
              
              if (shopsWithRelevantReviews.length > 0) {
                return (
                  <div className="space-y-4">
                    {shopsWithRelevantReviews.map((shop, index) => (
                      <div 
                        key={index}
                        className="bg-white dark:bg-zinc-800 p-6 rounded-xl border-2 border-gray-200 dark:border-zinc-700 shadow-lg hover:shadow-xl transition-shadow duration-300"
                      >
                        {/* Shop Name - Capitalize, Bold, Link */}
                        <div className="mb-4">
                          {shop.placeId ? (
                            <Link 
                              to={`/shop/${shop.placeId}`}
                              className="text-2xl font-bold text-gray-900 dark:text-white hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors"
                            >
                              {capitalizeWords(shop.name)}
                            </Link>
                          ) : (
                            <h4 className="text-2xl font-bold text-gray-900 dark:text-white">
                              {capitalizeWords(shop.name)}
                            </h4>
                          )}
                        </div>

                        {/* Rating Badge */}
                        {shop.rating && (
                          <div className="mb-4">
                            <div className="inline-flex items-center gap-2 px-4 py-2 bg-amber-50 dark:bg-amber-900/20 border-2 border-amber-200 dark:border-amber-800 rounded-lg">
                              <svg className="w-6 h-6 text-amber-500" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"></path>
                              </svg>
                              <span className="font-bold text-gray-900 dark:text-white text-xl">{shop.rating}</span>
                            </div>
                          </div>
                        )}


                        {/* Review Text - Ambil dari reviews.json berdasarkan place_id */}
                        {(() => {
                          // Ambil review dari reviews.json berdasarkan place_id
                          const reviewsByPlaceId = reviewsData?.reviews_by_place_id || {};
                          const shopReviews = shop.placeId ? reviewsByPlaceId[shop.placeId] : [];
                          
                          // Parse kata kunci dari input user
                          const userInput = result?.input || '';
                          const keywords = userInput
                            .split(',')
                            .map(kw => kw.trim().toLowerCase())
                            .filter(kw => kw.length > 0);
                          
                          // Filter review yang sesuai konteks berdasarkan kata kunci
                          // Prioritas 1: Review yang relevan dengan keywords
                          const relevantReviews = shopReviews?.filter(review => {
                            const reviewText = (review?.text || '').toLowerCase();
                            // Filter review yang memiliki teks minimal 20 karakter
                            if (reviewText.trim().length < 20) {
                              return false;
                            }
                            
                            // Jika ada kata kunci, cek apakah review mengandung minimal salah satu kata kunci
                            if (keywords.length > 0) {
                              return keywords.some(keyword => {
                                // Cek kata kunci yang panjangnya minimal 3 karakter untuk menghindari false positive
                                if (keyword.length >= 3) {
                                  return reviewText.includes(keyword);
                                }
                                return false;
                              });
                            }
                            
                            // Jika tidak ada kata kunci, return true (tampilkan semua review yang valid)
                            return true;
                          }) || [];
                          
                          // HANYA tampilkan review yang relevan dengan keywords
                          // JANGAN tampilkan review yang tidak relevan sebagai fallback
                          let displayReviews = relevantReviews.slice(0, 2);
                          
                          // WAJIB tampilkan review HANYA jika ada review yang relevan dengan keywords
                          if (displayReviews.length > 0) {
                            return (
                              <div className="space-y-2 mb-4">
                                <p className="text-sm font-bold text-gray-700 dark:text-gray-300">
                                  Berdasarkan Ulasan Pengunjung:
                                </p>
                                <div className="space-y-3">
                                  {displayReviews.map((review, reviewIdx) => {
                                    // Ambil data review PERSIS dari reviews.json - tidak diubah
                                    const reviewText = review.text || '';
                                    const authorName = review.author_name || 'Anonim';
                                    const reviewRating = review.rating || 0;
                                    
                                    return (
                                      <div key={reviewIdx} className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed bg-gray-50 dark:bg-zinc-700/50 p-3 rounded-lg">
                                        <div className="mb-2">
                                          {/* Tampilkan review text PERSIS dari reviews.json tanpa modifikasi */}
                                          {reviewText}
                                        </div>
                                        <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                                          <span className="font-medium">— {authorName}</span>
                                          <span className="flex items-center gap-1">
                                            <svg className="w-4 h-4 text-amber-500" fill="currentColor" viewBox="0 0 20 20">
                                              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"></path>
                                            </svg>
                                            {reviewRating}
                                          </span>
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            );
                          }
                          return null;
                        })()}

                        {/* Action Buttons */}
                        <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-gray-200 dark:border-zinc-700">
                          {/* Button ke Profile Coffee Shop */}
                          {shop.placeId && (
                            <a
                              href={`/shop/${shop.placeId}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors duration-200 font-medium text-sm shadow-sm hover:shadow-md"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                              </svg>
                              <span>Lihat Detail</span>
                              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
                              </svg>
                            </a>
                          )}
                          
                          {/* Button ke Google Maps */}
                          {shop.mapsUrl && (
                            <a
                              href={shop.mapsUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors duration-200 font-medium text-sm shadow-sm hover:shadow-md"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
                              </svg>
                              <span>Buka di Maps</span>
                              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
                              </svg>
                            </a>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                );
              }
              
              // Jika tidak ada shops dengan review relevan, tampilkan pesan
              if (shops.length > 0 && shopsWithRelevantReviews.length === 0) {
                return (
                  <div className="bg-yellow-50 dark:bg-yellow-900/20 border-2 border-yellow-200 dark:border-yellow-800 p-6 rounded-xl shadow-md">
                    <div className="flex items-start gap-3">
                      <svg className="w-6 h-6 text-yellow-600 dark:text-yellow-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                      </svg>
                      <div className="flex-1">
                        <h4 className="text-lg font-bold text-yellow-800 dark:text-yellow-300 mb-2">
                          Tidak Ada Coffee Shop yang Sesuai
                        </h4>
                        <p className="text-yellow-700 dark:text-yellow-400 leading-relaxed">
                          Maaf, tidak ada coffee shop yang memiliki ulasan pengunjung yang relevan dengan preferensi Anda: <span className="font-semibold italic">"{userInput}"</span>
                        </p>
                        <p className="text-sm text-yellow-600 dark:text-yellow-500 mt-3">
                          💡 <strong>Tips:</strong> Coba gunakan kata kunci yang lebih umum atau cek kembali preferensi Anda.
                        </p>
                      </div>
                    </div>
                  </div>
                );
              }
              
              // Fallback: tampilkan teks biasa jika parsing gagal
              return (
                <div className="bg-white dark:bg-zinc-800 p-5 rounded-xl border border-gray-200 dark:border-zinc-700 shadow-sm">
                  <div className="text-gray-800 dark:text-gray-200 leading-relaxed whitespace-pre-wrap text-base">
                    {result.analysis ? renderTextWithBold(result.analysis) : 'Tidak ada hasil rekomendasi'}
                  </div>
                </div>
              );
            })()}

            {/* Info Footer */}
            <div className="flex items-center justify-end text-xs text-gray-500 dark:text-gray-400 px-2">
              <span>{new Date(result.timestamp * 1000).toLocaleTimeString('id-ID')}</span>
            </div>
          </div>
        )}

        {/* Loading Spinner */}
        {loading && (
          <div className="mt-6 flex justify-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
          </div>
        )}

        {/* Tips */}
        <div className="mt-6 p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
          <h4 className="font-semibold text-amber-900 dark:text-amber-300 mb-2 flex items-center gap-2">
            <span>💡</span>
            Tips Kata Kunci yang Efektif:
          </h4>
          <ul className="text-sm text-amber-800 dark:text-amber-400 space-y-2">
            <li className="flex items-start gap-2">
              <span className="mt-0.5">✓</span>
              <span><strong>Fasilitas:</strong> wifi bagus, terminal banyak, colokan, AC.</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-0.5">✓</span>
              <span><strong>Suasana:</strong> cozy, tenang, ramai.</span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default LLMAnalyzer;

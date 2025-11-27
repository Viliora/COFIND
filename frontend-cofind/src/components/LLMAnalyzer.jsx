import React, { useState } from 'react';

const LLMAnalyzer = () => {
  const [input, setInput] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';
  const FIXED_LOCATION = 'Pontianak'; // Lokasi fixed, tidak bisa diubah user
  const FIXED_TASK = 'recommend'; // Task fixed: hanya rekomendasi

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

    setLoading(true);
    setError(null);
    setResult(null);

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

      setResult(data);
    } catch (err) {
      setError(err.message || 'Gagal menganalisis teks');
      console.error('LLM Error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setInput('');
    setResult(null);
    setError(null);
  };

  // Quick recommendation fields
  const recommendationFields = [
    { label: '🛋️ Cozy', value: 'cozy' },
    { label: '📚 Ruang Belajar', value: 'ruang belajar, tenang, fokus' },
    { label: '📶 WiFi', value: 'wifi bagus, internet cepat' },
    { label: '🔌 Stopkontak', value: 'terminal banyak, colokan' },
    { label: '🕌 Musholla', value: 'musholla, tempat ibadah' },
    { label: '🛋️ Sofa', value: 'kursi sofa, nyaman' },
    { label: '❄️ AC Dingin', value: 'AC dingin, sejuk' },
    { label: '📸 Aesthetic', value: 'aesthetic, instagramable, bagus untuk foto' },
    { label: '🤫 Tenang', value: 'tenang, sepi, tidak ramai' },
    { label: '🎵 Live Music', value: 'live music, musik' },
    { label: '🌳 Outdoor', value: 'outdoor seating, taman' },
    { label: '💰 Harga Terjangkau', value: 'harga terjangkau, murah, affordable' },
    { label: '🚬 Smoking Area', value: 'indoor smoking area, boleh merokok' },
    { label: '🐕 Pet Friendly', value: 'pet friendly, boleh bawa hewan' },
    { label: '🍰 Menu Lengkap', value: 'makan dan minum, makanan berat' },
    { label: '☕ Kopi Enak', value: 'kopi enak, kualitas kopi bagus' },
    { label: '🅿️ Parkir Luas', value: 'parkir luas, mudah parkir' },
    { label: '🌙 24 jam', value: 'buka malam, 24 jam' },
  ];

  // Handle field click - append to input
  const handleFieldClick = (fieldValue) => {
    if (input.trim()) {
      // Jika sudah ada input, tambahkan dengan koma
      setInput(prev => prev + ', ' + fieldValue);
    } else {
      // Jika kosong, langsung set
      setInput(fieldValue);
    }
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

        {/* Input Area - Keywords */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
            🏷️ Kata Kunci Preferensi (pisahkan dengan koma):
          </label>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Klik tombol di atas atau ketik manual: wifi bagus, terminal banyak, cozy, tenang, harga murah, dll."
            className="w-full p-4 border border-gray-300 dark:border-zinc-600 rounded-lg bg-white dark:bg-zinc-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-indigo-600 focus:border-transparent outline-none resize-none h-24 sm:h-28"
          />
          <div className="mt-2 flex items-start gap-2 text-xs text-gray-600 dark:text-gray-400">
            <span className="flex-shrink-0">💡</span>
            <div className="space-y-1">
              <p className="font-medium">Tips: Klik tombol rekomendasi di atas atau ketik manual</p>
              <p className="text-gray-500 dark:text-gray-500">• Kata yang match akan ditampilkan dengan <strong className="font-bold text-gray-700 dark:text-gray-300">bold</strong> di hasil</p>
              <p className="text-gray-500 dark:text-gray-500">• Anda bisa klik beberapa tombol sekaligus untuk kombinasi preferensi</p>
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
            className="flex-1 px-6 py-3 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors duration-200 flex items-center justify-center gap-2 shadow-md hover:shadow-lg"
          >
            {loading ? (
              <>
                <span className="animate-spin">⏳</span>
                Mencari Rekomendasi...
              </>
            ) : (
              <>
                <span>🎯</span>
                Dapatkan Rekomendasi
              </>
            )}
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
          <div className="mt-6 p-6 bg-gradient-to-br from-green-50 to-blue-50 dark:from-green-900/20 dark:to-blue-900/20 border-2 border-green-200 dark:border-green-800 rounded-xl shadow-lg">
            <div className="mb-4">
              <h3 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2 mb-3">
                <span>🎯</span>
                Rekomendasi Coffee Shop untuk Anda
              </h3>
              <div className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400 mb-4 pb-3 border-b border-gray-300 dark:border-gray-600">
                <span className="px-2 py-1 bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 rounded-full font-medium">
                  📍 Pontianak
                </span>
                <span className="px-2 py-1 bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 rounded-full font-medium">
                  ✓ Berdasarkan Ulasan Pengunjung
                </span>
              </div>
              <p className="text-sm text-gray-700 dark:text-gray-300 italic bg-gray-50 dark:bg-zinc-800/50 p-3 rounded-lg">
                <span className="font-semibold">Preferensi Anda:</span> {result.input}
              </p>
            </div>

            {/* Analysis Result with Review Evidence & Bold Keywords */}
            <div className="bg-white dark:bg-zinc-800 p-5 rounded-lg border border-gray-200 dark:border-zinc-700 shadow-sm">
              <div className="text-gray-800 dark:text-gray-200 leading-relaxed whitespace-pre-wrap text-base">
                {result.analysis ? renderTextWithBold(result.analysis) : 'Tidak ada hasil rekomendasi'}
              </div>
            </div>

            {/* Info Footer */}
            <div className="mt-4 flex items-center justify-between text-xs">
              <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
                <span>🤖</span>
                <span>Dianalisis oleh AI dengan data real-time dari Google Places</span>
              </div>
              <p className="text-gray-500 dark:text-gray-500">
                {new Date(result.timestamp * 1000).toLocaleTimeString('id-ID')}
              </p>
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
              <span><strong>Fasilitas:</strong> wifi bagus, terminal banyak, colokan, AC, kipas angin</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-0.5">✓</span>
              <span><strong>Suasana:</strong> cozy, tenang, ramai, aesthetic, instagramable</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-0.5">✓</span>
              <span><strong>Khusus:</strong> indoor smoking area, outdoor seating, live music, pet friendly</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-0.5">✓</span>
              <span><strong>Harga:</strong> harga terjangkau, murah, affordable, mahal</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-0.5">✓</span>
              <span>Kata kunci yang <strong className="text-indigo-600 dark:text-indigo-400">match</strong> akan ditampilkan <strong>bold</strong> di hasil! 🎯</span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default LLMAnalyzer;

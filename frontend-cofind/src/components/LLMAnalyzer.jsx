import React, { useState } from 'react';

const LLMAnalyzer = () => {
  const [input, setInput] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';
  const FIXED_LOCATION = 'Pontianak'; // Lokasi fixed, tidak bisa diubah user
  const FIXED_TASK = 'recommend'; // Task fixed: hanya rekomendasi

  // Function untuk render text dengan markdown bold
  const renderTextWithBold = (text) => {
    if (!text) return null;
    
    // Split by **word** pattern untuk bold
    const parts = text.split(/(\*\*[^*]+\*\*)/g);
    
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

  return (
    <div className="w-full max-w-2xl mx-auto p-4 sm:p-6">
      <div className="bg-white dark:bg-zinc-800 rounded-xl shadow-lg border border-gray-200 dark:border-zinc-700 p-6">
        {/* Header */}
        <div className="mb-6">
          <h2 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white mb-2">
            ☕ Rekomendasi Coffee Shop AI
          </h2>
          <p className="text-gray-600 dark:text-gray-400 text-sm">
            Jelaskan preferensi Anda, dan AI akan memberikan rekomendasi coffee shop terbaik di <span className="font-semibold text-indigo-600 dark:text-indigo-400">Pontianak</span> dengan <span className="font-semibold text-green-600 dark:text-green-400">bukti lengkap dari review pengunjung</span> (nama + komentar asli)
          </p>
        </div>

        {/* Input Area - Keywords */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
            🏷️ Kata Kunci Preferensi (pisahkan dengan koma):
          </label>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="wifi bagus, terminal banyak, cozy, tenang, harga murah, dll."
            className="w-full p-4 border border-gray-300 dark:border-zinc-600 rounded-lg bg-white dark:bg-zinc-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-indigo-600 focus:border-transparent outline-none resize-none h-24 sm:h-28"
          />
          <div className="mt-2 flex items-start gap-2 text-xs text-gray-600 dark:text-gray-400">
            <span className="flex-shrink-0">💡</span>
            <div className="space-y-1">
              <p className="font-medium">Masukkan kata kunci yang Anda cari, dipisah koma:</p>
              <p className="text-gray-500 dark:text-gray-500">• <span className="italic">wifi bagus, terminal banyak, cozy</span></p>
              <p className="text-gray-500 dark:text-gray-500">• Kata yang match akan ditampilkan dengan <strong className="font-bold text-gray-700 dark:text-gray-300">bold</strong> di hasil</p>
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
                  ✓ Dengan Bukti Review
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

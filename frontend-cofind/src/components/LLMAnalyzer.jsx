import React, { useState } from 'react';

const LLMAnalyzer = () => {
  const [input, setInput] = useState('');
  const [task, setTask] = useState('analyze'); // analyze, summarize, recommend
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';

  const handleAnalyze = async () => {
    if (!input.trim()) {
      setError('Silakan masukkan teks untuk dianalisis');
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
          task: task,
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

  const getTaskLabel = () => {
    switch (task) {
      case 'summarize':
        return 'Ringkasan';
      case 'recommend':
        return 'Rekomendasi';
      default:
        return 'Analisis';
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto p-4 sm:p-6">
      <div className="bg-white dark:bg-zinc-800 rounded-xl shadow-lg border border-gray-200 dark:border-zinc-700 p-6">
        {/* Header */}
        <div className="mb-6">
          <h2 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white mb-2">
            ☕ AI Coffee Assistant
          </h2>
          <p className="text-gray-600 dark:text-gray-400 text-sm">
            Jelaskan preferensi Anda, dan AI akan membantu menganalisis dan memberikan rekomendasi coffee shop terbaik
          </p>
        </div>

        {/* Task Selector */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-900 dark:text-white mb-3">
            Pilih Jenis Analisis:
          </label>
          <div className="grid grid-cols-3 gap-2">
            {[
              { value: 'analyze', label: '📊 Analisis', icon: '📊' },
              { value: 'summarize', label: '📝 Ringkas', icon: '📝' },
              { value: 'recommend', label: '🎯 Rekomendasikan', icon: '🎯' },
            ].map((option) => (
              <button
                key={option.value}
                onClick={() => setTask(option.value)}
                className={`p-3 rounded-lg font-medium transition-all duration-200 text-sm ${
                  task === option.value
                    ? 'bg-indigo-600 text-white shadow-lg'
                    : 'bg-gray-100 dark:bg-zinc-700 text-gray-900 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-zinc-600'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {/* Input Area */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
            Masukkan Teks:
          </label>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Contoh: Saya suka coffee shop yang cozy, memiliki wifi, dan menu kopi specialty. Bagaimana saya mencari coffee shop yang tepat?"
            className="w-full p-4 border border-gray-300 dark:border-zinc-600 rounded-lg bg-white dark:bg-zinc-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-indigo-600 focus:border-transparent outline-none resize-none h-24 sm:h-32"
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Minimal 10 karakter
          </p>
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
            className="flex-1 px-6 py-3 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-400 text-white font-semibold rounded-lg transition-colors duration-200 flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <span className="animate-spin">⏳</span>
                Menganalisis...
              </>
            ) : (
              <>
                <span>🤖</span>
                Analisis dengan AI
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
          <div className="mt-6 p-6 bg-gradient-to-br from-indigo-50 to-blue-50 dark:from-indigo-900/20 dark:to-blue-900/20 border border-indigo-200 dark:border-indigo-800 rounded-lg">
            <div className="mb-4">
              <h3 className="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2 mb-3">
                <span>✨</span>
                {getTaskLabel()} AI
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4 pb-4 border-b border-gray-300 dark:border-gray-600">
                Input: <span className="font-medium italic">{result.input}</span>
              </p>
            </div>

            {/* Analysis Result */}
            <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg border border-gray-200 dark:border-zinc-700">
              <p className="text-gray-800 dark:text-gray-200 leading-relaxed whitespace-pre-wrap">
                {result.analysis || 'Tidak ada hasil analisis'}
              </p>
            </div>

            {/* Timestamp */}
            <p className="text-xs text-gray-500 dark:text-gray-500 mt-4 text-right">
              {new Date(result.timestamp * 1000).toLocaleTimeString('id-ID')}
            </p>
          </div>
        )}

        {/* Loading Spinner */}
        {loading && (
          <div className="mt-6 flex justify-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
          </div>
        )}

        {/* Tips */}
        <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
          <h4 className="font-semibold text-blue-900 dark:text-blue-300 mb-2">💡 Tips:</h4>
          <ul className="text-sm text-blue-800 dark:text-blue-400 space-y-1">
            <li>• Jelaskan preferensi Anda dengan detail untuk hasil terbaik</li>
            <li>• Gunakan "Rekomendasikan" untuk mendapat saran coffee shop spesifik</li>
            <li>• Analisis AI berbasis teks dari Llama 2</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default LLMAnalyzer;

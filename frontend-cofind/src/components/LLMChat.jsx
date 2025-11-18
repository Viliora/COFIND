import React, { useState, useRef, useEffect } from 'react';

const LLMChat = () => {
  const [messages, setMessages] = useState([
    {
      id: 1,
      text: 'Halo! Saya adalah AI Coffee Assistant. Saya siap membantu Anda menemukan coffee shop yang sempurna. Ceritakan preferensi Anda!',
      sender: 'ai',
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [context, setContext] = useState('');
  const messagesEndRef = useRef(null);
  const [error, setError] = useState(null);

  const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async () => {
    if (!input.trim()) return;

    // Add user message
    const userMessage = {
      id: messages.length + 1,
      text: input,
      sender: 'user',
      timestamp: new Date(),
    };
    setMessages([...messages, userMessage]);
    setInput('');
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/api/llm/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: input,
          context: context || undefined,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || 'Terjadi kesalahan saat berkomunikasi dengan AI');
      }

      // Add AI response
      const aiMessage = {
        id: messages.length + 2,
        text: data.reply || data.message || 'Maaf, saya tidak bisa merespon saat ini',
        sender: 'ai',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, aiMessage]);

      // Update context for conversation continuity
      setContext(data.message || '');
    } catch (err) {
      setError(err.message || 'Gagal menghubungi AI');
      console.error('Chat Error:', err);

      // Add error message
      const errorMessage = {
        id: messages.length + 2,
        text: `❌ Error: ${err.message || 'Koneksi ke AI gagal. Coba lagi nanti.'}`,
        sender: 'system',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleClearChat = () => {
    setMessages([
      {
        id: 1,
        text: 'Halo! Saya adalah AI Coffee Assistant. Saya siap membantu Anda menemukan coffee shop yang sempurna. Ceritakan preferensi Anda!',
        sender: 'ai',
        timestamp: new Date(),
      },
    ]);
    setContext('');
    setError(null);
  };

  const getMessageStyle = (sender) => {
    if (sender === 'user') {
      return 'bg-indigo-600 text-white rounded-bl-xl rounded-tr-xl rounded-tl-lg';
    } else if (sender === 'ai') {
      return 'bg-gray-200 dark:bg-zinc-700 text-gray-900 dark:text-white rounded-br-xl rounded-tl-xl rounded-tr-lg';
    } else {
      return 'bg-red-100 dark:bg-red-900/30 text-red-900 dark:text-red-300 rounded-lg border border-red-300 dark:border-red-700';
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto p-4 sm:p-6 h-screen sm:h-auto flex flex-col">
      <div className="bg-white dark:bg-zinc-800 rounded-xl shadow-lg border border-gray-200 dark:border-zinc-700 overflow-hidden flex flex-col h-full">
        {/* Header */}
        <div className="bg-gradient-to-r from-indigo-600 to-blue-600 p-4 sm:p-6 text-white">
          <h2 className="text-2xl sm:text-3xl font-bold mb-1">☕ AI Coffee Chat</h2>
          <p className="text-indigo-100 text-sm">
            Percakapan interaktif dengan AI untuk menemukan coffee shop impian Anda
          </p>
        </div>

        {/* Messages Container */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 bg-gray-50 dark:bg-zinc-900/50">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div className={`max-w-xs sm:max-w-sm lg:max-w-md px-4 py-3 ${getMessageStyle(message.sender)}`}>
                <p className="text-sm sm:text-base leading-relaxed whitespace-pre-wrap break-words">
                  {message.text}
                </p>
                <p className={`text-xs mt-2 ${message.sender === 'user' ? 'text-indigo-200' : 'text-gray-500 dark:text-gray-400'}`}>
                  {message.timestamp.toLocaleTimeString('id-ID', {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </p>
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-200 dark:bg-zinc-700 text-gray-900 dark:text-white rounded-br-xl rounded-tl-xl rounded-tr-lg px-4 py-3">
                <div className="flex gap-2 items-center">
                  <span className="animate-pulse">●</span>
                  <span className="animate-pulse animation-delay-100">●</span>
                  <span className="animate-pulse animation-delay-200">●</span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Error Message */}
        {error && (
          <div className="px-4 sm:px-6 py-3 bg-red-50 dark:bg-red-900/20 border-t border-red-200 dark:border-red-800">
            <p className="text-red-700 dark:text-red-300 text-sm">
              ⚠️ {error}
            </p>
          </div>
        )}

        {/* Input Area */}
        <div className="border-t border-gray-200 dark:border-zinc-700 p-4 sm:p-6 bg-white dark:bg-zinc-800">
          <div className="flex gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ketik pesan Anda... (Shift+Enter untuk baris baru)"
              className="flex-1 p-3 border border-gray-300 dark:border-zinc-600 rounded-lg bg-white dark:bg-zinc-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-indigo-600 focus:border-transparent outline-none resize-none h-12"
              disabled={loading}
            />
            <button
              onClick={handleSendMessage}
              disabled={loading || !input.trim()}
              className="px-4 py-3 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-400 text-white font-semibold rounded-lg transition-colors duration-200 flex items-center gap-2 h-12"
              title="Kirim pesan (Enter)"
            >
              {loading ? '⏳' : '📤'}
            </button>
            <button
              onClick={handleClearChat}
              className="px-4 py-3 bg-gray-300 dark:bg-zinc-600 hover:bg-gray-400 dark:hover:bg-zinc-500 text-gray-900 dark:text-white font-semibold rounded-lg transition-colors duration-200 h-12"
              title="Bersihkan percakapan"
            >
              🗑️
            </button>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
            💡 Tip: Tekan Enter untuk mengirim, Shift+Enter untuk baris baru
          </p>
        </div>
      </div>
    </div>
  );
};

export default LLMChat;

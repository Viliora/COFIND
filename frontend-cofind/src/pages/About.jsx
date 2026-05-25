import React, { useEffect, useMemo, useState, useId } from 'react';

const SECTIONS = [
  {
    id: 'apa',
    title: 'Apa itu Cofind?',
    icon: '☕',
    accent: 'from-amber-500/20 to-orange-500/10 dark:from-amber-500/15 dark:to-orange-600/10',
    border: 'border-amber-200/80 dark:border-amber-800/50',
    keywords:
      'cofind aplikasi coffee shop pontianak temukan ngopi katalog',
    paragraphs: [
      'Cofind adalah aplikasi web untuk menemukan dan menjelajahi coffee shop di Pontianak — dari katalog lengkap, peta radius, hingga rekomendasi yang membaca pola ulasan pengunjung.',
      'Kami menggabungkan data tempat (alamat, rating, jumlah ulasan) dengan konten ulasan agar pilihan Anda tidak hanya mengandalkan angka bintang saja.',
    ],
  },
  {
    id: 'tujuan',
    title: 'Tujuan & nilai lebih',
    icon: '🎯',
    accent: 'from-indigo-500/20 to-violet-500/10 dark:from-indigo-500/15 dark:to-violet-600/10',
    border: 'border-indigo-200/80 dark:border-indigo-800/50',
    keywords: 'tujuan masalah preferensi konteks aktivitas relevansi ulasan',
    paragraphs: [
      'Banyak pengguna ingin tempat yang cocok untuk kerja santai, meeting, atau sekadar nongkrong — bukan hanya “yang ratingnya tinggi”. Cofind membantu menyaring sinyal dari teks ulasan dan preferensi konteks.',
      'Nilai lebih: rekomendasi berbasis bukti ulasan, koleksi pribadi (favorit & ingin dikunjungi), dan transparansi sumber data untuk kepercayaan pengguna.',
    ],
  },
  {
    id: 'fitur',
    title: 'Fitur utama',
    icon: '✨',
    accent: 'from-pink-500/20 to-rose-500/10 dark:from-pink-500/15 dark:to-rose-600/10',
    border: 'border-pink-200/80 dark:border-pink-800/50',
    keywords:
      'fitur beranda peta featured favorit want to visit login rekomendasi llm analisis pill konteks',
    paragraphs: [
      'Beranda: katalog coffee shop, featured, terbaru, peta radius, dan statistik ringkas.',
      'Koleksi: simpan favorit dan daftar “want to visit” setelah login.',
      'Rekomendasi konteks: pilih pill aktivitas — analisis LLM dan skor ulasan (khusus pengguna login) menampilkan coffee shop relevan beserta kutipan bukti ulasan.',
    ],
  },
  {
    id: 'data',
    title: 'Cakupan & sumber data',
    icon: '📍',
    accent: 'from-emerald-500/20 to-teal-500/10 dark:from-emerald-500/15 dark:to-teal-600/10',
    border: 'border-emerald-200/80 dark:border-emerald-800/50',
    keywords: 'google places api pontianak data rating ulasan 2025',
    paragraphs: [
      'Fokus geografis: Pontianak. Informasi tempat dan metrik ringkasan mengacu pada integrasi Places API (periode referensi data dapat berbeda per entri).',
      'Ulasan yang ditampilkan di aplikasi berasal dari kontribusi pengguna terdaftar di platform Cofind; rekomendasi AI memadukan ulasan ini dengan sinyal lain yang tersedia di backend.',
    ],
  },
  {
    id: 'teknologi',
    title: 'Teknologi',
    icon: '⚙️',
    accent: 'from-slate-500/20 to-zinc-500/10 dark:from-slate-500/15 dark:to-zinc-600/10',
    border: 'border-slate-200/80 dark:border-slate-600/50',
    keywords:
      'react vite tailwind flask python sqlite backend frontend huggingface llm',
    paragraphs: [
      'Antarmuka: React, Vite, Tailwind CSS. Layanan backend: Flask (Python), penyimpanan data aplikasi termasuk SQLite untuk akun dan sesi.',
      'Alur rekomendasi memakai ekspansi kata kunci, skor berbasis ulasan, dan ringkasan/penyusunan ulang kandidat lewat model LLM sesuai konfigurasi server.',
    ],
  },
  {
    id: 'tim',
    title: 'Tim',
    icon: '👥',
    accent: 'from-blue-500/20 to-cyan-500/10 dark:from-blue-500/15 dark:to-cyan-600/10',
    border: 'border-blue-200/80 dark:border-blue-800/50',
    keywords: 'tim pengembang cofind maintainer',
    paragraphs: [
      'Cofind dikembangkan dan dirawat oleh tim pengembang Cofind. Halaman ini akan diperbarui jika ada informasi tim atau kontributor resmi yang ingin ditampilkan.',
    ],
  },
  {
    id: 'kontak',
    title: 'Kontak & umpan balik',
    icon: '✉️',
    accent: 'from-violet-500/20 to-purple-500/10 dark:from-violet-500/15 dark:to-purple-600/10',
    border: 'border-violet-200/80 dark:border-violet-800/50',
    keywords: 'kontak email saran bug laporan',
    paragraphs: [
      'Punya saran fitur, laporan bug, atau pertanyaan? Silakan hubungi tim lewat saluran resmi yang Anda tentukan (contoh: email support atau repositori proyek).',
    ],
  },
  {
    id: 'versi',
    title: 'Versi & pembaruan',
    icon: '📅',
    accent: 'from-orange-500/20 to-amber-500/10 dark:from-orange-500/15 dark:to-amber-600/10',
    border: 'border-orange-200/80 dark:border-orange-800/50',
    keywords: 'versi changelog update pembaruan',
    paragraphs: [
      'Versi aplikasi frontend mengikuti rilis proyek Anda (lihat package.json). Konten halaman Tentang ini disarankan diperbarui setiap ada perubahan besar fitur atau kebijakan data.',
    ],
  },
];

function normalizeSearch(s) {
  return String(s || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ');
}

export default function About() {
  const searchId = useId();
  const [query, setQuery] = useState('');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    document.title = 'Tentang - Cofind';
    const t = requestAnimationFrame(() => setMounted(true));
    return () => {
      cancelAnimationFrame(t);
      document.title = 'Cofind';
    };
  }, []);

  const q = normalizeSearch(query);

  const filtered = useMemo(() => {
    if (!q) return SECTIONS;
    return SECTIONS.filter((s) => {
      const hay = normalizeSearch(
        `${s.title} ${s.keywords} ${s.paragraphs.join(' ')}`,
      );
      return hay.includes(q);
    });
  }, [q]);

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 via-white to-indigo-50/40 dark:from-zinc-950 dark:via-zinc-900 dark:to-indigo-950/30 py-6 sm:py-10 px-3 sm:px-4 md:px-6 lg:px-8">
      <style>{`
        @keyframes about-card-in {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .about-card-animate {
          animation: about-card-in 0.45s ease-out both;
        }
        @keyframes about-search-glow {
          0%, 100% { box-shadow: 0 0 0 0 rgba(99, 102, 241, 0); }
          50% { box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.12); }
        }
        .about-search-focus:focus-within {
          animation: about-search-glow 1.2s ease-in-out;
        }
      `}</style>

      <div className="max-w-3xl mx-auto">
        <header
          className={`text-center transition-all duration-500 ${
            mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'
          }`}
        >
          <div className="inline-flex h-16 w-16 sm:h-20 sm:w-20 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 text-3xl sm:text-4xl shadow-lg shadow-indigo-500/25 mb-5 transition-transform duration-300 hover:scale-105 hover:rotate-1 active:scale-95">
            <span aria-hidden>☕</span>
          </div>
          <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold bg-gradient-to-r from-gray-900 via-indigo-800 to-violet-800 dark:from-white dark:via-indigo-200 dark:to-violet-200 bg-clip-text text-transparent px-2">
            Tentang Cofind
          </h1>
          <p className="mt-3 text-sm sm:text-base text-gray-600 dark:text-gray-400 max-w-xl mx-auto leading-relaxed">
            Kenali aplikasi, fitur, dan cara kami membantu Anda menemukan coffee
            shop yang pas di Pontianak.
          </p>
        </header>

        {/* Pencarian dalam halaman */}
        <div
          className={`mt-8 sm:mt-10 transition-all duration-500 delay-75 ${
            mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'
          }`}
        >
          <label
            htmlFor={searchId}
            className="sr-only"
          >
            Cari di halaman tentang
          </label>
          <div className="about-search-focus rounded-2xl border border-indigo-200/70 dark:border-indigo-800/50 bg-white/80 dark:bg-zinc-900/80 backdrop-blur-sm shadow-md shadow-indigo-500/5 transition-shadow duration-300 hover:shadow-lg hover:border-indigo-300/80 dark:hover:border-indigo-700/60">
            <div className="flex items-center gap-3 px-4 py-3 sm:px-5 sm:py-3.5">
              <span
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-100 dark:bg-indigo-950/80 text-indigo-600 dark:text-indigo-300 transition-transform duration-200 group-focus-within:scale-110"
                aria-hidden
              >
                <svg
                  className="h-5 w-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                  />
                </svg>
              </span>
              <input
                id={searchId}
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Cari topik: LLM, favorit, Pontianak, teknologi…"
                className="flex-1 min-w-0 bg-transparent text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 text-sm sm:text-base outline-none"
                autoComplete="off"
              />
              {query ? (
                <button
                  type="button"
                  onClick={() => setQuery('')}
                  className="shrink-0 rounded-full px-3 py-1 text-xs font-semibold text-indigo-600 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/60 hover:bg-indigo-100 dark:hover:bg-indigo-900/80 active:scale-95 transition-all duration-200"
                >
                  Hapus
                </button>
              ) : null}
            </div>
          </div>
          <p className="mt-2 text-center text-xs text-gray-500 dark:text-gray-400">
            {q ? (
              <>
                Menampilkan{' '}
                <span className="font-semibold text-indigo-600 dark:text-indigo-400">
                  {filtered.length}
                </span>{' '}
                dari {SECTIONS.length} bagian
              </>
            ) : (
              'Ketik kata kunci untuk menyaring bagian di bawah.'
            )}
          </p>
        </div>

        {/* Kartu konten */}
        <div className="mt-8 sm:mt-10 space-y-4 sm:space-y-5">
          {filtered.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-gray-300 dark:border-zinc-600 bg-white/50 dark:bg-zinc-900/50 px-6 py-12 text-center transition-all duration-300">
              <p className="text-gray-600 dark:text-gray-400 text-sm sm:text-base">
                Tidak ada bagian yang cocok dengan “{query}”.
              </p>
              <button
                type="button"
                onClick={() => setQuery('')}
                className="mt-4 text-sm font-semibold text-indigo-600 dark:text-indigo-400 hover:underline underline-offset-2 active:opacity-80"
              >
                Kosongkan pencarian
              </button>
            </div>
          ) : (
            filtered.map((section, index) => (
              <article
                key={section.id}
                style={{ animationDelay: `${Math.min(index, 8) * 45}ms` }}
                className={`about-card-animate rounded-2xl border ${section.border} bg-gradient-to-br ${section.accent} p-5 sm:p-6 shadow-sm transition-all duration-300 ease-out hover:shadow-md hover:-translate-y-0.5 hover:border-indigo-300/50 dark:hover:border-indigo-600/40 active:translate-y-0`}
              >
                <h2 className="flex items-center gap-2 text-lg sm:text-xl font-bold text-gray-900 dark:text-white">
                  <span
                    className="text-2xl leading-none transition-transform duration-200 hover:scale-110 inline-block"
                    aria-hidden
                  >
                    {section.icon}
                  </span>
                  {section.title}
                </h2>
                <div className="mt-3 space-y-2.5 text-sm sm:text-base text-gray-700 dark:text-gray-300 leading-relaxed">
                  {section.paragraphs.map((p, i) => (
                    <p key={i}>{p}</p>
                  ))}
                </div>
              </article>
            ))
          )}
        </div>

        <footer
          className={`mt-12 sm:mt-14 text-center text-xs text-gray-500 dark:text-gray-500 transition-opacity duration-500 ${
            mounted ? 'opacity-100' : 'opacity-0'
          }`}
        >
          <p>
            Terima kasih telah menggunakan Cofind — selamat menjelajahi coffee shop
            favorit Anda.
          </p>
        </footer>
      </div>
    </div>
  );
}

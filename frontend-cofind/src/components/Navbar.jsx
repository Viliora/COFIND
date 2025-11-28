import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import cofindImg from '../assets/cofind.svg?url';

const Navbar = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [collectionDropdownOpen, setCollectionDropdownOpen] = useState(false);

  // Sync search query with URL params
  useEffect(() => {
    const query = searchParams.get('search') || '';
    setSearchQuery(query);
  }, [searchParams]);

  // Handle search submission
  const handleSearch = (e) => {
    e.preventDefault();
    if (location.pathname !== '/') {
      navigate(`/?search=${encodeURIComponent(searchQuery)}`);
    } else {
      const url = new URL(window.location);
      url.searchParams.set('search', searchQuery);
      window.history.pushState({}, '', url);
      window.dispatchEvent(new Event('popstate'));
    }
  };

  // Handle search input change
  const handleSearchChange = (e) => {
    const value = e.target.value;
    setSearchQuery(value);
    
    // Update URL in real-time if on home page
    if (location.pathname === '/') {
      const url = new URL(window.location);
      if (value) {
        url.searchParams.set('search', value);
      } else {
        url.searchParams.delete('search');
      }
      window.history.replaceState({}, '', url);
      window.dispatchEvent(new Event('popstate'));
    }
  };
  
  // Theme state management
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  const [dark, setDark] = useState(() => {
    try {
      const saved = localStorage.getItem('theme-dark');
      return saved === 'true' || (saved === null && prefersDark);
    } catch {
      return prefersDark;
    }
  });
  
  // Helper untuk check active route
  const isActive = (path) => {
    if (path === '/') {
      return location.pathname === '/';
    }
    return location.pathname.startsWith(path);
  };

  // Apply theme changes and save preference
  useEffect(() => {
    const root = document.documentElement;
    const html = document.querySelector('html');
    
    if (dark) {
      html.classList.add('dark');
      root.style.colorScheme = 'dark';
      localStorage.setItem('theme-dark', 'true');
    } else {
      html.classList.remove('dark');
      root.style.colorScheme = 'light';
      localStorage.setItem('theme-dark', 'false');
    }
  }, [dark]);

  // Listen for system theme changes
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (e) => {
      if (localStorage.getItem('theme-dark') === null) {
        setDark(e.matches);
      }
    };
    
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  return (
    <nav className="bg-white dark:bg-zinc-900 shadow-sm border-b border-gray-100 dark:border-zinc-800 fixed inset-x-0 top-0 z-50">
  <div className="max-w-7xl mx-auto px-3 sm:px-4 md:px-6 lg:px-8">
    <div className="flex justify-between items-center h-14 sm:h-16 gap-4">

          {/* Left: logo + brand name + search bar */}
          <div className="flex items-center gap-3 flex-shrink-0">
            {/* Logo & Brand Name */}
            <Link 
              to="/" 
              className="flex items-center gap-2 group"
              onClick={() => setMobileMenuOpen(false)}
            >
              <img 
                src={cofindImg} 
                alt="Cofind" 
                className="h-8 sm:h-9 md:h-10 w-auto transition-transform group-hover:scale-105" 
              />
              <span className="text-xl sm:text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 dark:from-blue-400 dark:to-purple-400 bg-clip-text text-transparent">
                COFIND
              </span>
            </Link>

            {/* Search Bar */}
            <form onSubmit={handleSearch} className="hidden sm:flex items-center relative">
              <input
                type="text"
                value={searchQuery}
                onChange={handleSearchChange}
                placeholder="Coffee shop yang ingin dituju.."
                className="w-48 md:w-64 lg:w-80 px-4 py-2 pl-10 text-sm bg-gray-50 dark:bg-zinc-800 border border-gray-200 dark:border-zinc-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-transparent text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 transition-all"
              />
              <svg 
                className="absolute left-3 w-4 h-4 text-gray-400 dark:text-gray-500 pointer-events-none"
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
              </svg>
            </form>
          </div>

          {/* Center: navigation buttons */}
          <div className="hidden md:flex flex-1 justify-center items-center">
  <div className="flex items-center gap-0.5 bg-gray-50 dark:bg-zinc-800/50 rounded-lg p-1">
    {/* nav buttons… */} 

              {/* Beranda */}
              <Link
                to="/"
                className={`relative inline-flex items-center justify-center gap-1.5 rounded-md px-3 lg:px-4 py-1.5 lg:py-2 text-xs lg:text-sm font-medium transition-all duration-300 ease-in-out ${
                  isActive('/')
                    ? 'bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow-md'
                    : 'bg-white dark:bg-zinc-700 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-50 dark:hover:bg-zinc-600 hover:shadow-sm'
                }`}
              >
                <svg
                  className="w-4 h-4 transition-transform duration-300 group-hover:scale-110"
                  fill="none"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path>
                </svg>
                <span>Beranda</span>
              </Link>

              {/* Koleksi (Dropdown) */}
              <div className="relative">
                <button
                  onClick={() => setCollectionDropdownOpen(!collectionDropdownOpen)}
                  className={`relative inline-flex items-center justify-center gap-1.5 rounded-md px-3 lg:px-4 py-1.5 lg:py-2 text-xs lg:text-sm font-medium transition-all duration-300 ease-in-out ${
                    isActive('/favorite') || isActive('/want-to-visit')
                      ? 'bg-gradient-to-r from-pink-500 to-rose-500 text-white shadow-md'
                      : 'bg-white dark:bg-zinc-700 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-50 dark:hover:bg-zinc-600 hover:shadow-sm'
                  }`}
                >
                  <svg
                    className="w-4 h-4 transition-transform duration-300"
                    fill="none"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"></path>
                  </svg>
                  <span>Koleksi</span>
                  <svg
                    className={`w-3 h-3 transition-transform duration-300 ${collectionDropdownOpen ? 'rotate-180' : ''}`}
                    fill="none"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path d="M19 9l-7 7-7-7"></path>
                  </svg>
                </button>

                {/* Dropdown Menu */}
                {collectionDropdownOpen && (
                  <div className="absolute top-full left-0 mt-2 w-48 bg-white dark:bg-zinc-800 rounded-lg shadow-lg border border-gray-200 dark:border-zinc-700 py-2 z-50 animate-fadeIn">
                    <Link
                      to="/favorite"
                      onClick={() => setCollectionDropdownOpen(false)}
                      className="flex items-center gap-2 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-zinc-700 transition-all duration-300 ease-in-out hover:pl-5"
                    >
                      <svg className="w-4 h-4" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
                        <path d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"></path>
                      </svg>
                      <span>Favorit</span>
                    </Link>
                    <Link
                      to="/want-to-visit"
                      onClick={() => setCollectionDropdownOpen(false)}
                      className="flex items-center gap-2 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-zinc-700 transition-all duration-300 ease-in-out hover:pl-5"
                    >
                      <svg className="w-4 h-4" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
                        <path d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"></path>
                      </svg>
                      <span>Want to Visit</span>
                    </Link>
                  </div>
                )}
              </div>

              {/* Rekomendasi (AI Analyzer) */}
              <Link
                to="/ai-analyzer"
                className={`relative inline-flex items-center justify-center gap-1.5 rounded-md px-3 lg:px-4 py-1.5 lg:py-2 text-xs lg:text-sm font-medium transition-all duration-300 ease-in-out ${
                  isActive('/ai-analyzer')
                    ? 'bg-gradient-to-r from-emerald-500 to-teal-500 text-white shadow-md'
                    : 'bg-white dark:bg-zinc-700 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-50 dark:hover:bg-zinc-600 hover:shadow-sm'
                }`}
              >
                <svg
                  className="w-4 h-4 transition-transform duration-300"
                  fill="none"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path>
                </svg>
                <span>Rekomendasi</span>
              </Link>

              {/* About */}
              <Link
                to="/about"
                className={`relative inline-flex items-center justify-center gap-1.5 rounded-md px-3 lg:px-4 py-1.5 lg:py-2 text-xs lg:text-sm font-medium transition-all duration-300 ease-in-out ${
                  isActive('/about')
                    ? 'bg-gradient-to-r from-amber-500 to-orange-500 text-white shadow-md'
                    : 'bg-white dark:bg-zinc-700 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-50 dark:hover:bg-zinc-600 hover:shadow-sm'
                }`}
              >
                <svg
                  className="w-4 h-4 transition-transform duration-300"
                  fill="none"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                <span>Tentang</span>
              </Link>
            </div>
          </div>

          {/* Right side: theme switch + mobile menu */}
          <div className="flex items-center gap-2 sm:gap-3 flex-shrink-0 min-w-max">
            {/* Theme toggle */}
            <button
              onClick={() => setDark((v) => !v)}
              className="p-2 rounded-lg bg-gray-100 dark:bg-zinc-800 hover:bg-gray-200 dark:hover:bg-zinc-700 transition-colors duration-200"
              aria-label="Toggle theme"
              title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {dark ? (
                <svg
                  className="w-5 h-5 text-amber-500"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"></path>
                </svg>
              ) : (
                <svg
                  className="w-5 h-5 text-yellow-600"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"></path>
                </svg>
              )}
            </button>

            {/* Mobile menu button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-1.5 sm:p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-zinc-800 transition-colors"
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? (
                <svg className="w-5 h-5 text-gray-600 dark:text-gray-300" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
                  <path d="M6 18L18 6M6 6l12 12"></path>
                </svg>
              ) : (
                <svg className="w-5 h-5 text-gray-600 dark:text-gray-300" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
                  <path d="M4 6h16M4 12h16M4 18h16"></path>
                </svg>
              )}
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-gray-100 dark:border-zinc-800 py-3 max-w-7xl mx-auto px-3 sm:px-4 md:px-6 lg:px-8">
            {/* Mobile Search Bar */}
            <form onSubmit={handleSearch} className="sm:hidden mb-3 relative">
              <input
                type="text"
                value={searchQuery}
                onChange={handleSearchChange}
                placeholder="Coffee shop yang ingin dituju.."
                className="w-full px-4 py-2 pl-10 text-sm bg-gray-50 dark:bg-zinc-800 border border-gray-200 dark:border-zinc-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-transparent text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400"
              />
              <svg 
                className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 dark:text-gray-500 pointer-events-none"
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
              </svg>
            </form>
            <div className="flex flex-col gap-1">
              <Link
                to="/"
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-300 ease-in-out ${
                  isActive('/')
                    ? 'bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow-md'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-white/80 dark:hover:bg-zinc-700/80 hover:shadow-sm hover:pl-5'
                }`}
              >
                <svg className="w-4 h-4 transition-transform duration-300" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
                  <path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path>
                </svg>
                Beranda
              </Link>
              {/* Koleksi Section */}
              <div className="space-y-1">
                <div className="px-4 py-2 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Koleksi
                </div>
                <Link
                  to="/favorite"
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-300 ease-in-out ${
                    isActive('/favorite')
                      ? 'bg-gradient-to-r from-pink-500 to-rose-500 text-white shadow-md'
                      : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-white/80 dark:hover:bg-zinc-700/80 hover:shadow-sm hover:pl-5'
                  }`}
                >
                  <svg className="w-4 h-4 transition-transform duration-300" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
                    <path d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"></path>
                  </svg>
                  Favorit
                </Link>
                <Link
                  to="/want-to-visit"
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-300 ease-in-out ${
                    isActive('/want-to-visit')
                      ? 'bg-gradient-to-r from-blue-500 to-cyan-500 text-white shadow-md'
                      : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-white/80 dark:hover:bg-zinc-700/80 hover:shadow-sm hover:pl-5'
                  }`}
                >
                  <svg className="w-4 h-4 transition-transform duration-300" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
                    <path d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"></path>
                  </svg>
                  Want to Visit
                </Link>
              </div>
              <Link
                to="/ai-analyzer"
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-300 ease-in-out ${
                  isActive('/ai-analyzer')
                    ? 'bg-gradient-to-r from-emerald-500 to-teal-500 text-white shadow-md'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-white/80 dark:hover:bg-zinc-700/80 hover:shadow-sm hover:pl-5'
                }`}
              >
                <svg className="w-4 h-4 transition-transform duration-300" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
                  <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path>
                </svg>
                Rekomendasi
              </Link>
              <Link
                to="/about"
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-300 ease-in-out ${
                  isActive('/about')
                    ? 'bg-gradient-to-r from-amber-500 to-orange-500 text-white shadow-md'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-white/80 dark:hover:bg-zinc-700/80 hover:shadow-sm hover:pl-5'
                }`}
              >
                <svg className="w-4 h-4 transition-transform duration-300" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
                  <path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                About
              </Link>
            </div>
          </div>
        )}
      </div>
    </nav>
  );
};

export default Navbar;
import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import cofindImg from '../assets/cofind.svg?url';
import { useAuth } from '../context/authContext';
import { AuthProvider } from "../context/authContext";

const Navbar = () => {
  const { user, profile, isAuthenticated, isAdmin, signOut } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [collectionDropdownOpen, setCollectionDropdownOpen] = useState(false);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);

  // Sync search query with URL params
  useEffect(() => {
    const query = searchParams.get('search') || '';
    setSearchQuery(query);
  }, [searchParams]);

  // Close user dropdown when route changes
  useEffect(() => {
    setUserDropdownOpen(false);
  }, [location.pathname]);

  // Close user dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (userDropdownOpen && !event.target.closest('.user-dropdown-container')) {
        setUserDropdownOpen(false);
      }
    };

    if (userDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }
  }, [userDropdownOpen]);

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

          {/* Right side: theme switch + user + mobile menu */}
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

            {/* User Auth Button - Desktop */}
            <div className="hidden md:block">
              {isAuthenticated ? (
                <div className="relative user-dropdown-container">
                  <button 
                    onClick={() => setUserDropdownOpen(!userDropdownOpen)}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-100 dark:bg-zinc-800 hover:bg-gray-200 dark:hover:bg-zinc-700 transition-colors"
                  >
                    <div className="w-7 h-7 rounded-full bg-gradient-to-r from-amber-500 to-orange-500 flex items-center justify-center text-white text-sm font-semibold">
                      {profile?.username?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}
                    </div>
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300 max-w-24 truncate">
                      {profile?.username || user?.email?.split('@')[0] || 'User'}
                    </span>
                    <svg 
                      className={`w-4 h-4 text-gray-500 transition-transform ${userDropdownOpen ? 'rotate-180' : ''}`} 
                      fill="none" 
                      stroke="currentColor" 
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  {/* Dropdown */}
                  {userDropdownOpen && (
                    <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-zinc-800 rounded-lg shadow-lg border border-gray-200 dark:border-zinc-700 py-2 z-50">
                      <Link
                        to="/profile"
                        onClick={() => setUserDropdownOpen(false)}
                        className="flex items-center gap-2 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-zinc-700"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                        </svg>
                        Profil Saya
                      </Link>
                      {isAdmin && (
                        <Link
                          to="/admin"
                          onClick={() => setUserDropdownOpen(false)}
                          className="flex items-center gap-2 px-4 py-2 text-sm text-purple-600 dark:text-purple-400 hover:bg-gray-100 dark:hover:bg-zinc-700"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                          </svg>
                          Admin Panel
                        </Link>
                      )}
                      <button
                        onClick={async () => {
                          setUserDropdownOpen(false);
                          try {
                            console.log('[Navbar] Logging out - force clearing all storage...');
                            
                            // CRITICAL: Force clear ALL storage FIRST before signOut
                            try {
                              // Clear ALL localStorage keys
                              localStorage.clear();
                              console.log('[Navbar] ✅ localStorage cleared');
                              
                              // Clear ALL sessionStorage keys
                              sessionStorage.clear();
                              console.log('[Navbar] ✅ sessionStorage cleared');
                              
                              // Also try to clear IndexedDB if accessible
                              if ('indexedDB' in window) {
                                try {
                                  const databases = await indexedDB.databases();
                                  await Promise.all(
                                    databases.map(db => {
                                      if (db.name) {
                                        return new Promise((resolve, reject) => {
                                          const deleteReq = indexedDB.deleteDatabase(db.name);
                                          deleteReq.onsuccess = () => resolve();
                                          deleteReq.onerror = () => reject(deleteReq.error);
                                          deleteReq.onblocked = () => resolve(); // Continue even if blocked
                                        });
                                      }
                                    })
                                  );
                                  console.log('[Navbar] ✅ IndexedDB cleared');
                                } catch (idbError) {
                                  console.warn('[Navbar] ⚠️ Error clearing IndexedDB:', idbError);
                                }
                              }
                            } catch (clearError) {
                              console.error('[Navbar] ⚠️ Error clearing storage:', clearError);
                            }
                            
                            // Sign out from Supabase (for server-side cleanup)
                            try {
                              const result = await signOut();
                              if (result?.error) {
                                console.error('[Navbar] Error signing out:', result.error);
                              } else {
                                console.log('[Navbar] Sign out successful');
                              }
                            } catch (signOutError) {
                              console.warn('[Navbar] ⚠️ Error during signOut (non-critical):', signOutError);
                            }
                            
                            // Navigate to login page after logout
                            console.log('[Navbar] ✅ All storage cleared, navigating to login...');
                            navigate('/login');
                          } catch (error) {
                            console.error('[Navbar] Error during logout:', error);
                            // Force clear storage and navigate even if there's an error
                            try {
                              localStorage.clear();
                              sessionStorage.clear();
                              console.log('[Navbar] ✅ Emergency: Storage cleared, navigating to login...');
                            } catch (e) {
                              console.error('[Navbar] ❌ Failed to clear storage:', e);
                            }
                            navigate('/login');
                          }
                        }}
                        className="flex items-center gap-2 px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-gray-100 dark:hover:bg-zinc-700 w-full text-left"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                        </svg>
                        Keluar
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <Link
                  to="/login"
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-amber-500 to-orange-500 text-white text-sm font-medium hover:from-amber-600 hover:to-orange-600 transition-colors shadow-sm"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
                  </svg>
                  Masuk
                </Link>
              )}
            </div>

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

              {/* User Auth Section - Mobile */}
              <div className="border-t border-gray-100 dark:border-zinc-800 mt-2 pt-2">
                {isAuthenticated ? (
                  <>
                    <Link
                      to="/profile"
                      onClick={() => setMobileMenuOpen(false)}
                      className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-white/80 dark:hover:bg-zinc-700/80 transition-all duration-300"
                    >
                      <div className="w-6 h-6 rounded-full bg-gradient-to-r from-amber-500 to-orange-500 flex items-center justify-center text-white text-xs font-semibold">
                        {profile?.username?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}
                      </div>
                      Profil Saya
                    </Link>
                    {isAdmin && (
                      <Link
                        to="/admin"
                        onClick={() => setMobileMenuOpen(false)}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-purple-600 dark:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-900/20 transition-all duration-300"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                        </svg>
                        Admin Panel
                      </Link>
                    )}
                    <button
                      onClick={async () => {
                        setMobileMenuOpen(false);
                        try {
                          console.log('[Navbar] Logging out - force clearing all storage...');
                          
                          // CRITICAL: Force clear ALL storage FIRST before signOut
                          try {
                            // Clear ALL localStorage keys
                            localStorage.clear();
                            console.log('[Navbar] ✅ localStorage cleared');
                            
                            // Clear ALL sessionStorage keys
                            sessionStorage.clear();
                            console.log('[Navbar] ✅ sessionStorage cleared');
                            
                            // Also try to clear IndexedDB if accessible
                            if ('indexedDB' in window) {
                              try {
                                const databases = await indexedDB.databases();
                                await Promise.all(
                                  databases.map(db => {
                                    if (db.name) {
                                      return new Promise((resolve, reject) => {
                                        const deleteReq = indexedDB.deleteDatabase(db.name);
                                        deleteReq.onsuccess = () => resolve();
                                        deleteReq.onerror = () => reject(deleteReq.error);
                                        deleteReq.onblocked = () => resolve(); // Continue even if blocked
                                      });
                                    }
                                  })
                                );
                                console.log('[Navbar] ✅ IndexedDB cleared');
                              } catch (idbError) {
                                console.warn('[Navbar] ⚠️ Error clearing IndexedDB:', idbError);
                              }
                            }
                          } catch (clearError) {
                            console.error('[Navbar] ⚠️ Error clearing storage:', clearError);
                          }
                          
                          // Sign out from Supabase (for server-side cleanup)
                          try {
                            const result = await signOut();
                            if (result?.error) {
                              console.error('[Navbar] Error signing out:', result.error);
                            } else {
                              console.log('[Navbar] Sign out successful');
                            }
                          } catch (signOutError) {
                            console.warn('[Navbar] ⚠️ Error during signOut (non-critical):', signOutError);
                          }
                          
                          // Navigate to login page after logout
                          console.log('[Navbar Mobile] ✅ All storage cleared, navigating to login...');
                          setMobileMenuOpen(false); // Close mobile menu
                          navigate('/login');
                        } catch (error) {
                          console.error('[Navbar Mobile] Error during logout:', error);
                          // Force clear storage and navigate even if there's an error
                          try {
                            localStorage.clear();
                            sessionStorage.clear();
                            console.log('[Navbar Mobile] ✅ Emergency: Storage cleared, navigating to login...');
                          } catch (e) {
                            console.error('[Navbar Mobile] ❌ Failed to clear storage:', e);
                          }
                          setMobileMenuOpen(false); // Close mobile menu
                          navigate('/login');
                        }
                      }}
                      className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 w-full text-left transition-all duration-300"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                      </svg>
                      Keluar
                    </button>
                  </>
                ) : (
                  <Link
                    to="/login"
                    onClick={() => setMobileMenuOpen(false)}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-gradient-to-r from-amber-500 to-orange-500 text-white shadow-md"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
                    </svg>
                    Masuk / Daftar
                  </Link>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </nav>
  );
};

export default Navbar;
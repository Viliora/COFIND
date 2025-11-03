import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import userImg from '../assets/user.png';
import cofindImg from '../assets/cofind.svg?url';

const Navbar = () => {
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  
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
    <div className="flex justify-between items-center h-14 sm:h-16">

          {/* Left: logo */}
          <div className="flex items-center flex-shrink-0">
            <Link to="/" className="flex items-center group">
              <img 
                src={cofindImg} 
                alt="Cofind" 
                className="h-6 sm:h-7 md:h-8 w-auto transition-transform group-hover:scale-105" 
              />
            </Link>
          </div>

          {/* Center: navigation buttons */}
          <div className="hidden md:flex flex-1 justify-center items-center">
  <div className="flex items-center gap-0.5 bg-gray-50 dark:bg-zinc-800/50 rounded-lg p-1">
    {/* nav buttons… */} 

              {/* Home */}
              <Link
                to="/"
                className={`relative inline-flex items-center justify-center gap-1.5 rounded-md px-3 lg:px-4 py-1.5 lg:py-2 text-xs lg:text-sm font-medium transition-all duration-200 ${
                  isActive('/')
                    ? 'bg-white dark:bg-zinc-700 text-gray-900 dark:text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                }`}
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path>
                </svg>
                <span>Home</span>
              </Link>

              {/* Favorite */}
              <Link
                to="/favorite"
                className={`relative inline-flex items-center justify-center gap-1.5 rounded-md px-3 lg:px-4 py-1.5 lg:py-2 text-xs lg:text-sm font-medium transition-all duration-200 ${
                  isActive('/favorite')
                    ? 'bg-white dark:bg-zinc-700 text-gray-900 dark:text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                }`}
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"></path>
                </svg>
                <span>Favorite</span>
              </Link>

              {/* About */}
              <Link
                to="/about"
                className={`relative inline-flex items-center justify-center gap-1.5 rounded-md px-3 lg:px-4 py-1.5 lg:py-2 text-xs lg:text-sm font-medium transition-all duration-200 ${
                  isActive('/about')
                    ? 'bg-white dark:bg-zinc-700 text-gray-900 dark:text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                }`}
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                <span>About</span>
              </Link>
            </div>
          </div>

          {/* Right side: theme switch + profile + mobile menu */}
          <div className="flex items-center gap-2 sm:gap-3 flex-shrink-0 min-w-max">
            {/* Theme toggle */}
            <button
              onClick={() => setDark((v) => !v)}
              className="p-1.5 sm:p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-zinc-800 transition-colors"
              aria-label="Toggle theme"
              title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {dark ? (
                <svg
                  className="w-4 h-4 sm:w-5 sm:h-5 text-gray-600 dark:text-gray-300"
                  fill="none"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"></path>
                </svg>
              ) : (
                <svg
                  className="w-4 h-4 sm:w-5 sm:h-5 text-gray-600 dark:text-gray-300"
                  fill="none"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"></path>
                </svg>
              )}
            </button>

            {/* Profile button */}
            <button
              type="button"
              className="relative rounded-full focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 transition-transform hover:scale-105"
              aria-label="User menu"
              title="User profile"
            >
              <img 
                src={userImg} 
                alt="Profile" 
                className="w-7 h-7 sm:w-8 sm:h-8 md:w-9 md:h-9 rounded-full object-cover border-2 border-gray-200 dark:border-zinc-700" 
              />
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
            <div className="flex flex-col gap-1">
              <Link
                to="/"
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive('/')
                    ? 'bg-gray-100 dark:bg-zinc-800 text-gray-900 dark:text-white'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-zinc-800/50'
                }`}
              >
                <svg className="w-4 h-4" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
                  <path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path>
                </svg>
                Home
              </Link>
              <Link
                to="/favorite"
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive('/favorite')
                    ? 'bg-gray-100 dark:bg-zinc-800 text-gray-900 dark:text-white'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-zinc-800/50'
                }`}
              >
                <svg className="w-4 h-4" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
                  <path d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"></path>
                </svg>
                Favorite
              </Link>
              <Link
                to="/about"
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive('/about')
                    ? 'bg-gray-100 dark:bg-zinc-800 text-gray-900 dark:text-white'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-zinc-800/50'
                }`}
              >
                <svg className="w-4 h-4" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
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
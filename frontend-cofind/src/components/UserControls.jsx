// Floating User Controls Component - untuk button profile dan theme toggle
import React, { useEffect, useState } from 'react';
import userImg from '../assets/user.png';

const UserControls = () => {
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
    <div className="fixed top-20 sm:top-24 right-4 sm:right-6 z-40 flex flex-col items-center gap-2 sm:gap-3">
      {/* Theme Toggle Button */}
      <button
        onClick={() => setDark((v) => !v)}
        className="p-2 sm:p-2.5 rounded-full bg-white dark:bg-zinc-800 shadow-lg hover:shadow-xl border border-gray-200 dark:border-zinc-700 transition-all hover:scale-110"
        aria-label="Toggle theme"
        title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
      >
        {dark ? (
          <svg
            className="w-5 h-5 sm:w-6 sm:h-6 text-yellow-500"
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
            className="w-5 h-5 sm:w-6 sm:h-6 text-amber-500"
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

      {/* Profile Button */}
      <button
        type="button"
        className="relative rounded-full focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 transition-all hover:scale-110 shadow-lg hover:shadow-xl"
        aria-label="User menu"
        title="User profile"
      >
        <img 
          src={userImg} 
          alt="Profile" 
          className="w-10 h-10 sm:w-12 sm:h-12 rounded-full object-cover border-2 border-white dark:border-zinc-800 shadow-md" 
        />
      </button>
    </div>
  );
};

export default UserControls;


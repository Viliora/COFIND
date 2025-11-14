/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
  "./index.html",
  "./src/**/*.{js,ts,jsx,tsx}", 
],
  theme: {
    extend: {
      colors: {
        // Custom colors untuk profile button
        'profile-light': '#818cf8',  // indigo-500
        'profile-dark': '#6366f1',   // indigo-600
        // Custom colors untuk favorite button
        'favorite-light': '#ef4444', // red-500
        'favorite-dark': '#dc2626',  // red-600
      },
    },
  },
  plugins: [],
}


/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        cofind: {
          primary: 'var(--cofind-primary)',
          'primary-hover': 'var(--cofind-primary-hover)',
          secondary: 'var(--cofind-secondary)',
          'secondary-hover': 'var(--cofind-secondary-hover)',
          background: 'var(--cofind-background)',
          paper: 'var(--cofind-paper)',
          surface: 'var(--cofind-surface)',
          ink: 'var(--cofind-ink)',
          muted: 'var(--cofind-muted)',
          rule: 'var(--cofind-rule)',
          'on-primary': 'var(--cofind-on-primary)',
          'on-secondary': 'var(--cofind-on-secondary)',
        },
        'profile-light': 'var(--cofind-secondary)',
        'profile-dark': 'var(--cofind-secondary-hover)',
        'favorite-light': '#b45309',
        'favorite-dark': '#92400e',
      },
      fontFamily: {
        display: ['var(--font-display)'],
        sans: ['var(--font-body)'],
      },
      borderRadius: {
        control: 'var(--cofind-radius-control)',
        panel: 'var(--cofind-radius-panel)',
      },
      boxShadow: {
        'cofind-sm': 'var(--cofind-shadow-sm)',
        'cofind-md': 'var(--cofind-shadow-md)',
        'cofind-lg': 'var(--cofind-shadow-lg)',
      },
      maxWidth: {
        cofind: 'var(--cofind-content-max)',
      },
    },
  },
  plugins: [],
};
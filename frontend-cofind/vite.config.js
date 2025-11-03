import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react({
      // Enable Fast Refresh untuk instant updates
      fastRefresh: true,
    }),
  ],
  server: {
    // Enable HMR (Hot Module Replacement)
    hmr: {
      overlay: true, // Tampilkan error overlay
    },
    // Port untuk development server
    port: 5173,
    // Watch options untuk file changes
    watch: {
      usePolling: false,
      interval: 100,
    },
  },
  build: {
    // Memastikan service worker di-copy ke build output
    rollupOptions: {
      // Service worker di public/ akan otomatis di-copy
    },
  },
  // Public dir berisi file yang akan di-copy ke root output
  publicDir: 'public',
})

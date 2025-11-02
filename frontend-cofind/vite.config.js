import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    // Memastikan service worker di-copy ke build output
    rollupOptions: {
      // Service worker di public/ akan otomatis di-copy
    },
  },
  // Public dir berisi file yang akan di-copy ke root output
  publicDir: 'public',
})

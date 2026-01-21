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
    // Enable HMR with auto-detection for dynamic port assignment
    hmr: {
      protocol: 'ws',
      host: 'localhost',
      // Let Vite auto-detect the port
    },
    port: 5173,
    watch: {
      usePolling: false,
      interval: 100,
    },
  },
  build: {
    // Add cache busting untuk static assets
    rollupOptions: {
      output: {
        // Add hash to filenames untuk cache busting
        // Ini memastikan file baru selalu ter-load, bukan dari cache
        entryFileNames: 'assets/[name]-[hash].js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash].[ext]',
      },
    },
    // Service worker di public/ akan otomatis di-copy ke build output
  },
  // Public dir berisi file yang akan di-copy ke root output
  publicDir: 'public',
})

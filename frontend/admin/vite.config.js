import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Served under /admin/ in production (see nginx.conf). Set VITE_BASE=/ to serve from the site root (Vercel).
export default defineConfig({
  base: process.env.VITE_BASE || '/admin/',
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          charts: ['recharts'],
          vendor: ['@tanstack/react-query', 'axios', 'react-hook-form', 'react-hot-toast', 'react-dropzone', 'zustand'],
        },
      },
    },
  },
  server: {
    port: 5174,
    proxy: { '/api': process.env.API_TARGET || 'http://localhost:8000' },
  },
})

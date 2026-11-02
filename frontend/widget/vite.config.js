import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Builds ONE self-contained file: dist/helpdesk-widget.js
// Embed on any page with:
//   <script src="https://helpdesk.college.edu/widget/helpdesk-widget.js"
//           data-api="https://helpdesk.college.edu/api" defer></script>
export default defineConfig({
  plugins: [react()],
  define: { 'process.env.NODE_ENV': JSON.stringify('production') },
  server: {
    port: 5173,
    proxy: { '/api': process.env.API_TARGET || 'http://localhost:8000' },
  },
  build: {
    lib: {
      entry: 'src/main.jsx',
      name: 'CollegeHelpDesk',
      formats: ['iife'],
      fileName: () => 'helpdesk-widget.js',
    },
    cssCodeSplit: false,
    rollupOptions: { output: { inlineDynamicImports: true } },
  },
})

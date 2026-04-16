import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import http from 'http'

const proxyTarget =
  process.env.VITE_PROXY_TARGET ?? 'http://localhost:8050'

// Fresh connection per request so backend hostname (e.g. api:8050) is re-resolved
// each time; avoids ECONNREFUSED when the backend container restarts and gets a new IP.
const proxyAgent = new http.Agent({ keepAlive: false })

const isProduction = process.env.NODE_ENV === 'production'
// Disable HMR in production or if explicitly disabled
const disableHMR = isProduction || process.env.VITE_DISABLE_HMR === 'true'

// Determine if we're in a production-like environment (deployed)
// Only use custom HMR config if explicitly set via env vars
const useCustomHMR = !!process.env.VITE_HMR_HOST

export default defineConfig({
  plugins: [react()],
  esbuild: {
    drop: isProduction ? ['console', 'debugger'] : [],
  },
  server: {
    host: '0.0.0.0',
    allowedHosts: [
      'localhost',
      '.mamaope.com',
      'empirico.ai',
      '.empirico.ai',
    ],
    hmr: disableHMR
      ? false
      : useCustomHMR
        ? {
            // Explicit override for proxied/cloud dev environments.
            host: process.env.VITE_HMR_HOST,
            clientPort: process.env.VITE_HMR_PORT ? parseInt(process.env.VITE_HMR_PORT) : undefined,
            protocol: process.env.VITE_HMR_PROTOCOL || 'wss',
          }
        : undefined,
    proxy: {
      '/api/v2': {
        target: proxyTarget,
        changeOrigin: true,
        secure: false,
        timeout: 600000, // 10 minutes for transcription
        agent: proxyAgent,
      },
    },
    watch: {
      ignored: ['**/node_modules/**', '**/.git/**', '**/dist/**', '**/.next/**', '**/.turbo/**'],
      usePolling: false,
    },
  },
  build: {
    sourcemap: !isProduction,
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          // Split heavy/vendor chunks so initial load is smaller
          if (id.includes('node_modules')) {
            // React core in its own chunk - largest dependency, split so main parses faster
            if (id.includes('react-dom') || id.includes('/react/') || id.includes('scheduler')) return 'react-vendor'
            if (id.includes('recharts') || id.includes('d3-')) return 'charts'
            if (id.includes('react-router')) return 'router'
            if (id.includes('@tanstack/react-query')) return 'query'
            if (id.includes('jspdf') || id.includes('html2canvas')) return 'pdf'
            if (id.includes('marked') || id.includes('dompurify')) return 'markdown'
            if (id.includes('zustand')) return 'store'
            if (id.includes('react-hook-form')) return 'forms'
          }
        },
      },
    },
    chunkSizeWarningLimit: 600,
    minify: 'esbuild',
    cssMinify: false, /* PostCSS + cssnano minifies CSS in production */
    target: 'esnext',
  },
})


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
  server: {
    host: '0.0.0.0',
    allowedHosts: [
      'localhost',
      '.mamaope.com',
      'empirico.ai',
      '.empirico.ai',
    ],
    hmr: disableHMR ? false : useCustomHMR ? {
      // Use custom HMR config if provided via env vars (for production)
      host: process.env.VITE_HMR_HOST,
      clientPort: process.env.VITE_HMR_PORT ? parseInt(process.env.VITE_HMR_PORT) : undefined,
      protocol: process.env.VITE_HMR_PROTOCOL || 'wss',
    } : {
      // Default to localhost for local development (no custom config)
      host: 'localhost',
      protocol: 'ws',
    },
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
  // Disable HMR in production builds
  build: {
    sourcemap: !isProduction,
  },
})


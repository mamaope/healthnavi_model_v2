import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

const proxyTarget =
  process.env.VITE_PROXY_TARGET ?? 'http://localhost:8050'

const isProduction = process.env.NODE_ENV === 'production'
// Disable HMR in production or if explicitly disabled
const disableHMR = isProduction || process.env.VITE_DISABLE_HMR === 'true'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    allowedHosts: [
      'empirico.mamaope.com',
      'localhost',
      '.mamaope.com',
    ],
    hmr: disableHMR ? false : {
      host: process.env.VITE_HMR_HOST || 'empirico.mamaope.com',
      clientPort: process.env.VITE_HMR_PORT ? parseInt(process.env.VITE_HMR_PORT) : 443,
      protocol: process.env.VITE_HMR_PROTOCOL || 'wss',
    },
    proxy: {
      '/api/v2': {
        target: proxyTarget,
        changeOrigin: true,
        secure: false,
        timeout: 600000, // 10 minutes for transcription
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


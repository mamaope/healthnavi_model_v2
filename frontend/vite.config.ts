import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

const proxyTarget =
  process.env.VITE_PROXY_TARGET ?? 'http://localhost:8050'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    allowedHosts: [
      'healthnavy.mamaope.com',
      'localhost',
      '.mamaope.com',
    ],
    proxy: {
      '/api/v2': {
        target: proxyTarget,
        changeOrigin: true,
        secure: false,
      },
    },
  },
})


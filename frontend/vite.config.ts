import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: { environment: 'jsdom' },
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8090',
        changeOrigin: true,
        // the Studio refuses a write whose Origin is not its own address
        configure: proxy => proxy.on('proxyReq', request => request.setHeader('origin', 'http://127.0.0.1:8090')),
      },
    },
  },
})

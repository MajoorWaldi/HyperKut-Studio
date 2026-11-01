import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// The node pack that ships the timeline editor: HYPERKUT_VIDEOTOOLS_DIR, else the folder around Studio, else a sibling clone.
const here = (path: string) => fileURLToPath(new URL(path, import.meta.url))
const pack = [process.env.HYPERKUT_VIDEOTOOLS_DIR, here('../../'), here('../../ComfyUI-Majoor-VideoTools')]
  .find(dir => dir && existsSync(`${dir}/web/timeline_edit_panel.js`)) ?? here('../../')

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@videotools-web': `${pack}/web` } },
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

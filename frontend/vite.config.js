import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const backend = 'http://127.0.0.1:8484'

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: '../mcphawk/web/static',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api/live': { target: backend.replace('http', 'ws'), ws: true },
      '/api': backend,
    },
  },
})

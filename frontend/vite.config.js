import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'

// Keep all browser requests same-origin; only the local development proxy
// translates its own Origin to the Python server's existing allowlist.
const target = 'http://127.0.0.1:8765'
const developmentOrigins = new Set(['http://127.0.0.1:5173', 'http://localhost:5173'])
const proxy = Object.fromEntries(['/api', '/media', '/artifacts'].map(path => [path, {
  target,
  changeOrigin: true,
  configure(server) {
    server.on('proxyReq', (request, incoming) => {
      if (developmentOrigins.has(incoming.headers.origin)) request.setHeader('Origin', target)
    })
  },
}]))

export default defineConfig({
  plugins: [vue()],
  server: { host: '127.0.0.1', port: 5173, strictPort: true, proxy },
  build: {
    outDir: fileURLToPath(new URL('../web', import.meta.url)),
    emptyOutDir: true,
    sourcemap: false,
  },
})

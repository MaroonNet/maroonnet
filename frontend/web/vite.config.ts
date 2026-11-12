import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The backend during development: `uv run fastapi dev server/main.py` in backend/.
const BACKEND = 'http://127.0.0.1:8000'
const toBackend = { target: BACKEND, changeOrigin: false }

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // In development the web app and the backend are two servers. The proxy passes these
    // addresses on to the backend, so the browser sees a single server. It keeps the address
    // the browser used, which the backend needs to build the style's tile addresses.
    proxy: {
      '/api': toBackend,
      '/maps': toBackend,
      '/tiles': toBackend,
    },
  },
})

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'  // vite's defineConfig, with the test settings added

// The backend during development: `uv run fastapi dev server/main.py` in backend/.
const BACKEND = 'http://127.0.0.1:8000'
const toBackend = { target: BACKEND, changeOrigin: false }

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
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
  test: {
    environment: 'jsdom',  // a pretend browser, so components can be drawn and pressed in tests
  },
})

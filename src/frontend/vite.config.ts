/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Vite config: https://vite.dev/config/  Vitest config: https://vitest.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],

  // Read .env files from the repo root, so frontend and backend share one .env
  // (see .env.example). Only variables starting with VITE_ reach the browser.
  envDir: '../..',

  server: {
    // Forward /api requests to the FastAPI backend during development, so the
    // frontend can call `/api/...` without CORS issues or hard-coded ports.
    // 127.0.0.1 (not localhost): Node may resolve localhost to IPv6, but uvicorn
    // only listens on IPv4 by default.
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },

  test: {
    // jsdom simulates a browser DOM so components can render in Node.
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.ts'],
  },
})

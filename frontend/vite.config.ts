import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  // Read the repo-root .env so frontend and backend share one file. Vite only exposes
  // VITE_-prefixed variables to the browser, so server secrets stay server-side.
  envDir: '..',
  server: {
    // The FastAPI backend (`finbo serve`) runs on :8000.
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})

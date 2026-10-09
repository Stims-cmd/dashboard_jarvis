import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The API is proxied so the browser sees a single origin (no CORS, strict cookies work).
const apiTarget = process.env.JARVIS_API_URL ?? 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': apiTarget },
    // File events do not cross Docker volumes on Windows: poll instead.
    watch: process.env.VITE_USE_POLLING === 'true' ? { usePolling: true, interval: 300 } : undefined,
  },
})

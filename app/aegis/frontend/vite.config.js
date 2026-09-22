import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Inside docker-compose, 'localhost' would resolve to the frontend container
// itself, not the backend service - VITE_BACKEND_PROXY_TARGET overrides it
// to 'http://backend:8000' there. Host-based (non-docker) dev keeps the
// localhost default.
const backendTarget = process.env.VITE_BACKEND_PROXY_TARGET || 'http://localhost:8000'

// Browser navigations (GET + Accept: text/html) must render the React SPA;
// API calls (POSTs, JSON GETs from fetch) carry a different Accept header
// and fall through to the proxy.
function spaBypass(req) {
  if (req.method === 'GET' && (req.headers.accept || '').includes('text/html')) {
    return '/index.html'
  }
}

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    watch: {
      usePolling: true,
      interval: 300,
    },
    proxy: {
      // /bank hosts BOTH frontend routes and API endpoints.
      // Only non-HTML requests may reach the backend.
      '/bank': {
        target: backendTarget,
        bypass: spaBypass,
      },
      '/ingest': backendTarget,
      // Same collision as /bank: SPA simulator page vs protocol endpoint.
      '/ussd': {
        target: backendTarget,
        bypass: spaBypass,
      },
      '/score': backendTarget,
    }
  }
})

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Inside docker-compose, 'localhost' would resolve to the frontend container
// itself, not the backend service — VITE_BACKEND_PROXY_TARGET overrides it
// to 'http://backend:8000' there. Host-based (non-docker) dev keeps the
// localhost default.
const backendTarget = process.env.VITE_BACKEND_PROXY_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // Bind-mounted source on Windows/Docker doesn't deliver inotify events, so
    // Vite would keep serving stale transformed modules from its in-memory
    // graph. Polling is the reliable option here.
    watch: {
      usePolling: true,
      interval: 300,
    },
    proxy: {
      '/bank': backendTarget,
      '/ingest': backendTarget,
      // The SPA route '/ussd' (the feature-phone simulator page) collides with
      // the backend's USSD endpoint path. Browser navigations (GET text/html)
      // must render the React app; the simulator's POSTs must reach the real
      // protocol-accurate endpoint. Note the USSD protocol contract is the
      // CON/END + accumulated-text shape, not the URL path, so this changes
      // nothing an aggregator depends on.
      '/ussd': {
        target: backendTarget,
        bypass(req) {
          if (req.method === 'GET' && (req.headers.accept || '').includes('text/html')) {
            return '/index.html'
          }
        },
      },
      '/score': backendTarget,
    }
  }
})

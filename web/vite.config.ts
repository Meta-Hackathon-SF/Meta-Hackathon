import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'
import { museChatPlugin } from './museChatPlugin.ts'

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss(), ...(mode === 'fixture' ? [museChatPlugin()] : [])],
  // The normal local app uses the same cookie/session origin and API path as production.
  // Only the explicitly selected fixture mode uses the in-browser test adapters.
  define: mode === 'live' ? {
    'import.meta.env.VITE_CONSTELLATIONS_API': JSON.stringify('/api/v1'),
  } : undefined,
  server: mode === 'live' ? {
    proxy: {
      '/api/v1': {
        target: 'https://constellations-demo-zeta.vercel.app',
        changeOrigin: true,
        secure: true,
      },
    },
  } : undefined,
}))

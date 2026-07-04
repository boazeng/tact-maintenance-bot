import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Frontend on 5210; /api is proxied to the FastAPI backend on 8020.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5210,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8020',
        changeOrigin: true,
      },
    },
  },
})

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    fs: {
      // Allow the dev server to serve files from the repo root (parent of app/).
      // Required so import.meta.glob can resolve ../../../samples/*.sql at runtime.
      allow: ['..'],
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
    include: ['src/**/*.unit.test.{ts,tsx}'],
  },
})

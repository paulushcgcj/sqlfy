import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import tsconfigPaths from 'vite-tsconfig-paths';

// https://vite.dev/config/
export default defineConfig({
  resolve: {
    alias: {
      '@/': new URL('./src/', import.meta.url).pathname,
    },
  },
  plugins: [react(), tsconfigPaths()],
  server: {
    fs: {
      // Allow the dev server to serve files from the repo root (parent of app/).
      // Required so import.meta.glob can resolve ../../../samples/*.sql at runtime.
      allow: ['..'],
    },
  },
  test: {
    alias: {
      '@/': new URL('./src/', import.meta.url).pathname,
    },
    environment: 'jsdom',
    globals: true,
    tsconfig: './tsconfig.test.json',
    setupFiles: ['./src/config/tests/setup.ts'],
    include: ['src/**/*.unit.test.{ts,tsx}'],
  },
});

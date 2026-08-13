/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    target: 'es2022',
    // Marketing build ships to a public Pages host; source maps would expose
    // the full TypeScript surface for no operational gain.
    sourcemap: false,
    // The force-graph bundle is large and only the cascade needs it.
    rollupOptions: {
      output: {
        manualChunks: { graph: ['react-force-graph-2d'] },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}', 'tests/**/*.test.{ts,tsx}'],
  },
});

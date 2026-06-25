import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Standalone Vitest config. Kept separate from vite.config.ts because vitest
// bundles its own vite copy, whose plugin types clash with vite 8 under tsc.
// This file is intentionally excluded from the tsc build (see tsconfig.node).
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})

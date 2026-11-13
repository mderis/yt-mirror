import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

// `./start --dev` sets YTM_PORT. This default is the same as DEV_BACKEND_PORT in `start`.
const backendPort = process.env.YTM_PORT ?? '47800'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      // The browser talks only to this server. API calls are passed on to the backend.
      '/api': { target: `http://127.0.0.1:${backendPort}`, changeOrigin: true },
    },
  },
  build: {
    // Only index.html is built. theme-preview.html is for the development server (R-TH-08).
    outDir: 'dist',
    emptyOutDir: true,
  },
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.test.ts'],
    setupFiles: ['tests/setup.ts'],
    restoreMocks: true,
    // Stylesheets are empty in tests, except the token file: the preview page reads its text.
    css: { include: [/tokens\.css/] },
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,vue}', 'tools/**/*.ts'],
      exclude: [
        'src/**/*.d.ts',
        'src/main.ts',
        'src/design/preview/main.ts',
        'tools/gen-api.ts',
        'tools/theme-lint/cli.ts',
      ],
      reporter: ['text-summary', 'json-summary'],
      // docs/TESTING.md section 3
      thresholds: { lines: 85, branches: 80 },
    },
  },
})

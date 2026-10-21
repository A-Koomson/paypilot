import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

const proxyTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      // Same-origin /api in dev, mirroring the Vercel rewrite used in production.
      '/api': { target: proxyTarget, changeOrigin: false },
    },
  },
  build: { sourcemap: false, target: 'es2022' },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/tests/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
    // jsdom 27 pulls ESM-only css-calc; Node 22.11 needs the experimental loader in worker processes.
    pool: 'forks',
    execArgv: ['--experimental-require-module'],
  },
})

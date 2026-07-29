import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

function normalizeBase(value: string | undefined): string {
  const raw = value?.trim() || '/'
  return raw === '/' ? '/' : `/${raw.replace(/^\/+|\/+$/g, '')}/`
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_API_PROXY_TARGET || 'http://localhost:8000'

  return {
    base: normalizeBase(env.VITE_APP_BASE),
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/api': {
          target,
          changeOrigin: true,
          timeout: 3_600_000,
          proxyTimeout: 3_600_000,
        },
      },
    },
    test: {
      include: ['src/**/*.test.{ts,tsx}'],
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
      css: true,
      coverage: { reporter: ['text', 'html'] },
    },
  }
})

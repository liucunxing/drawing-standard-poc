import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  retries: 0,
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:49174', trace: 'retain-on-failure' },
  webServer: {
    command: 'pnpm build && pnpm preview --host 127.0.0.1 --port 49174 --strictPort',
    port: 49174,
    reuseExistingServer: false,
    timeout: 120_000,
  },
  projects: [
    { name: 'chrome-1366', use: { ...devices['Desktop Chrome'], channel: 'chrome', viewport: { width: 1366, height: 768 } } },
    { name: 'chrome-1920', use: { ...devices['Desktop Chrome'], channel: 'chrome', viewport: { width: 1920, height: 1080 } } },
  ],
})

import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  workers: 1,
  use: { baseURL: process.env.PLAYGROUND_SMOKE_URL || 'http://127.0.0.1:5173', trace: 'off' },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
})

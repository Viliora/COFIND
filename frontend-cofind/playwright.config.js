import { defineConfig, devices } from '@playwright/test'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '..')

/** Port terpisah agar tidak bentrok dengan dev server (5173) / Flask (5000) lokal. */
const E2E_FRONTEND_PORT = process.env.PW_E2E_FRONTEND_PORT || '5174'
const E2E_API_PORT = process.env.PW_E2E_API_PORT || '5055'
const e2eApiOrigin = `http://127.0.0.1:${E2E_API_PORT}`

/**
 * E2E: jalankan dari folder frontend-cofind (`npm run test:e2e`).
 * Playwright men-start Vite + Flask sendiri di port di atas (SQLite, tanpa Postgres dari .env).
 */
const e2eBackendEnv = {
  ...process.env,
  COFIND_DB_BACKEND: 'sqlite',
  DATABASE_URL: '',
  SUPABASE_DB_URL: '',
  VITE_API_BASE: e2eApiOrigin,
  FLASK_RUN_PORT: E2E_API_PORT,
  PORT: E2E_API_PORT,
}

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? 'github' : 'list',
  timeout: 60_000,
  use: {
    baseURL: `http://127.0.0.1:${E2E_FRONTEND_PORT}`,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${E2E_FRONTEND_PORT} --strictPort`,
      url: `http://127.0.0.1:${E2E_FRONTEND_PORT}`,
      cwd: __dirname,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: e2eBackendEnv,
    },
    {
      command: process.platform === 'win32' ? 'python app.py' : 'python3 app.py',
      url: `${e2eApiOrigin}/api/test`,
      cwd: repoRoot,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: e2eBackendEnv,
    },
  ],
})

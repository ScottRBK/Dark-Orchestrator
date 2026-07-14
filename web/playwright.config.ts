import { defineConfig } from '@playwright/test'

const databaseUrl = [
  'postgresql://dark_orchestrator:dark_orchestrator@',
  'localhost:54329/dark_orchestrator_e2e',
].join('')

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  use: {
    baseURL: 'http://127.0.0.1:15173',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: [
        'cd .. &&',
        'uv run python scripts/reset_database.py e2e &&',
        `DARK_ORCH_DATABASE_URL=${databaseUrl}`,
        'DARK_ORCH_HEART_BEAT_INTERVAL=0.05',
        'DARK_ORCH_SCRIPT_ROOT=web/tests/fixtures',
        'uv run uvicorn main:app --host 127.0.0.1 --port 18099',
      ].join(' '),
      port: 18099,
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: [
        'VITE_API_PROXY_TARGET=http://127.0.0.1:18099',
        'npm run dev -- --host 127.0.0.1 --port 15173',
      ].join(' '),
      port: 15173,
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
})

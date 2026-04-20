import { defineConfig } from '@playwright/test';
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  projects: [
    {
      name: 'contract',
      use: { baseURL: 'http://localhost:5181' },
      testDir: resolve(__dirname, 'tests/contract'),
    },
  ],
  use: {
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  reporter: [['list'], ['html', { open: 'never' }]],
  webServer: [
    {
      command: 'node ../../tests/ui-shared/mock-api-server.mjs',
      url: 'http://localhost:8001',
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'npm run dev -- --port 5181',
      env: { API_BASE_URL: 'http://localhost:8001' },
      url: 'http://localhost:5181',
      reuseExistingServer: !process.env.CI,
    },
  ],
});

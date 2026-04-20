import { defineConfig } from '@playwright/test';
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';
import { BASE_URLS } from '../../tests/ui-shared/config';

const __dirname = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  projects: [
    {
      name: 'smoke',
      use: { baseURL: BASE_URLS.dashboard },
      testDir: resolve(__dirname, 'tests/smoke'),
    },
  ],
  use: {
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  reporter: [['list'], ['html', { open: 'never' }]],
});

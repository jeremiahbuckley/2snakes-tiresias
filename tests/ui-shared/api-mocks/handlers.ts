import type { Page } from '@playwright/test';
import { BASE_URLS } from '../config';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

const pathToMockFile: Record<string, string> = {
  // Add entries here as you build the contract suite.
  // Key: API pathname (e.g. '/auth/me')
  // Value: filename inside api-mocks/responses/ (e.g. 'auth-me.json')
};

export async function registerApiMocks(page: Page): Promise<void> {
  await page.route(`${BASE_URLS.api}/**`, async (route) => {
    const url = new URL(route.request().url());
    const mockFilename = pathToMockFile[url.pathname];
    if (mockFilename) {
      await route.fulfill({
        path: resolve(__dirname, 'responses', mockFilename),
        contentType: 'application/json',
      });
    } else {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: `no mock registered for ${route.request().method()} ${url.pathname} — add it to pathToMockFile in handlers.ts` }),
      });
    }
  });
}

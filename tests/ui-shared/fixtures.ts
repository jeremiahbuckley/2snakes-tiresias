import { test as base, type Page } from '@playwright/test';
import { TEST_USER, assertTestUserConfigured } from './config';
import { login } from './helpers/auth';

export const test = base.extend<{
  authedPage: Page;
  guestPage: Page;
}>({
  authedPage: async ({ page }, use) => {
    assertTestUserConfigured();
    await login(page, TEST_USER.email, TEST_USER.password);
    await use(page);
  },
  guestPage: async ({ page }, use) => {
    await use(page);
  },
});

export const contractTest = base.extend<{
  authedPage: Page;
  guestPage: Page;
}>({
  authedPage: async ({ page }, use) => {
    // Use the dev bypass (no API call) so contract tests work without a real backend.
    await page.goto('/login');
    await page.getByRole('button', { name: /continue with mock data/i }).click();
    await page.waitForURL('/dashboard');
    await use(page);
  },
  guestPage: async ({ page }, use) => {
    await use(page);
  },
});

export { expect } from '@playwright/test';

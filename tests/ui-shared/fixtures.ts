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
    // Mock API server accepts any credentials — no real user env vars needed.
    await login(page, 'test@contract.local', 'contract-password');
    await use(page);
  },
  guestPage: async ({ page }, use) => {
    await use(page);
  },
});

export { expect } from '@playwright/test';

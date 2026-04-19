import { test as base, type Page } from '@playwright/test';
import { TEST_USER, assertTestUserConfigured } from './config';
import { login } from './helpers/auth';
import { registerApiMocks } from './api-mocks/handlers';

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

// contractTest registers API mocks before any page interaction.
// When writing the first contract test that uses authedPage, you must also
// add a mock for the POST /auth/login endpoint in handlers.ts — otherwise
// the login() call inside authedPage will try to hit the real API.
export const contractTest = base.extend<{
  authedPage: Page;
  guestPage: Page;
}>({
  authedPage: async ({ page }, use) => {
    assertTestUserConfigured();
    await registerApiMocks(page);
    await login(page, TEST_USER.email, TEST_USER.password);
    await use(page);
  },
  guestPage: async ({ page }, use) => {
    await registerApiMocks(page);
    await use(page);
  },
});

export { expect } from '@playwright/test';

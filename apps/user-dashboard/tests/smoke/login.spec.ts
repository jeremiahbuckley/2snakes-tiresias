import { test, expect } from '../../../../tests/ui-shared/fixtures';
import { TEST_USER, assertTestUserConfigured } from '../../../../tests/ui-shared/config';

test.describe('login', () => {
  test('unauthenticated request redirects to /login', async ({ guestPage: page }) => {
    await page.goto('/dashboard');
    await page.waitForURL(/\/login/);
    await expect(page).toHaveURL(/login/);
  });

  test('valid credentials land on /dashboard', async ({ guestPage: page }) => {
    assertTestUserConfigured();
    await page.goto('/login');
    await page.getByLabel('Email').fill(TEST_USER.email);
    await page.getByLabel('Password').fill(TEST_USER.password);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.waitForURL('**/dashboard');
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  });
});

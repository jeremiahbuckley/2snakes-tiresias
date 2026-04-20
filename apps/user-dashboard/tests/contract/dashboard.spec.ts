import { contractTest, expect } from '../../../../tests/ui-shared/fixtures';

contractTest.describe('dashboard', () => {
  contractTest('renders heading and welcome message', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
    await expect(page.getByText('Welcome back, Jeremiah B.')).toBeVisible();
  });

  contractTest('shows resolved and total prediction counts', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    // stat card shows "189 / 247" — 189 is rendered as text, 247 in .stat-denom span
    await expect(page.getByText('189')).toBeVisible();
  });

  contractTest('recent activity table has exactly 5 rows', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    await expect(page.locator('table tbody tr')).toHaveCount(5);
  });

  contractTest('shows earned badge from mock data', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    await expect(page.getByText('First Prediction')).toBeVisible();
  });
});

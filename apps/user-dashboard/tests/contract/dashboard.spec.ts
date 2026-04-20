import { contractTest, expect } from '../../../../tests/ui-shared/fixtures';

contractTest.describe('dashboard', () => {
  contractTest('renders heading and welcome message', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
    await expect(page.getByText('Welcome back, Jeremiah B.')).toBeVisible();
  });

  contractTest('shows resolved prediction count from mock data', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    // mock dashboard.json has resolved_predictions: 6, total_predictions: 10 → "60% resolved"
    await expect(page.getByText('60% resolved')).toBeVisible();
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

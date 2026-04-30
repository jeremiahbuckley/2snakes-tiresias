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

  contractTest('tag dropdown renders on dashboard', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('#tag-filter')).toBeVisible();
  });

  contractTest('selecting a tag on dashboard updates URL and shows indicator', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');
    await page.selectOption('#tag-filter', 'politics');
    await expect(page).toHaveURL(/tag=politics/);
    await expect(page.locator('.tag-indicator')).toContainText('politics');
  });

  contractTest('refresh data button is visible in dashboard header', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('button', { name: /refresh data/i })).toBeVisible();
  });

  contractTest('clicking refresh button shows syncing state', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');
    await page.getByRole('button', { name: /refresh data/i }).click();
    await expect(page.getByRole('button', { name: /syncing/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /syncing/i })).toBeDisabled();
  });
});

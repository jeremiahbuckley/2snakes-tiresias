import { contractTest, expect } from '../../../../tests/ui-shared/fixtures';

contractTest.describe('stats', () => {
  contractTest('renders heading and Brier score value', async ({ authedPage: page }) => {
    await page.goto('/stats');
    await expect(page.getByRole('heading', { name: 'Stats' })).toBeVisible();
    await expect(page.getByText('0.162')).toBeVisible();
  });

  contractTest('shows calibration chart section', async ({ authedPage: page }) => {
    await page.goto('/stats');
    await expect(page.getByRole('heading', { name: 'Calibration Curve' })).toBeVisible();
  });

  contractTest('shows Brier timeline chart section', async ({ authedPage: page }) => {
    await page.goto('/stats');
    await expect(page.getByRole('heading', { name: 'Brier Score Over Time' })).toBeVisible();
  });

  contractTest('tag dropdown renders when available_tags returned', async ({ authedPage: page }) => {
    await page.goto('/stats');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('#tag-filter')).toBeVisible();
  });

  contractTest('selecting a tag in dropdown updates URL', async ({ authedPage: page }) => {
    await page.goto('/stats');
    await page.waitForLoadState('networkidle');
    await page.selectOption('#tag-filter', 'politics');
    await expect(page).toHaveURL(/tag=politics/);
  });

  contractTest('tag indicator shows when tag is selected', async ({ authedPage: page }) => {
    await page.goto('/stats?tag=crypto');
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('Showing: crypto')).toBeVisible();
  });
});

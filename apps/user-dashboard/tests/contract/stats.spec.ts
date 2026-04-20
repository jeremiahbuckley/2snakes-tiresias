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
});

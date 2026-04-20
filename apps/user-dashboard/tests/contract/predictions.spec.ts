import { contractTest, expect } from '../../../../tests/ui-shared/fixtures';

contractTest.describe('predictions', () => {
  contractTest('initial render shows all 10 predictions', async ({ authedPage: page }) => {
    await page.goto('/predictions');
    await expect(page.getByRole('heading', { name: 'Predictions' })).toBeVisible();
    await expect(page.locator('table tbody tr')).toHaveCount(10);
  });

  contractTest('source filter — kalshi shows 3 predictions', async ({ authedPage: page }) => {
    await page.goto('/predictions?source=kalshi');
    await expect(page.locator('table tbody tr')).toHaveCount(3);
  });

  contractTest('status filter — resolved shows 6 predictions', async ({ authedPage: page }) => {
    await page.goto('/predictions?status=resolved');
    await expect(page.locator('table tbody tr')).toHaveCount(6);
  });

  contractTest('sort — oldest first puts Ethereum ETF row first', async ({ authedPage: page }) => {
    await page.goto('/predictions?sort=date_asc');
    await expect(page.locator('table tbody tr').first()).toContainText('Ethereum ETF');
  });
});

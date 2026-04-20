import { contractTest, expect } from '../../../../tests/ui-shared/fixtures';

contractTest.describe('predictions', () => {
  contractTest('initial render shows predictions from mock data', async ({ authedPage: page }) => {
    await page.goto('/predictions');
    await expect(page.getByRole('heading', { name: 'Predictions' })).toBeVisible();
    await expect(page.locator('table tbody tr')).toHaveCount(5);
  });

  contractTest('source filter tab updates page URL', async ({ authedPage: page }) => {
    await page.goto('/predictions');
    // Platform tabs are in the filter bar; use exact text within .source-tabs to avoid ambiguity
    await page.locator('.filter-bar .tab', { hasText: 'kalshi' }).click();
    await expect(page).toHaveURL(/source=kalshi/);
  });

  contractTest('status filter tab updates page URL', async ({ authedPage: page }) => {
    await page.goto('/predictions');
    await page.getByRole('button', { name: 'Resolved' }).click();
    await expect(page).toHaveURL(/status=resolved/);
  });

  contractTest('sort — date_asc param is accepted and table renders', async ({ authedPage: page }) => {
    await page.goto('/predictions?sort=date_asc');
    // mock returns fixed data regardless of sort param; verify table still renders
    await expect(page.locator('table tbody tr')).toHaveCount(5);
    await expect(page.locator('table tbody tr').first()).toContainText('Will the Fed cut rates');
  });
});

import { contractTest, expect } from '../../../../tests/ui-shared/fixtures';

contractTest.describe('devBypass banner', () => {
  contractTest('shows mock data banner after devBypass login', async ({ guestPage: page }) => {
    await page.goto('/login');
    await page.getByRole('button', { name: /continue with mock data/i }).click();
    await page.waitForURL('/dashboard');
    await expect(page.getByText(/mock data mode/i)).toBeVisible();
  });

  contractTest('does not show banner after normal login', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    await expect(page.getByText(/mock data mode/i)).not.toBeVisible();
  });
});

import { contractTest, expect } from '../../../../tests/ui-shared/fixtures';

contractTest.describe('settings', () => {
  contractTest('profile section shows display name from auth response', async ({ authedPage: page }) => {
    await page.goto('/settings');
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
    await expect(page.getByLabel('Display Name')).toHaveValue('Jeremiah B.');
  });

  contractTest('linked accounts show correct connected/disconnected state', async ({ authedPage: page }) => {
    await page.goto('/settings');
    // Kalshi is linked — identifier is visible
    await expect(page.getByText('jeremiah_b_kalshi')).toBeVisible();
    // Metaculus is not linked
    await expect(
      page.locator('.platform-item', { hasText: 'Metaculus' }).getByText('Not linked')
    ).toBeVisible();
  });

  contractTest('notification prefs checkboxes reflect mock response', async ({ authedPage: page }) => {
    await page.goto('/settings');
    // email_on_resolution: true → checked
    await expect(page.getByRole('checkbox', { name: /market resolutions/i })).toBeChecked();
    // email_on_rank_change: false → unchecked
    await expect(page.getByRole('checkbox', { name: /leaderboard rank changes/i })).not.toBeChecked();
  });
});

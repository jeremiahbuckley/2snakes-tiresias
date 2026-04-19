import type { Page } from '@playwright/test';

export async function login(page: Page, email: string, password: string): Promise<void> {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: /log in/i }).click();
  await page.waitForURL('/dashboard');
}

export async function logout(page: Page): Promise<void> {
  await page.getByRole('button', { name: /log out/i }).click();
  await page.waitForURL('/login');
}

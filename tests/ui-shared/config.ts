import dotenv from 'dotenv';
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const result = dotenv.config({ path: resolve(__dirname, '../../.env.test') });
if (result.error && (result.error as NodeJS.ErrnoException)?.code !== 'ENOENT') {
  throw result.error;
}

export const BASE_URLS = {
  dashboard: process.env.DASHBOARD_URL ?? 'http://localhost:5173',
  leaderboard: process.env.LEADERBOARD_URL ?? 'http://localhost:5174',
  profile: process.env.PROFILE_URL ?? 'http://localhost:5175',
  api: process.env.API_BASE_URL ?? 'http://localhost:8000',
} as const;

export const TEST_USER = {
  email: process.env.TEST_USER_EMAIL ?? '',
  password: process.env.TEST_USER_PASSWORD ?? '',
} as const;

export function assertTestUserConfigured(): void {
  if (!TEST_USER.email || !TEST_USER.password) {
    throw new Error(
      'TEST_USER_EMAIL and TEST_USER_PASSWORD must be set. ' +
      'Copy .env.test.example to .env.test and fill in credentials.'
    );
  }
}

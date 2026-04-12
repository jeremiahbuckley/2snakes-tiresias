import { redirect, fail } from '@sveltejs/kit';
import { login } from '$lib/api.js';

/** @type {import('./$types').Actions} */
export const actions = {
  /** Real login: POST /auth/login → set JWT cookie. */
  login: async ({ request, cookies, url }) => {
    const data = await request.formData();
    const email = data.get('email')?.toString() ?? '';
    const password = data.get('password')?.toString() ?? '';

    try {
      const result = await login(email, password);
      cookies.set('tiresias_token', result.access_token, {
        path: '/',
        httpOnly: true,
        sameSite: 'lax',
        maxAge: 60 * 60 * 24 * 7, // 7 days
        secure: process.env.NODE_ENV === 'production',
      });
    } catch (err) {
      if (err.status === 401) {
        return fail(400, { error: 'Incorrect email or password.' });
      }
      return fail(500, { error: 'Could not reach the API. Is the server running?' });
    }

    const redirectTo = url.searchParams.get('redirect') ?? '/dashboard';
    throw redirect(303, redirectTo);
  },

  /**
   * Dev bypass: sets a placeholder token so the dashboard is reachable
   * while the real auth backend is still being built.
   */
  devBypass: async ({ cookies, url }) => {
    cookies.set('tiresias_token', 'dev-mock-token', {
      path: '/',
      httpOnly: true,
      sameSite: 'lax',
      maxAge: 60 * 60 * 24,
    });
    const redirectTo = url.searchParams.get('redirect') ?? '/dashboard';
    throw redirect(303, redirectTo);
  },

  /** Sign out: clear the token cookie. */
  logout: async ({ cookies }) => {
    cookies.delete('tiresias_token', { path: '/' });
    throw redirect(303, '/login');
  },
};

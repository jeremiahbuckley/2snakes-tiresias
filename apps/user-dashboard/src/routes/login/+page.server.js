import { redirect, fail } from '@sveltejs/kit';

const API_BASE = process.env.API_BASE_URL ?? 'http://localhost:8000';

/** @type {import('./$types').Actions} */
export const actions = {
  /** Real login: POST /auth/login → set JWT cookie. */
  login: async ({ request, cookies, url, fetch }) => {
    const data = await request.formData();
    const email = data.get('email')?.toString() ?? '';
    const password = data.get('password')?.toString() ?? '';

    let result;
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (res.status === 401) return fail(400, { error: 'Incorrect email or password.' });
      if (!res.ok) throw new Error(`API ${res.status}`);
      result = await res.json();
    } catch {
      return fail(500, { error: 'Could not reach the API. Is the server running?' });
    }
    cookies.set('tiresias_token', result.access_token, {
      path: '/',
      httpOnly: true,
      sameSite: 'lax',
      maxAge: 60 * 60 * 24 * 7,
      secure: process.env.NODE_ENV === 'production',
    });

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

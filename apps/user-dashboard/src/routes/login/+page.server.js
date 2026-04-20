import { redirect, fail } from '@sveltejs/kit';

const API_BASE = process.env.API_BASE_URL ?? 'http://localhost:8000';

/** @type {import('./$types').PageServerLoad} */
export async function load() {
  return { devBypassEnabled: process.env.DEV_BYPASS_ENABLED === 'true' };
}

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

  devBypass: async ({ cookies, url }) => {
    if (process.env.DEV_BYPASS_ENABLED !== 'true') {
      return fail(403, { error: 'Dev bypass is not enabled.' });
    }
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

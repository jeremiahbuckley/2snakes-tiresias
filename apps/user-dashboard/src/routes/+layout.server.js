import { redirect } from '@sveltejs/kit';

const PUBLIC_ROUTES = ['/login', '/register'];
const API_BASE = process.env.API_BASE_URL ?? 'http://localhost:8000';
const DEV_TOKEN = 'dev-mock-token';

/** @type {import('./$types').LayoutServerLoad} */
export async function load({ url, cookies, fetch }) {
  const path = url.pathname;

  if (PUBLIC_ROUTES.some((r) => path.startsWith(r))) {
    return {};
  }

  const token = cookies.get('tiresias_token');

  if (!token) {
    throw redirect(303, `/login?redirect=${encodeURIComponent(path)}`);
  }

  if (token === DEV_TOKEN && process.env.DEV_BYPASS_ENABLED === 'true') {
    return {
      token,
      isMockSession: true,
      user: {
        id: 'dev',
        username: 'dev',
        display_name: 'Dev User',
        email: 'dev@localhost',
        bio: null,
        avatar_url: null,
        social_links: {},
      },
    };
  }

  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    cookies.delete('tiresias_token', { path: '/' });
    throw redirect(303, `/login?redirect=${encodeURIComponent(path)}`);
  }

  const user = await res.json();
  return { token, user };
}

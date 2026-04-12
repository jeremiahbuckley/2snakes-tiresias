import { redirect } from '@sveltejs/kit';

const PUBLIC_ROUTES = ['/login'];
const API_BASE = process.env.API_BASE_URL ?? 'http://localhost:8000';

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

  // Validate the token and fetch the current user in one call.
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    // Token expired or invalid — clear the cookie and send to login.
    cookies.delete('tiresias_token', { path: '/' });
    throw redirect(303, `/login?redirect=${encodeURIComponent(path)}`);
  }

  const user = await res.json();
  // token and user are available to all child pages via data.token / data.user
  return { token, user };
}

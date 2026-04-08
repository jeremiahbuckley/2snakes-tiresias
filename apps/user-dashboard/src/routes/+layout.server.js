import { redirect } from '@sveltejs/kit';

const PUBLIC_ROUTES = ['/login'];

/** @type {import('./$types').LayoutServerLoad} */
export async function load({ url, cookies }) {
  const path = url.pathname;

  // Allow login and any other public routes through without auth
  if (PUBLIC_ROUTES.some((r) => path.startsWith(r))) {
    return {};
  }

  const token = cookies.get('tiresias_token');

  if (!token) {
    throw redirect(303, `/login?redirect=${encodeURIComponent(path)}`);
  }

  // TODO: validate the token against GET /auth/me once the backend is live.
  // For now we trust the cookie's presence as sufficient for development.
  // const user = await getMe(token).catch(() => null);
  // if (!user) {
  //   cookies.delete('tiresias_token', { path: '/' });
  //   throw redirect(303, '/login');
  // }

  return { token };
}

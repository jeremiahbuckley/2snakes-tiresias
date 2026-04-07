import { PUBLIC_API_BASE_URL } from '$env/static/public';
import { error } from '@sveltejs/kit';

/** @type {import('./$types').PageServerLoad} */
export async function load({ params }) {
  const { username } = params;

  // TODO: replace with real fetch once api-gateway /users/:username/profile is implemented
  // const res = await fetch(`${PUBLIC_API_BASE_URL}/users/${username}/profile`);
  // if (!res.ok) throw error(404, 'Profile not found');
  // return await res.json();

  return { username };
}

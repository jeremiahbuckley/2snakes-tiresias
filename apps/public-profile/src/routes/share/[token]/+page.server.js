import { error } from '@sveltejs/kit';

const API_BASE = process.env.API_BASE_URL ?? 'http://localhost:8000';

/** @type {import('./$types').PageServerLoad} */
export async function load({ params, url }) {
  const { token } = params;
  const tag = url.searchParams.get('tag') ?? '';

  const qs = tag ? `?tag=${encodeURIComponent(tag)}` : '';

  let res;
  try {
    res = await fetch(`${API_BASE}/auth/share/${token}${qs}`);
  } catch {
    throw error(503, 'Service unavailable — please try again shortly.');
  }

  if (res.status === 404) throw error(404, 'This share link is not found or has expired.');
  if (!res.ok) throw error(500, 'Could not load shared profile.');

  const shareData = await res.json();
  return { shareData, tagFilter: tag };
}

import { error } from '@sveltejs/kit';

const API_BASE = process.env.API_BASE_URL ?? 'http://localhost:8000';

/** @type {import('./$types').PageServerLoad} */
export async function load({ params }) {
  const { token } = params;

  let shareData;
  try {
    const res = await fetch(`${API_BASE}/auth/share/${token}`);
    if (res.status === 404) {
      throw error(404, 'This share link is not found or has expired.');
    }
    if (!res.ok) {
      throw error(500, 'Could not load shared profile.');
    }
    shareData = await res.json();
  } catch (e) {
    if (e?.status) throw e;
    throw error(503, 'Service unavailable — please try again shortly.');
  }

  return { shareData };
}

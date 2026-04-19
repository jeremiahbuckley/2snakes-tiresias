import { error } from '@sveltejs/kit';

/** @type {import('./$types').PageServerLoad} */
export async function load({ params }) {
  const { token } = params;

  // TODO: replace with real fetch once api-gateway /auth/share/:token is implemented
  // const API_BASE = process.env.API_BASE_URL ?? 'http://localhost:8000';
  // try {
  //   const res = await fetch(`${API_BASE}/auth/share/${token}`);
  //   if (res.status === 404) throw error(404, 'This share link is not found or has expired.');
  //   if (!res.ok)            throw error(500, 'Could not load shared profile.');
  //   return { shareData: await res.json() };
  // } catch (e) {
  //   if (e?.status) throw e;
  //   throw error(503, 'Service unavailable — please try again shortly.');
  // }

  // --- Mock data (mirrors the shape /auth/share/:token will return) ---
  // Treat the token `expired_xyz` as a 404 so the error UI can be previewed.
  if (token === 'expired_xyz') {
    throw error(404, 'This share link is not found or has expired.');
  }

  return {
    shareData: {
      label: 'Jeremiah B.',
      show_scores: true,
      show_badges: true,
      public_profile_only: false,
      scores: {
        total_predictions: 247,
        resolved_predictions: 189,
        mean_brier_score: 0.162,
        brier_skill_score: 0.237,
        calibration_score: 0.91,
        accuracy: 0.72,
        last_scored_at: '2026-04-07T15:23:00Z',
      },
    },
  };
}

import { getDashboard } from '$lib/api.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent }) {
  const { user, token } = await parent();
  const data = await getDashboard(user.id, token);
  return {
    user: data.user,
    score: data.score,
    badges: data.badges,
    recentPredictions: data.recent_predictions,
  };
}

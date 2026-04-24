import { getDashboard } from '$lib/api.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent }) {
  const { user, token, isMockSession } = await parent();
  if (isMockSession) {
    return {
      user,
      score: { total_predictions: 0, resolved_predictions: 0, mean_brier_score: null, brier_skill_score: null, calibration_score: null, accuracy: null, last_scored_at: null, per_source: {}, per_domain: {} },
      badges: [],
      recentPredictions: [],
    };
  }
  const data = await getDashboard(user.id, token);
  return {
    user: data.user,
    score: data.score,
    badges: data.badges,
    recentPredictions: data.recent_predictions,
  };
}

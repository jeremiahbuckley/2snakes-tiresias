import { getUserStats } from '$lib/api.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent, url }) {
  const { user, token, isMockSession } = await parent();
  const tag = url.searchParams.get('tag') ?? '';
  if (isMockSession) {
    return {
      score: { total_predictions: 0, resolved_predictions: 0, mean_brier_score: null, brier_skill_score: null, calibration_score: null, accuracy: null, last_scored_at: null, per_source: {}, per_domain: {} },
      calibration: [],
      brierTimeline: [],
      availableTags: ['crypto', 'economics', 'politics', 'tech'],
      tagFilter: tag,
    };
  }
  const data = await getUserStats(user.id, token, { tag });
  return {
    score: data.score,
    calibration: data.calibration,
    brierTimeline: data.brier_timeline,
    availableTags: data.available_tags ?? [],
    tagFilter: tag,
  };
}

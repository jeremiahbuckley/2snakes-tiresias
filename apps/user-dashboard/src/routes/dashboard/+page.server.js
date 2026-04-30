import { getDashboard } from '$lib/api.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent, url }) {
  const { user, token, isMockSession } = await parent();
  const tag = url.searchParams.get('tag') ?? '';
  if (isMockSession) {
    return {
      user,
      token,
      score: { total_predictions: 0, resolved_predictions: 0, mean_brier_score: null, brier_skill_score: null, calibration_score: null, accuracy: null, last_scored_at: null, per_source: {}, per_domain: {} },
      badges: [],
      recentPredictions: [],
      availableTags: ['politics', 'crypto'],
      tagFilter: tag,
      lastSyncedAt: null,
      syncStatus: [],
    };
  }
  const data = await getDashboard(user.id, token, { tag });
  return {
    user: data.user,
    token,
    score: data.score,
    badges: data.badges,
    recentPredictions: data.recent_predictions,
    availableTags: data.available_tags ?? [],
    tagFilter: tag,
    lastSyncedAt: data.last_synced_at ?? null,
    syncStatus: data.sync_status ?? [],
  };
}

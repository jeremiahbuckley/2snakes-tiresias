import { getUserStats } from '$lib/api.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent }) {
  const { user, token } = await parent();
  const data = await getUserStats(user.id, token);
  return {
    score: data.score,
    calibration: data.calibration,
    brierTimeline: data.brier_timeline,
  };
}

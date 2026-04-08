import { mockScore, mockCalibration, mockBrierTimeline } from '$lib/mock.js';

/** @type {import('./$types').PageServerLoad} */
export async function load() {
  // TODO: replace with real API calls once api-gateway is live:
  //   const dashboard = await getDashboard(userId, token);
  //   const calibration = dashboard.calibration_buckets;
  //   const timeline = dashboard.brier_timeline;

  return {
    score: mockScore,
    calibration: mockCalibration,
    brierTimeline: mockBrierTimeline,
  };
}

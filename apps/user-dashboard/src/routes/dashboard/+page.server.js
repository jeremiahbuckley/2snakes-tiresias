import { mockUser, mockScore, mockBadges, mockPredictions } from '$lib/mock.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ cookies }) {
  const token = cookies.get('tiresias_token');

  // TODO: replace with real API calls once api-gateway is live:
  //   const user   = await getMe(token);
  //   const dashboard = await getDashboard(user.user_id, token);

  const recentPredictions = mockPredictions
    .slice()
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5);

  return {
    user: mockUser,
    score: mockScore,
    badges: mockBadges,
    recentPredictions,
  };
}

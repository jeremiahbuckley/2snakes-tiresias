import { mockPredictions } from '$lib/mock.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ url }) {
  // TODO: replace with real API call once api-gateway is live:
  //   const predictions = await getDashboard(userId, token).then(d => d.predictions);

  const sourceFilter = url.searchParams.get('source') ?? 'all';
  const statusFilter = url.searchParams.get('status') ?? 'all';
  const sortBy = url.searchParams.get('sort') ?? 'date_desc';

  let predictions = [...mockPredictions];

  if (sourceFilter !== 'all') {
    predictions = predictions.filter((p) => p.source === sourceFilter);
  }

  if (statusFilter === 'resolved') {
    predictions = predictions.filter((p) => p.outcome !== null);
  } else if (statusFilter === 'pending') {
    predictions = predictions.filter((p) => p.outcome === null);
  }

  if (sortBy === 'date_desc') {
    predictions.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  } else if (sortBy === 'date_asc') {
    predictions.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
  } else if (sortBy === 'brier_asc') {
    predictions.sort((a, b) => {
      if (a.brier_score == null) return 1;
      if (b.brier_score == null) return -1;
      return a.brier_score - b.brier_score;
    });
  } else if (sortBy === 'brier_desc') {
    predictions.sort((a, b) => {
      if (a.brier_score == null) return 1;
      if (b.brier_score == null) return -1;
      return b.brier_score - a.brier_score;
    });
  }

  return {
    predictions,
    filters: { sourceFilter, statusFilter, sortBy },
    totals: {
      all: mockPredictions.length,
      resolved: mockPredictions.filter((p) => p.outcome !== null).length,
      pending: mockPredictions.filter((p) => p.outcome === null).length,
    },
  };
}

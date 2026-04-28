import { getPredictions } from '$lib/api.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent, url }) {
  const { user, token, isMockSession } = await parent();
  const source = url.searchParams.get('source') ?? '';
  const status = url.searchParams.get('status') ?? '';
  const sort   = url.searchParams.get('sort')   ?? 'date_desc';
  const tag    = url.searchParams.get('tag')    ?? '';
  const filters = {
    sourceFilter: source || 'all',
    statusFilter: status || 'all',
    sortBy: sort,
    tagFilter: tag,
  };
  if (isMockSession) {
    return {
      predictions: [],
      totals: { all: 0, resolved: 0, pending: 0 },
      availableTags: ['crypto', 'economics', 'politics', 'tech'],
      filters,
    };
  }
  const data = await getPredictions(user.id, token, { source, status, sort, tag });
  return {
    predictions: data.predictions,
    totals: data.totals,
    availableTags: data.available_tags ?? [],
    filters,
  };
}

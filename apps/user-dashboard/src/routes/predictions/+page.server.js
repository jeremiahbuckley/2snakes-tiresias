import { getPredictions } from '$lib/api.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent, url }) {
  const { user, token } = await parent();
  const source = url.searchParams.get('source') ?? '';
  const status = url.searchParams.get('status') ?? '';
  const sort   = url.searchParams.get('sort')   ?? 'date_desc';
  const data = await getPredictions(user.id, token, { source, status, sort });
  return {
    predictions: data.predictions,
    totals: data.totals,
    filters: {
      sourceFilter: source || 'all',
      statusFilter: status || 'all',
      sortBy: sort,
    },
  };
}

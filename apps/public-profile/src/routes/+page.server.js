/** @type {import('./$types').PageServerLoad} */
export async function load() {
  // TODO: replace with real fetch once api-gateway /profiles/featured is implemented
  // const API_BASE = process.env.API_BASE_URL ?? 'http://localhost:8000';
  // const res = await fetch(`${API_BASE}/profiles/featured`);
  // if (!res.ok) throw error(500, 'Could not load featured profiles.');
  // return await res.json();

  // --- Mock data ---
  return {
    featured: [
      {
        username: 'jeremiah_b',
        display_name: 'Jeremiah B.',
        brier_skill_score: 0.237,
        resolved_predictions: 189,
        platforms: ['kalshi', 'polymarket', 'manifold', 'metaculus'],
      },
      {
        username: 'cassandra_t',
        display_name: 'Cassandra T.',
        brier_skill_score: 0.341,
        resolved_predictions: 412,
        platforms: ['kalshi', 'polymarket', 'manifold', 'metaculus'],
      },
      {
        username: 'delphi_oracle',
        display_name: 'Delphi',
        brier_skill_score: 0.318,
        resolved_predictions: 298,
        platforms: ['polymarket', 'manifold', 'metaculus'],
      },
    ],
    demo_share_token: 'demo_abc123',
  };
}

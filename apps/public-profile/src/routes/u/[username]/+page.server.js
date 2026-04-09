import { PUBLIC_API_BASE_URL } from '$env/static/public';
import { error } from '@sveltejs/kit';

/** @type {import('./$types').PageServerLoad} */
export async function load({ params }) {
  const { username } = params;

  // TODO: replace with real fetch once api-gateway /users/:username/profile is implemented
  // const res = await fetch(`${PUBLIC_API_BASE_URL}/users/${username}/profile`);
  // if (!res.ok) throw error(404, 'Profile not found');
  // return await res.json();

  // --- Mock data (mirrors the shape api-gateway will return) ---
  return {
    user: {
      id: 'usr_abc123',
      username,
      display_name: 'Jeremiah B.',
      bio: 'Forecaster tracking markets across Kalshi, Polymarket, Manifold, and Metaculus.',
      avatar_url: null,
      social_links: {
        twitter: 'jeremiahb',
        kalshi: 'jeremiah_b_kalshi',
        polymarket: '0xabc123',
        manifold: 'JeremiahB',
        metaculus: null,
        website: null,
      },
      created_at: '2024-09-01T00:00:00Z',
    },
    score: {
      total_predictions: 247,
      resolved_predictions: 189,
      mean_brier_score: 0.162,
      brier_skill_score: 0.237,
      calibration_score: 0.91,
      accuracy: 0.72,
      last_scored_at: '2026-04-07T15:23:00Z',
      per_source: {
        kalshi: 0.148,
        polymarket: 0.171,
        manifold: 0.155,
        metaculus: 0.183,
      },
    },
    badges: [
      {
        id: 'first-prediction',
        name: 'First Prediction',
        description: 'Made at least one resolved prediction.',
        earned: true,
        earned_at: '2024-09-14T10:00:00Z',
        icon: '🎯',
      },
      {
        id: 'ten-predictions',
        name: 'Getting Started',
        description: 'Made at least 10 resolved predictions.',
        earned: true,
        earned_at: '2024-10-01T10:00:00Z',
        icon: '🌱',
      },
      {
        id: 'hundred-predictions',
        name: 'Prolific Forecaster',
        description: 'Made at least 100 resolved predictions.',
        earned: true,
        earned_at: '2025-03-15T10:00:00Z',
        icon: '📊',
      },
      {
        id: 'above-baseline',
        name: 'Better Than Coin Flip',
        description: 'Brier Skill Score > 0 (better than random).',
        earned: true,
        earned_at: '2025-01-08T10:00:00Z',
        icon: '🪙',
      },
      {
        id: 'multi-platform',
        name: 'Cross-Platform Forecaster',
        description: 'Resolved predictions on 3 or more platforms.',
        earned: true,
        earned_at: '2025-06-01T10:00:00Z',
        icon: '🌐',
      },
      {
        id: 'well-calibrated',
        name: 'Well Calibrated',
        description: 'Expected Calibration Error below 0.05 with 50+ predictions.',
        earned: false,
        earned_at: null,
        icon: '⚖️',
      },
    ],
    recentPredictions: [
      {
        id: 'pred_001',
        market_title: 'Will the Fed cut rates before June 2026?',
        source: 'kalshi',
        probability: 0.72,
        outcome: 'yes',
        brier_score: 0.0784,
        resolved_at: '2026-03-20T18:00:00Z',
      },
      {
        id: 'pred_002',
        market_title: 'Will Bitcoin exceed $120k in Q1 2026?',
        source: 'polymarket',
        probability: 0.35,
        outcome: 'no',
        brier_score: 0.1225,
        resolved_at: '2026-03-31T23:59:00Z',
      },
      {
        id: 'pred_003',
        market_title: 'Will SpaceX launch Starship to orbit by end of 2025?',
        source: 'manifold',
        probability: 0.65,
        outcome: 'yes',
        brier_score: 0.1225,
        resolved_at: '2025-12-28T20:00:00Z',
      },
      {
        id: 'pred_004',
        market_title: 'Will a major AI lab release a model scoring 90%+ on MMLU?',
        source: 'metaculus',
        probability: 0.88,
        outcome: 'yes',
        brier_score: 0.0144,
        resolved_at: '2025-11-15T12:00:00Z',
      },
      {
        id: 'pred_008',
        market_title: 'Will Ethereum ETF see $10B+ net inflows in 2025?',
        source: 'kalshi',
        probability: 0.41,
        outcome: 'no',
        brier_score: 0.1681,
        resolved_at: '2025-12-31T23:59:00Z',
      },
    ],
  };
}

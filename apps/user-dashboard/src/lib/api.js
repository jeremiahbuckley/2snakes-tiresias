/**
 * Tiresias API client.
 *
 * All functions read PUBLIC_API_BASE_URL from the environment
 * (set in .env as PUBLIC_API_BASE_URL=http://localhost:8000).
 *
 * Each function has a comment indicating which api-gateway endpoint it calls.
 * The backend stubs currently return 501; swap in real calls as each endpoint lands.
 */

const BASE =
  typeof import.meta !== 'undefined' && import.meta.env
    ? (import.meta.env.PUBLIC_API_BASE_URL ?? 'http://localhost:8000')
    : 'http://localhost:8000';

async function apiFetch(path, options = {}) {
  const { token, ...fetchOptions } = options;
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(fetchOptions.headers ?? {}),
  };
  const res = await fetch(`${BASE}${path}`, { ...fetchOptions, headers });
  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw Object.assign(new Error(`API ${res.status}: ${path}`), { status: res.status, detail });
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Auth  (POST /auth/login, POST /auth/register, GET /auth/me)
// ---------------------------------------------------------------------------

/** Exchange email + password for a JWT access token. */
export async function login(email, password) {
  return apiFetch('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

/** Create a new account. Returns a JWT access token. */
export async function register(email, password, display_name) {
  return apiFetch('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, display_name }),
  });
}

/** Return the currently authenticated user's info. */
export async function getMe(token) {
  return apiFetch('/auth/me', { token });
}

// ---------------------------------------------------------------------------
// Dashboard  (GET /users/{user_id}/dashboard)
// ---------------------------------------------------------------------------

/** Private dashboard data: scores, badges, recent predictions. */
export async function getDashboard(userId, token) {
  return apiFetch(`/users/${userId}/dashboard`, { token });
}

// ---------------------------------------------------------------------------
// Account linking  (POST /auth/link)
// ---------------------------------------------------------------------------

/** Link an external platform account (kalshi | polymarket | manifold | metaculus). */
export async function linkAccount(platform, externalIdentifier, credential, token) {
  return apiFetch('/auth/link', {
    method: 'POST',
    token,
    body: JSON.stringify({
      platform,
      external_identifier: externalIdentifier,
      credential,
    }),
  });
}

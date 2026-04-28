/**
 * Tiresias API client.
 *
 * Server-side (Node.js/SSR): reads API_BASE_URL from process.env.
 * Client-side (browser): reads PUBLIC_API_BASE_URL from import.meta.env.
 *
 * Each function maps to a specific api-gateway endpoint.
 */

const BASE = typeof window === 'undefined'
  ? (process.env.API_BASE_URL ?? 'http://localhost:8000')
  : (import.meta.env.PUBLIC_API_BASE_URL ?? 'http://localhost:8000');

/**
 * @param {string} path
 * @param {{ token?: string, method?: string, body?: string, headers?: Record<string, string> }} [options]
 */
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
  // 204 No Content has no body
  if (res.status === 204) return null;
  return res.json();
}

// ---------------------------------------------------------------------------
// Auth  —  POST /auth/login, POST /auth/register, GET /auth/me
// ---------------------------------------------------------------------------

/** Exchange email + password for a JWT access token. */
export async function login(email, password) {
  return apiFetch('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

/** Create a new account. Returns { access_token, user_id }. */
export async function register(email, username, password, display_name) {
  return apiFetch('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, username, password, display_name }),
  });
}

/** Return the currently authenticated user's profile. */
export async function getMe(token) {
  return apiFetch('/auth/me', { token });
}

/** Update display name, bio, avatar. */
export async function updateProfile(token, { display_name, bio, avatar_url }) {
  return apiFetch('/auth/me/profile', {
    method: 'PATCH',
    token,
    body: JSON.stringify({ display_name, bio, avatar_url }),
  });
}

// ---------------------------------------------------------------------------
// Dashboard  —  GET /users/{user_id}/dashboard
// ---------------------------------------------------------------------------

/** Private dashboard data: scores, badges, recent predictions. */
export async function getDashboard(userId, token, { tag = '' } = {}) {
  const params = new URLSearchParams();
  if (tag) params.set('tag', tag);
  const qs = params.toString();
  return apiFetch(`/users/${userId}/dashboard${qs ? '?' + qs : ''}`, { token });
}

// ---------------------------------------------------------------------------
// Predictions  —  GET /users/{user_id}/predictions
// ---------------------------------------------------------------------------

/**
 * Paginated, filtered prediction list.
 * @param {string} userId
 * @param {string} token
 * @param {{ source?: string, status?: string, sort?: string, tag?: string }} [filters]
 */
export async function getPredictions(userId, token, { source = '', status = '', sort = 'date_desc', tag = '' } = {}) {
  const params = new URLSearchParams();
  if (source && source !== 'all') params.set('source', source);
  if (status && status !== 'all') params.set('status', status);
  if (sort && sort !== 'date_desc') params.set('sort', sort);
  if (tag) params.set('tag', tag);
  const qs = params.toString();
  return apiFetch(`/users/${userId}/predictions${qs ? '?' + qs : ''}`, { token });
}

// ---------------------------------------------------------------------------
// Stats  —  GET /users/{user_id}/stats
// ---------------------------------------------------------------------------

/** Scores + calibration curve + Brier timeline. */
export async function getUserStats(userId, token, { tag = '' } = {}) {
  const params = new URLSearchParams();
  if (tag) params.set('tag', tag);
  const qs = params.toString();
  return apiFetch(`/users/${userId}/stats${qs ? '?' + qs : ''}`, { token });
}

// ---------------------------------------------------------------------------
// Linked accounts  —  market sources + social publishing
// All platforms: kalshi | polymarket | manifold | metaculus | x | bluesky
// ---------------------------------------------------------------------------

/** List all linked accounts for the current user. */
export async function getLinkedAccounts(token) {
  return apiFetch('/auth/me/linked-accounts', { token });
}

/**
 * Add or update a linked account for a platform.
 * @param {string} platform - one of the platform IDs
 * @param {{ external_identifier: string, credential: string, is_enabled: boolean }} body
 */
export async function upsertLinkedAccount(token, platform, body) {
  return apiFetch(`/auth/me/linked-accounts/${platform}`, {
    method: 'PUT',
    token,
    body: JSON.stringify(body),
  });
}

/**
 * Toggle is_enabled for a linked account without changing credentials.
 * @param {string} platform
 * @param {boolean} is_enabled
 */
export async function toggleLinkedAccount(token, platform, is_enabled) {
  return apiFetch(`/auth/me/linked-accounts/${platform}`, {
    method: 'PATCH',
    token,
    body: JSON.stringify({ is_enabled }),
  });
}

/** Remove a linked account. */
export async function removeLinkedAccount(token, platform) {
  return apiFetch(`/auth/me/linked-accounts/${platform}`, {
    method: 'DELETE',
    token,
  });
}

// ---------------------------------------------------------------------------
// Share tokens  —  anonymous sharing
// ---------------------------------------------------------------------------

/** List all active share tokens. */
export async function getShareTokens(token) {
  return apiFetch('/auth/me/share-tokens', { token });
}

/**
 * Generate a new anonymous share link.
 * @param {{ label?: string, show_scores: boolean, show_badges: boolean, show_predictions: boolean }} body
 */
export async function createShareToken(token, body) {
  return apiFetch('/auth/me/share-tokens', {
    method: 'POST',
    token,
    body: JSON.stringify(body),
  });
}

/** Revoke a share token so its URL stops resolving. */
export async function revokeShareToken(token, tokenSlug) {
  return apiFetch(`/auth/me/share-tokens/${tokenSlug}`, {
    method: 'DELETE',
    token,
  });
}

/** Public endpoint — resolve a share token (no auth required). */
export async function resolveShareToken(tokenSlug) {
  return apiFetch(`/auth/share/${tokenSlug}`);
}

// ---------------------------------------------------------------------------
// Notification preferences
// ---------------------------------------------------------------------------

/** Get email notification preferences. */
export async function getNotificationPrefs(token) {
  return apiFetch('/auth/me/notifications', { token });
}

/**
 * Update email notification preferences (partial update).
 * @param {{ email_on_resolution?: boolean, email_on_badge?: boolean, email_on_rank_change?: boolean }} body
 */
export async function updateNotificationPrefs(token, body) {
  return apiFetch('/auth/me/notifications', {
    method: 'PATCH',
    token,
    body: JSON.stringify(body),
  });
}

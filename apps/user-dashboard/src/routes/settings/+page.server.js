import { fail, redirect } from '@sveltejs/kit';

const API_BASE = process.env.API_BASE_URL ?? 'http://localhost:8000';

const MARKET_PLATFORMS = ['kalshi', 'polymarket', 'manifold', 'metaculus'];
const SOCIAL_PLATFORMS = ['x', 'bluesky'];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Thin fetch wrapper — throws { status, detail } on non-ok responses. */
async function api(fetch, path, { token, method = 'GET', body } = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  if (res.status === 204) return null;
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw { status: res.status, detail };
  }
  return res.json();
}

/**
 * Convert the flat linked-accounts array from the API into two keyed objects
 * the UI expects: { kalshi: { linked, external_identifier, … }, … }
 */
function reshapeAccounts(list) {
  const empty = () => ({ linked: false, external_identifier: null, linked_at: null, is_enabled: false, is_verified: false });

  const linkedAccounts = Object.fromEntries(MARKET_PLATFORMS.map((p) => [p, empty()]));
  const socialAccounts = Object.fromEntries(SOCIAL_PLATFORMS.map((p) => [p, empty()]));

  for (const acct of list) {
    const shaped = {
      linked: true,
      external_identifier: acct.external_identifier,
      linked_at: acct.linked_at,
      is_enabled: acct.is_enabled,
      is_verified: acct.is_verified,
    };
    if (MARKET_PLATFORMS.includes(acct.platform)) linkedAccounts[acct.platform] = shaped;
    if (SOCIAL_PLATFORMS.includes(acct.platform)) socialAccounts[acct.platform] = shaped;
  }

  return { linkedAccounts, socialAccounts };
}

// ---------------------------------------------------------------------------
// Load
// ---------------------------------------------------------------------------

/** @type {import('./$types').PageServerLoad} */
export async function load({ cookies, fetch, parent }) {
  // token and user are already fetched by the layout — reuse them.
  const { token, user } = await parent();

  let accountsList, shareTokens, notificationPrefs;
  try {
    [accountsList, shareTokens, notificationPrefs] = await Promise.all([
      api(fetch, '/auth/me/linked-accounts', { token }),
      api(fetch, '/auth/me/share-tokens', { token }),
      api(fetch, '/auth/me/notifications', { token }),
    ]);
  } catch (err) {
    if (err.status === 401) throw redirect(303, '/login');
    // Surface other errors to the page rather than crashing
    accountsList = [];
    shareTokens = [];
    notificationPrefs = { email_on_resolution: true, email_on_badge: true, email_on_rank_change: false };
  }

  const { linkedAccounts, socialAccounts } = reshapeAccounts(accountsList);

  return { user, linkedAccounts, socialAccounts, shareTokens, notificationPrefs };
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

/** @type {import('./$types').Actions} */
export const actions = {

  // ---- Profile -------------------------------------------------------------

  saveProfile: async ({ request, cookies, fetch }) => {
    const token = cookies.get('tiresias_token');
    const data = await request.formData();
    try {
      await api(fetch, '/auth/me/profile', {
        token,
        method: 'PATCH',
        body: {
          display_name: data.get('display_name') || null,
          bio: data.get('bio') || null,
          avatar_url: data.get('avatar_url') || null,
        },
      });
    } catch (err) {
      return fail(err.status ?? 500, { error: 'Could not save profile. Please try again.' });
    }
    return { success: true, action: 'profile' };
  },

  // ---- Market accounts -----------------------------------------------------

  linkMarketAccount: async ({ request, cookies, fetch }) => {
    const token = cookies.get('tiresias_token');
    const data = await request.formData();
    const platform = data.get('platform')?.toString() ?? '';
    const identifier = data.get('identifier')?.toString() ?? '';
    const credential = data.get('credential')?.toString() ?? '';

    if (!identifier || !credential) {
      return fail(400, { error: 'Identifier and credential are required.', platform });
    }
    try {
      await api(fetch, `/auth/me/linked-accounts/${platform}`, {
        token,
        method: 'PUT',
        body: { external_identifier: identifier, credential, is_enabled: true },
      });
    } catch (err) {
      return fail(err.status ?? 500, { error: 'Could not link account. Check your credentials and try again.', platform });
    }
    return { success: true, action: 'marketLink', platform };
  },

  unlinkMarketAccount: async ({ request, cookies, fetch }) => {
    const token = cookies.get('tiresias_token');
    const data = await request.formData();
    const platform = data.get('platform')?.toString() ?? '';
    try {
      await api(fetch, `/auth/me/linked-accounts/${platform}`, { token, method: 'DELETE' });
    } catch (err) {
      return fail(err.status ?? 500, { error: 'Could not disconnect account.' });
    }
    return { success: true, action: 'marketUnlink', platform };
  },

  toggleMarketEnabled: async ({ request, cookies, fetch }) => {
    const token = cookies.get('tiresias_token');
    const data = await request.formData();
    const platform = data.get('platform')?.toString() ?? '';
    const is_enabled = data.get('is_enabled') === 'true';
    try {
      await api(fetch, `/auth/me/linked-accounts/${platform}`, {
        token,
        method: 'PATCH',
        body: { is_enabled },
      });
    } catch (err) {
      return fail(err.status ?? 500, { error: 'Could not update preference.' });
    }
    return { success: true, action: 'marketToggle', platform };
  },

  // ---- Social accounts -----------------------------------------------------

  linkSocialAccount: async ({ request, cookies, fetch }) => {
    const token = cookies.get('tiresias_token');
    const data = await request.formData();
    const platform = data.get('platform')?.toString() ?? '';
    const identifier = data.get('identifier')?.toString() ?? '';
    const credential = data.get('credential')?.toString() ?? '';

    if (!identifier || !credential) {
      return fail(400, { error: 'Handle and credential are required.', platform });
    }
    try {
      await api(fetch, `/auth/me/linked-accounts/${platform}`, {
        token,
        method: 'PUT',
        body: { external_identifier: identifier, credential, is_enabled: true },
      });
    } catch (err) {
      return fail(err.status ?? 500, { error: 'Could not connect social account.', platform });
    }
    return { success: true, action: 'socialLink', platform };
  },

  unlinkSocialAccount: async ({ request, cookies, fetch }) => {
    const token = cookies.get('tiresias_token');
    const data = await request.formData();
    const platform = data.get('platform')?.toString() ?? '';
    try {
      await api(fetch, `/auth/me/linked-accounts/${platform}`, { token, method: 'DELETE' });
    } catch (err) {
      return fail(err.status ?? 500, { error: 'Could not disconnect account.' });
    }
    return { success: true, action: 'socialUnlink', platform };
  },

  toggleSocialEnabled: async ({ request, cookies, fetch }) => {
    const token = cookies.get('tiresias_token');
    const data = await request.formData();
    const platform = data.get('platform')?.toString() ?? '';
    const is_enabled = data.get('is_enabled') === 'true';
    try {
      await api(fetch, `/auth/me/linked-accounts/${platform}`, {
        token,
        method: 'PATCH',
        body: { is_enabled },
      });
    } catch (err) {
      return fail(err.status ?? 500, { error: 'Could not update preference.' });
    }
    return { success: true, action: 'socialToggle', platform };
  },

  // ---- Share tokens --------------------------------------------------------

  createShareToken: async ({ request, cookies, fetch }) => {
    const token = cookies.get('tiresias_token');
    const data = await request.formData();
    let created;
    try {
      created = await api(fetch, '/auth/me/share-tokens', {
        token,
        method: 'POST',
        body: {
          label: data.get('label') || null,
          show_scores: data.get('show_scores') === 'on',
          show_badges: data.get('show_badges') === 'on',
          show_predictions: data.get('show_predictions') === 'on',
        },
      });
    } catch (err) {
      return fail(err.status ?? 500, { error: 'Could not create share link.' });
    }
    // Return the real token slug so the enhance callback can display it immediately
    return { success: true, action: 'tokenCreate', created };
  },

  revokeShareToken: async ({ request, cookies, fetch }) => {
    const token = cookies.get('tiresias_token');
    const data = await request.formData();
    const slug = data.get('token')?.toString() ?? '';
    try {
      await api(fetch, `/auth/me/share-tokens/${slug}`, { token, method: 'DELETE' });
    } catch (err) {
      return fail(err.status ?? 500, { error: 'Could not revoke share link.' });
    }
    return { success: true, action: 'tokenRevoke' };
  },

  // ---- Notifications -------------------------------------------------------

  saveNotifications: async ({ request, cookies, fetch }) => {
    const token = cookies.get('tiresias_token');
    const data = await request.formData();
    try {
      await api(fetch, '/auth/me/notifications', {
        token,
        method: 'PATCH',
        body: {
          email_on_resolution: data.get('email_on_resolution') === 'on',
          email_on_badge: data.get('email_on_badge') === 'on',
          email_on_rank_change: data.get('email_on_rank_change') === 'on',
        },
      });
    } catch (err) {
      return fail(err.status ?? 500, { error: 'Could not save notification preferences.' });
    }
    return { success: true, action: 'notifications' };
  },
};

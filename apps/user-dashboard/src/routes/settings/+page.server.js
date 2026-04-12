import {
  mockUser,
  mockLinkedAccounts,
  mockSocialAccounts,
  mockShareTokens,
  mockNotificationPrefs,
} from '$lib/mock.js';
import { fail } from '@sveltejs/kit';

/** @type {import('./$types').PageServerLoad} */
export async function load() {
  // TODO: replace with real API calls once api-gateway is live:
  //   const token = event.cookies.get('tiresias_token');
  //   const user = await getMe(token);
  //   const linked = await getLinkedAccounts(token);
  //   const shareTokens = await getShareTokens(token);
  //   const notifPrefs = await getNotificationPrefs(token);

  return {
    user: mockUser,
    linkedAccounts: mockLinkedAccounts,
    socialAccounts: mockSocialAccounts,
    shareTokens: mockShareTokens,
    notificationPrefs: mockNotificationPrefs,
  };
}

/** @type {import('./$types').Actions} */
export const actions = {

  // --------------------------------------------------------------------------
  // Profile
  // --------------------------------------------------------------------------

  /** Save profile changes (display_name, bio, avatar_url). */
  saveProfile: async ({ request }) => {
    const data = await request.formData();
    const display_name = data.get('display_name')?.toString() ?? '';
    const bio = data.get('bio')?.toString() ?? '';
    const avatar_url = data.get('avatar_url')?.toString() ?? '';

    // TODO: PATCH /auth/me/profile  { display_name, bio, avatar_url }
    console.log('saveProfile (stub):', { display_name, bio, avatar_url });
    return { success: true, action: 'profile' };
  },

  // --------------------------------------------------------------------------
  // Market account management
  // --------------------------------------------------------------------------

  /** Connect or update a prediction market account. */
  linkMarketAccount: async ({ request }) => {
    const data = await request.formData();
    const platform = data.get('platform')?.toString() ?? '';
    const identifier = data.get('identifier')?.toString() ?? '';
    const credential = data.get('credential')?.toString() ?? '';

    if (!identifier || !credential) {
      return fail(400, { error: 'Identifier and API key are required.', platform });
    }

    // TODO: PUT /auth/me/linked-accounts/{platform}
    //   { external_identifier: identifier, credential, is_enabled: true }
    console.log('linkMarketAccount (stub):', { platform, identifier });
    return { success: true, action: 'marketLink', platform };
  },

  /** Disconnect a prediction market account. */
  unlinkMarketAccount: async ({ request }) => {
    const data = await request.formData();
    const platform = data.get('platform')?.toString() ?? '';

    // TODO: DELETE /auth/me/linked-accounts/{platform}
    console.log('unlinkMarketAccount (stub):', { platform });
    return { success: true, action: 'marketUnlink', platform };
  },

  /** Toggle whether a connected market is included in scoring. */
  toggleMarketEnabled: async ({ request }) => {
    const data = await request.formData();
    const platform = data.get('platform')?.toString() ?? '';
    const is_enabled = data.get('is_enabled') === 'true';

    // TODO: PATCH /auth/me/linked-accounts/{platform}  { is_enabled }
    console.log('toggleMarketEnabled (stub):', { platform, is_enabled });
    return { success: true, action: 'marketToggle', platform };
  },

  // --------------------------------------------------------------------------
  // Social account management
  // --------------------------------------------------------------------------

  /** Connect or update a social platform (X or Bluesky). */
  linkSocialAccount: async ({ request }) => {
    const data = await request.formData();
    const platform = data.get('platform')?.toString() ?? '';
    const identifier = data.get('identifier')?.toString() ?? '';
    const credential = data.get('credential')?.toString() ?? '';

    if (!identifier || !credential) {
      return fail(400, { error: 'Handle and credential are required.', platform });
    }

    // TODO: PUT /auth/me/linked-accounts/{platform}
    //   { external_identifier: identifier, credential, is_enabled: true }
    console.log('linkSocialAccount (stub):', { platform, identifier });
    return { success: true, action: 'socialLink', platform };
  },

  /** Disconnect a social platform account. */
  unlinkSocialAccount: async ({ request }) => {
    const data = await request.formData();
    const platform = data.get('platform')?.toString() ?? '';

    // TODO: DELETE /auth/me/linked-accounts/{platform}
    console.log('unlinkSocialAccount (stub):', { platform });
    return { success: true, action: 'socialUnlink', platform };
  },

  /** Toggle auto-publish for a connected social platform. */
  toggleSocialEnabled: async ({ request }) => {
    const data = await request.formData();
    const platform = data.get('platform')?.toString() ?? '';
    const is_enabled = data.get('is_enabled') === 'true';

    // TODO: PATCH /auth/me/linked-accounts/{platform}  { is_enabled }
    console.log('toggleSocialEnabled (stub):', { platform, is_enabled });
    return { success: true, action: 'socialToggle', platform };
  },

  // --------------------------------------------------------------------------
  // Share tokens
  // --------------------------------------------------------------------------

  /** Generate a new anonymous share link. */
  createShareToken: async ({ request }) => {
    const data = await request.formData();
    const label = data.get('label')?.toString() ?? null;
    const show_scores = data.get('show_scores') === 'on';
    const show_badges = data.get('show_badges') === 'on';
    const show_predictions = data.get('show_predictions') === 'on';

    // TODO: POST /auth/me/share-tokens  { label, show_scores, show_badges, show_predictions }
    console.log('createShareToken (stub):', { label, show_scores, show_badges, show_predictions });
    return { success: true, action: 'tokenCreate' };
  },

  /** Revoke an existing share token. */
  revokeShareToken: async ({ request }) => {
    const data = await request.formData();
    const token = data.get('token')?.toString() ?? '';

    // TODO: DELETE /auth/me/share-tokens/{token}
    console.log('revokeShareToken (stub):', { token });
    return { success: true, action: 'tokenRevoke' };
  },

  // --------------------------------------------------------------------------
  // Notification preferences
  // --------------------------------------------------------------------------

  /** Save notification preferences. */
  saveNotifications: async ({ request }) => {
    const data = await request.formData();
    const prefs = {
      email_on_resolution: data.get('email_on_resolution') === 'on',
      email_on_badge: data.get('email_on_badge') === 'on',
      email_on_rank_change: data.get('email_on_rank_change') === 'on',
    };

    // TODO: PATCH /auth/me/notifications  { ...prefs }
    console.log('saveNotifications (stub):', prefs);
    return { success: true, action: 'notifications' };
  },
};

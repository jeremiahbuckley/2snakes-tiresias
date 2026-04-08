import { mockUser, mockLinkedAccounts, mockNotificationPrefs } from '$lib/mock.js';
import { fail } from '@sveltejs/kit';

/** @type {import('./$types').PageServerLoad} */
export async function load() {
  // TODO: replace with real API calls once api-gateway is live:
  //   const user = await getMe(token);
  //   const linked = await getLinkedAccounts(userId, token);

  return {
    user: mockUser,
    linkedAccounts: mockLinkedAccounts,
    notificationPrefs: mockNotificationPrefs,
  };
}

/** @type {import('./$types').Actions} */
export const actions = {
  /** Save profile changes (display_name, bio, avatar_url). */
  saveProfile: async ({ request }) => {
    const data = await request.formData();
    const display_name = data.get('display_name')?.toString() ?? '';
    const bio = data.get('bio')?.toString() ?? '';
    const avatar_url = data.get('avatar_url')?.toString() ?? '';

    // TODO: PATCH /users/{userId}/profile with { display_name, bio, avatar_url }
    console.log('saveProfile (stub):', { display_name, bio, avatar_url });

    return { success: true, action: 'profile' };
  },

  /** Link an external platform account. */
  linkAccount: async ({ request }) => {
    const data = await request.formData();
    const platform = data.get('platform')?.toString() ?? '';
    const identifier = data.get('identifier')?.toString() ?? '';
    const credential = data.get('credential')?.toString() ?? '';

    if (!identifier || !credential) {
      return fail(400, { error: 'Identifier and API key are required.', platform });
    }

    // TODO: POST /auth/link { platform, external_identifier: identifier, credential }
    console.log('linkAccount (stub):', { platform, identifier });

    return { success: true, action: 'link', platform };
  },

  /** Unlink a platform account. */
  unlinkAccount: async ({ request }) => {
    const data = await request.formData();
    const platform = data.get('platform')?.toString() ?? '';

    // TODO: DELETE /auth/link/{platform}
    console.log('unlinkAccount (stub):', { platform });

    return { success: true, action: 'unlink', platform };
  },

  /** Save notification preferences. */
  saveNotifications: async ({ request }) => {
    const data = await request.formData();
    const prefs = {
      email_on_resolution: data.get('email_on_resolution') === 'on',
      email_on_badge: data.get('email_on_badge') === 'on',
      email_on_rank_change: data.get('email_on_rank_change') === 'on',
    };

    // TODO: PATCH /users/{userId}/notifications { ...prefs }
    console.log('saveNotifications (stub):', prefs);

    return { success: true, action: 'notifications' };
  },
};

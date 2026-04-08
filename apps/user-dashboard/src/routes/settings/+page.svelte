<script>
  import { enhance } from '$app/forms';

  /** @type {import('./$types').PageData} */
  export let data;

  /** @type {import('./$types').ActionData} */
  export let form;

  const { user, linkedAccounts, notificationPrefs } = data;

  const platforms = [
    {
      id: 'kalshi',
      name: 'Kalshi',
      color: '#00b894',
      description: 'US-regulated prediction market',
      credentialLabel: 'API Key',
      credentialPlaceholder: 'Your Kalshi API key',
    },
    {
      id: 'polymarket',
      name: 'Polymarket',
      color: '#6c5ce7',
      description: 'Crypto-based prediction market',
      credentialLabel: 'Wallet / API Key',
      credentialPlaceholder: '0x...',
    },
    {
      id: 'manifold',
      name: 'Manifold',
      color: '#e17055',
      description: 'Play-money prediction market',
      credentialLabel: 'API Key',
      credentialPlaceholder: 'Your Manifold API key',
    },
    {
      id: 'metaculus',
      name: 'Metaculus',
      color: '#0984e3',
      description: 'Forecasting community',
      credentialLabel: 'API Token',
      credentialPlaceholder: 'Your Metaculus API token',
    },
  ];

  // Track which platform is being linked (shows inline form)
  let linkingPlatform = null;

  function toggleLink(platformId) {
    linkingPlatform = linkingPlatform === platformId ? null : platformId;
  }

  function fmtDate(iso) {
    if (!iso) return '';
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  // Success/error feedback
  $: successAction = form?.success ? form.action : null;
</script>

<svelte:head>
  <title>Settings — Tiresias</title>
</svelte:head>

<div class="page-header">
  <h1>Settings</h1>
  <p class="subtitle">Manage your profile, linked accounts, and preferences</p>
</div>

{#if successAction}
  <div class="alert alert-success">
    {#if successAction === 'profile'}Changes saved successfully.
    {:else if successAction === 'link'}Account linked successfully.
    {:else if successAction === 'unlink'}Account unlinked.
    {:else if successAction === 'notifications'}Notification preferences updated.
    {/if}
  </div>
{/if}

{#if form?.error}
  <div class="alert alert-error">{form.error}</div>
{/if}

<!-- Profile section -->
<section class="card section">
  <h2 class="section-title">Profile</h2>
  <p class="section-desc">This information is shown on your public profile page.</p>

  <form method="POST" action="?/saveProfile" use:enhance class="profile-form">
    <div class="form-row">
      <div class="field">
        <label for="display_name">Display Name</label>
        <input
          id="display_name"
          name="display_name"
          type="text"
          value={user.display_name ?? ''}
          maxlength="128"
          placeholder="Your display name"
        />
      </div>
      <div class="field">
        <label for="avatar_url">Avatar URL</label>
        <input
          id="avatar_url"
          name="avatar_url"
          type="url"
          value={user.avatar_url ?? ''}
          placeholder="https://…"
        />
      </div>
    </div>
    <div class="field">
      <label for="bio">Bio</label>
      <textarea
        id="bio"
        name="bio"
        rows="3"
        maxlength="500"
        placeholder="A short bio visible on your public profile…"
      >{user.bio ?? ''}</textarea>
    </div>
    <div class="form-actions">
      <button type="submit" class="btn btn-primary">Save profile</button>
    </div>
  </form>
</section>

<!-- Linked accounts section -->
<section class="card section">
  <h2 class="section-title">Linked Accounts</h2>
  <p class="section-desc">
    Connect your prediction market accounts so Tiresias can sync your history.
  </p>

  <div class="platform-list">
    {#each platforms as platform}
      {@const linked = linkedAccounts[platform.id]}
      <div class="platform-item" class:is-linked={linked?.linked}>
        <div class="platform-info">
          <span
            class="platform-dot"
            style="background:{platform.color}"
          ></span>
          <div>
            <div class="platform-name">{platform.name}</div>
            <div class="platform-desc">{platform.description}</div>
          </div>
        </div>

        <div class="platform-status">
          {#if linked?.linked}
            <div class="linked-info">
              <span class="linked-id">{linked.external_identifier}</span>
              <span class="linked-since">since {fmtDate(linked.linked_at)}</span>
            </div>
            <span class="status-badge connected">Connected</span>
            <form method="POST" action="?/unlinkAccount" use:enhance>
              <input type="hidden" name="platform" value={platform.id} />
              <button type="submit" class="btn btn-danger-sm">Disconnect</button>
            </form>
          {:else}
            <span class="status-badge disconnected">Not linked</span>
            <button
              class="btn btn-secondary-sm"
              on:click={() => toggleLink(platform.id)}
            >
              {linkingPlatform === platform.id ? 'Cancel' : 'Connect'}
            </button>
          {/if}
        </div>
      </div>

      <!-- Inline link form -->
      {#if linkingPlatform === platform.id && !linked?.linked}
        <div class="link-form-wrap">
          <form method="POST" action="?/linkAccount" use:enhance class="link-form">
            <input type="hidden" name="platform" value={platform.id} />
            <div class="field">
              <label for="identifier_{platform.id}">Username / Identifier</label>
              <input
                id="identifier_{platform.id}"
                name="identifier"
                type="text"
                placeholder="Your {platform.name} username"
                required
              />
            </div>
            <div class="field">
              <label for="credential_{platform.id}">{platform.credentialLabel}</label>
              <input
                id="credential_{platform.id}"
                name="credential"
                type="password"
                placeholder={platform.credentialPlaceholder}
                required
              />
            </div>
            <button type="submit" class="btn btn-primary">Link account</button>
          </form>
        </div>
      {/if}
    {/each}
  </div>
</section>

<!-- Notifications section -->
<section class="card section">
  <h2 class="section-title">Notification Preferences</h2>
  <p class="section-desc">Choose when you'd like to receive email notifications.</p>

  <form method="POST" action="?/saveNotifications" use:enhance class="notif-form">
    <label class="toggle-row">
      <div class="toggle-info">
        <span class="toggle-label">Market resolutions</span>
        <span class="toggle-desc">Get notified when a market you've predicted on resolves.</span>
      </div>
      <input
        type="checkbox"
        name="email_on_resolution"
        checked={notificationPrefs.email_on_resolution}
        class="toggle"
      />
    </label>

    <label class="toggle-row">
      <div class="toggle-info">
        <span class="toggle-label">New badges</span>
        <span class="toggle-desc">Get notified when you earn a new badge.</span>
      </div>
      <input
        type="checkbox"
        name="email_on_badge"
        checked={notificationPrefs.email_on_badge}
        class="toggle"
      />
    </label>

    <label class="toggle-row">
      <div class="toggle-info">
        <span class="toggle-label">Leaderboard rank changes</span>
        <span class="toggle-desc">Get notified when your rank on the leaderboard changes.</span>
      </div>
      <input
        type="checkbox"
        name="email_on_rank_change"
        checked={notificationPrefs.email_on_rank_change}
        class="toggle"
      />
    </label>

    <div class="form-actions">
      <button type="submit" class="btn btn-primary">Save preferences</button>
    </div>
  </form>
</section>

<style>
  .page-header {
    margin-bottom: 28px;
  }

  h1 {
    font-size: 26px;
    color: #1a1f2e;
  }

  .subtitle {
    color: #6b7280;
    font-size: 14px;
    margin-top: 4px;
  }

  /* ---- Alerts ---- */
  .alert {
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 14px;
    margin-bottom: 20px;
  }

  .alert-success {
    background: #d1fae5;
    border: 1px solid #6ee7b7;
    color: #065f46;
  }

  .alert-error {
    background: #fef2f2;
    border: 1px solid #fca5a5;
    color: #991b1b;
  }

  /* ---- Section cards ---- */
  .card {
    background: #fff;
    border-radius: 12px;
    padding: 28px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.07);
  }

  .section {
    margin-bottom: 20px;
  }

  .section-title {
    font-size: 16px;
    font-weight: 600;
    color: #1a1f2e;
    margin-bottom: 4px;
  }

  .section-desc {
    font-size: 13px;
    color: #6b7280;
    margin-bottom: 20px;
  }

  /* ---- Profile form ---- */
  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 16px;
  }

  label {
    font-size: 13px;
    font-weight: 600;
    color: #374151;
  }

  input[type="text"],
  input[type="url"],
  input[type="password"],
  textarea {
    padding: 10px 12px;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    font-size: 14px;
    color: #1a1f2e;
    outline: none;
    transition: border-color 0.15s, box-shadow 0.15s;
    font-family: inherit;
    resize: vertical;
  }

  input:focus,
  textarea:focus {
    border-color: #4f8ef7;
    box-shadow: 0 0 0 3px rgba(79, 142, 247, 0.12);
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    margin-top: 4px;
  }

  /* ---- Buttons ---- */
  .btn {
    padding: 9px 18px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    border: none;
    transition: background 0.15s;
  }

  .btn-primary {
    background: #4f8ef7;
    color: #fff;
  }

  .btn-primary:hover {
    background: #3b7de8;
  }

  .btn-secondary-sm {
    padding: 6px 14px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    background: #f3f4f6;
    color: #374151;
    border: 1px solid #d1d5db;
    transition: background 0.15s;
  }

  .btn-secondary-sm:hover {
    background: #e5e7eb;
  }

  .btn-danger-sm {
    padding: 6px 14px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    background: #fef2f2;
    color: #991b1b;
    border: 1px solid #fca5a5;
    transition: background 0.15s;
  }

  .btn-danger-sm:hover {
    background: #fee2e2;
  }

  /* ---- Platform list ---- */
  .platform-list {
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .platform-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 0;
    border-bottom: 1px solid #f3f4f6;
    gap: 16px;
    flex-wrap: wrap;
  }

  .platform-item:last-of-type {
    border-bottom: none;
  }

  .platform-info {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .platform-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .platform-name {
    font-size: 14px;
    font-weight: 600;
    color: #1a1f2e;
  }

  .platform-desc {
    font-size: 12px;
    color: #9ca3af;
  }

  .platform-status {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .linked-info {
    display: flex;
    flex-direction: column;
    text-align: right;
  }

  .linked-id {
    font-size: 13px;
    font-weight: 600;
    color: #374151;
  }

  .linked-since {
    font-size: 11px;
    color: #9ca3af;
  }

  .status-badge {
    font-size: 11px;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 20px;
    letter-spacing: 0.03em;
  }

  .status-badge.connected {
    background: #d1fae5;
    color: #065f46;
  }

  .status-badge.disconnected {
    background: #f3f4f6;
    color: #9ca3af;
  }

  /* ---- Inline link form ---- */
  .link-form-wrap {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 4px;
  }

  .link-form .field:last-of-type {
    margin-bottom: 0;
  }

  /* ---- Notifications ---- */
  .notif-form {
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .toggle-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 0;
    border-bottom: 1px solid #f3f4f6;
    cursor: pointer;
    gap: 16px;
  }

  .toggle-row:last-of-type {
    border-bottom: none;
  }

  .toggle-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .toggle-label {
    font-size: 14px;
    font-weight: 500;
    color: #1a1f2e;
  }

  .toggle-desc {
    font-size: 13px;
    color: #9ca3af;
  }

  .toggle {
    width: 18px;
    height: 18px;
    flex-shrink: 0;
    cursor: pointer;
    accent-color: #4f8ef7;
  }

  .notif-form .form-actions {
    margin-top: 16px;
  }

  @media (max-width: 600px) {
    .form-row {
      grid-template-columns: 1fr;
    }
  }
</style>

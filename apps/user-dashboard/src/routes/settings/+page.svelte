<script>
  import { enhance } from '$app/forms';

  /** @type {import('./$types').PageData} */
  export let data;

  /** @type {import('./$types').ActionData} */
  export let form;

  const { user, linkedAccounts, socialAccounts, shareTokens, notificationPrefs } = data;

  // ---- Prediction market platforms ----------------------------------------
  const marketPlatforms = [
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
      credentialPlaceholder: '0x…',
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

  // ---- Social publishing platforms ----------------------------------------
  const socialPlatforms = [
    {
      id: 'x',
      name: 'X (Twitter)',
      color: '#000000',
      description: 'Post score summaries and badge links to your X profile',
      handleLabel: 'X Handle',
      handlePlaceholder: '@yourhandle',
      credentialLabel: 'API Credentials',
      credentialPlaceholder: 'Paste your OAuth access token',
      credentialHint: 'Create an X developer app and paste the Access Token here. Tiresias will post on your behalf.',
    },
    {
      id: 'bluesky',
      name: 'Bluesky',
      color: '#0085ff',
      description: 'Post score summaries and badge links to your Bluesky feed',
      handleLabel: 'Bluesky Handle',
      handlePlaceholder: 'you.bsky.social',
      credentialLabel: 'App Password',
      credentialPlaceholder: 'xxxx-xxxx-xxxx-xxxx',
      credentialHint: 'Generate an App Password in your Bluesky Settings → App Passwords.',
    },
  ];

  // ---- Local mutable state (initialized from server data) -----------------
  // Using `let` rather than const destructuring so enhance callbacks can
  // update these optimistically without waiting for load() to re-run.
  let markets      = { ...data.linkedAccounts };
  let socials      = { ...data.socialAccounts };
  let tokens       = [...data.shareTokens];
  let notifPrefs   = { ...data.notificationPrefs };

  let linkingMarket = null;
  let linkingSocial = null;
  let showCreateTokenForm = false;
  let successMessage = null;

  function toggleMarketLink(platformId) {
    linkingMarket = linkingMarket === platformId ? null : platformId;
  }

  function toggleSocialLink(platformId) {
    linkingSocial = linkingSocial === platformId ? null : platformId;
  }

  function copyToClipboard(text) {
    navigator.clipboard.writeText(text).catch(() => {});
  }

  function shareUrl(token) {
    const base = typeof window !== 'undefined' ? window.location.origin.replace('dashboard.', '') : 'https://tiresias.app';
    return `${base}/share/${token}`;
  }

  function fmtDate(iso) {
    if (!iso) return '';
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  function flash(msg) {
    successMessage = msg;
    setTimeout(() => (successMessage = null), 3000);
  }

  // ---- Enhance callbacks — optimistic UI updates --------------------------

  function enhanceMarketLink(platform) {
    return ({ formData }) => async ({ result, update }) => {
      if (result.type === 'success') {
        const identifier = formData.get('identifier');
        markets = {
          ...markets,
          [platform]: { linked: true, external_identifier: identifier, linked_at: new Date().toISOString(), is_enabled: true, is_verified: false },
        };
        linkingMarket = null;
        flash('Market account connected.');
      }
      await update({ reset: false });
    };
  }

  function enhanceMarketUnlink(platform) {
    return () => async ({ result, update }) => {
      if (result.type === 'success') {
        markets = {
          ...markets,
          [platform]: { linked: false, external_identifier: null, linked_at: null, is_enabled: false, is_verified: false },
        };
        flash('Market account disconnected.');
      }
      await update({ reset: false });
    };
  }

  function enhanceMarketToggle(platform) {
    return () => async ({ result, update }) => {
      if (result.type === 'success') {
        markets = {
          ...markets,
          [platform]: { ...markets[platform], is_enabled: !markets[platform].is_enabled },
        };
        flash('Data source preference updated.');
      }
      await update({ reset: false });
    };
  }

  function enhanceSocialLink(platform) {
    return ({ formData }) => async ({ result, update }) => {
      if (result.type === 'success') {
        const identifier = formData.get('identifier');
        socials = {
          ...socials,
          [platform]: { linked: true, external_identifier: identifier, linked_at: new Date().toISOString(), is_enabled: true, is_verified: false },
        };
        linkingSocial = null;
        flash('Social account connected.');
      }
      await update({ reset: false });
    };
  }

  function enhanceSocialUnlink(platform) {
    return () => async ({ result, update }) => {
      if (result.type === 'success') {
        socials = {
          ...socials,
          [platform]: { linked: false, external_identifier: null, linked_at: null, is_enabled: false, is_verified: false },
        };
        flash('Social account disconnected.');
      }
      await update({ reset: false });
    };
  }

  function enhanceSocialToggle(platform) {
    return () => async ({ result, update }) => {
      if (result.type === 'success') {
        socials = {
          ...socials,
          [platform]: { ...socials[platform], is_enabled: !socials[platform].is_enabled },
        };
        flash('Publishing preference updated.');
      }
      await update({ reset: false });
    };
  }

  function enhanceCreateToken() {
    return () => async ({ result, update }) => {
      if (result.type === 'success' && result.data?.created) {
        tokens = [...tokens, result.data.created];
        showCreateTokenForm = false;
        flash('Share link created.');
      }
      await update({ reset: false });
    };
  }

  function enhanceRevokeToken(slug) {
    return () => async ({ result, update }) => {
      if (result.type === 'success') {
        tokens = tokens.filter(t => t.token !== slug);
        flash('Share link revoked.');
      }
      await update({ reset: false });
    };
  }
</script>

<svelte:head>
  <title>Settings — Tiresias</title>
</svelte:head>

<div class="page-header">
  <h1>Settings</h1>
  <p class="subtitle">Manage your profile, data sources, publishing, and sharing preferences</p>
</div>

{#if successMessage}
  <div class="alert alert-success">{successMessage}</div>
{/if}

{#if form?.error}
  <div class="alert alert-error">{form.error}</div>
{/if}

<!-- =========================================================================
     SECTION 1 — Profile
     ========================================================================= -->
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

<!-- =========================================================================
     SECTION 2 — Market Data Sources
     ========================================================================= -->
<section class="card section">
  <h2 class="section-title">Market Data Sources</h2>
  <p class="section-desc">
    Connect your prediction market accounts so Tiresias can sync your trade history.
    Use the toggle to include or exclude a connected market from your scoring.
  </p>

  <div class="platform-list">
    {#each marketPlatforms as platform}
      {@const acct = markets[platform.id]}
      {@const isLinked = acct?.linked}

      <div class="platform-item" class:is-linked={isLinked}>
        <div class="platform-info">
          <span class="platform-dot" style="background:{platform.color}"></span>
          <div>
            <div class="platform-name">{platform.name}</div>
            <div class="platform-desc">{platform.description}</div>
          </div>
        </div>

        <div class="platform-status">
          {#if isLinked}
            <!-- Enable / disable toggle -->
            <form method="POST" action="?/toggleMarketEnabled" use:enhance={enhanceMarketToggle(platform.id)} class="toggle-form">
              <input type="hidden" name="platform" value={platform.id} />
              <input type="hidden" name="is_enabled" value={acct.is_enabled ? 'false' : 'true'} />
              <button
                type="submit"
                class="toggle-chip"
                class:toggle-chip-on={acct.is_enabled}
                title={acct.is_enabled ? 'Included in scoring — click to exclude' : 'Excluded from scoring — click to include'}
              >
                {acct.is_enabled ? 'Active' : 'Paused'}
              </button>
            </form>

            <div class="linked-info">
              <span class="linked-id">{acct.external_identifier}</span>
              <span class="linked-since">since {fmtDate(acct.linked_at)}</span>
            </div>
            <span class="status-badge connected">Connected</span>
            <form method="POST" action="?/unlinkMarketAccount" use:enhance={enhanceMarketUnlink(platform.id)}>
              <input type="hidden" name="platform" value={platform.id} />
              <button type="submit" class="btn btn-danger-sm">Disconnect</button>
            </form>
          {:else}
            <span class="status-badge disconnected">Not linked</span>
            <button class="btn btn-secondary-sm" on:click={() => toggleMarketLink(platform.id)}>
              {linkingMarket === platform.id ? 'Cancel' : 'Connect'}
            </button>
          {/if}
        </div>
      </div>

      {#if linkingMarket === platform.id && !isLinked}
        <div class="link-form-wrap">
          <form method="POST" action="?/linkMarketAccount" use:enhance={enhanceMarketLink(platform.id)} class="link-form">
            <input type="hidden" name="platform" value={platform.id} />
            <div class="field">
              <label for="market_id_{platform.id}">Username / Identifier</label>
              <input
                id="market_id_{platform.id}"
                name="identifier"
                type="text"
                placeholder="Your {platform.name} username"
                required
              />
            </div>
            <div class="field">
              <label for="market_cred_{platform.id}">{platform.credentialLabel}</label>
              <input
                id="market_cred_{platform.id}"
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

<!-- =========================================================================
     SECTION 3 — Social Publishing
     ========================================================================= -->
<section class="card section">
  <h2 class="section-title">Social Publishing</h2>
  <p class="section-desc">
    Connect social accounts so Tiresias can automatically post your score
    updates and badge announcements. You stay in control — publishing only
    fires when new badges are earned or your score meaningfully changes.
  </p>

  <div class="platform-list">
    {#each socialPlatforms as platform}
      {@const acct = socials[platform.id]}
      {@const isLinked = acct?.linked}

      <div class="platform-item" class:is-linked={isLinked}>
        <div class="platform-info">
          <span class="platform-dot" style="background:{platform.color}"></span>
          <div>
            <div class="platform-name">{platform.name}</div>
            <div class="platform-desc">{platform.description}</div>
          </div>
        </div>

        <div class="platform-status">
          {#if isLinked}
            <!-- Auto-publish toggle -->
            <form method="POST" action="?/toggleSocialEnabled" use:enhance={enhanceSocialToggle(platform.id)} class="toggle-form">
              <input type="hidden" name="platform" value={platform.id} />
              <input type="hidden" name="is_enabled" value={acct.is_enabled ? 'false' : 'true'} />
              <button
                type="submit"
                class="toggle-chip"
                class:toggle-chip-on={acct.is_enabled}
                title={acct.is_enabled ? 'Auto-publish on — click to pause' : 'Auto-publish off — click to enable'}
              >
                {acct.is_enabled ? 'Auto-publish on' : 'Auto-publish off'}
              </button>
            </form>

            <div class="linked-info">
              <span class="linked-id">{acct.external_identifier}</span>
              <span class="linked-since">since {fmtDate(acct.linked_at)}</span>
            </div>
            <span class="status-badge connected">Connected</span>
            <form method="POST" action="?/unlinkSocialAccount" use:enhance={enhanceSocialUnlink(platform.id)}>
              <input type="hidden" name="platform" value={platform.id} />
              <button type="submit" class="btn btn-danger-sm">Disconnect</button>
            </form>
          {:else}
            <span class="status-badge disconnected">Not linked</span>
            <button class="btn btn-secondary-sm" on:click={() => toggleSocialLink(platform.id)}>
              {linkingSocial === platform.id ? 'Cancel' : 'Connect'}
            </button>
          {/if}
        </div>
      </div>

      {#if linkingSocial === platform.id && !isLinked}
        <div class="link-form-wrap">
          <form method="POST" action="?/linkSocialAccount" use:enhance={enhanceSocialLink(platform.id)} class="link-form">
            <input type="hidden" name="platform" value={platform.id} />
            <div class="field">
              <label for="social_id_{platform.id}">{platform.handleLabel}</label>
              <input
                id="social_id_{platform.id}"
                name="identifier"
                type="text"
                placeholder={platform.handlePlaceholder}
                required
              />
            </div>
            <div class="field">
              <label for="social_cred_{platform.id}">{platform.credentialLabel}</label>
              <input
                id="social_cred_{platform.id}"
                name="credential"
                type="password"
                placeholder={platform.credentialPlaceholder}
                required
              />
              <span class="field-hint">{platform.credentialHint}</span>
            </div>
            <button type="submit" class="btn btn-primary">Connect</button>
          </form>
        </div>
      {/if}
    {/each}
  </div>
</section>

<!-- =========================================================================
     SECTION 4 — Anonymous Sharing
     ========================================================================= -->
<section class="card section">
  <h2 class="section-title">Anonymous Sharing</h2>
  <p class="section-desc">
    Share your scores and badges with anyone — without revealing your identity.
    Each link shows only what you choose. Recipients see your numbers, not your name.
  </p>

  <!-- Existing share links -->
  {#if tokens.length > 0}
    <div class="share-token-list">
      {#each tokens as st}
        <div class="share-token-item">
          <div class="share-token-meta">
            <span class="share-token-label">{st.label || 'Untitled link'}</span>
            <span class="share-token-created">Created {fmtDate(st.created_at)}</span>
          </div>

          <div class="share-token-visibility">
            {#if st.show_scores}<span class="vis-chip">Scores</span>{/if}
            {#if st.show_badges}<span class="vis-chip">Badges</span>{/if}
            {#if st.show_predictions}<span class="vis-chip">Predictions</span>{/if}
          </div>

          <div class="share-token-actions">
            <code class="share-url">/share/{st.token.slice(0, 10)}…</code>
            <button
              type="button"
              class="btn btn-secondary-sm"
              on:click={() => copyToClipboard(shareUrl(st.token))}
            >
              Copy link
            </button>
            <form method="POST" action="?/revokeShareToken" use:enhance={enhanceRevokeToken(st.token)}>
              <input type="hidden" name="token" value={st.token} />
              <button type="submit" class="btn btn-danger-sm">Revoke</button>
            </form>
          </div>
        </div>
      {/each}
    </div>
  {:else}
    <p class="empty-state">No share links yet. Create one below.</p>
  {/if}

  <!-- Create new link -->
  {#if showCreateTokenForm}
    <div class="link-form-wrap" style="margin-top:16px">
      <form method="POST" action="?/createShareToken" use:enhance={enhanceCreateToken()} class="link-form">
        <div class="field">
          <label for="token_label">Label <span class="optional">(optional)</span></label>
          <input
            id="token_label"
            name="label"
            type="text"
            maxlength="128"
            placeholder="e.g. For colleagues, Reddit post…"
          />
        </div>
        <div class="visibility-options">
          <span class="vis-label">What can recipients see?</span>
          <label class="vis-toggle">
            <input type="checkbox" name="show_scores" checked /> Scores &amp; accuracy
          </label>
          <label class="vis-toggle">
            <input type="checkbox" name="show_badges" checked /> Badges
          </label>
          <label class="vis-toggle">
            <input type="checkbox" name="show_predictions" /> Individual predictions
          </label>
        </div>
        <div class="form-actions" style="margin-top:12px">
          <button type="button" class="btn btn-secondary-sm" on:click={() => (showCreateTokenForm = false)}>Cancel</button>
          <button type="submit" class="btn btn-primary">Generate link</button>
        </div>
      </form>
    </div>
  {:else}
    <button
      type="button"
      class="btn btn-secondary-sm"
      style="margin-top:16px"
      on:click={() => (showCreateTokenForm = true)}
    >
      + New share link
    </button>
  {/if}
</section>

<!-- =========================================================================
     SECTION 5 — Notification Preferences
     ========================================================================= -->
<section class="card section">
  <h2 class="section-title">Notification Preferences</h2>
  <p class="section-desc">Choose when you'd like to receive email notifications.</p>

  <form method="POST" action="?/saveNotifications" use:enhance class="notif-form">
    <label class="toggle-row">
      <div class="toggle-info">
        <span class="toggle-label">Market resolutions</span>
        <span class="toggle-desc">Get notified when a market you've predicted on resolves.</span>
      </div>
      <input type="checkbox" name="email_on_resolution" checked={notificationPrefs.email_on_resolution} class="toggle" />
    </label>

    <label class="toggle-row">
      <div class="toggle-info">
        <span class="toggle-label">New badges</span>
        <span class="toggle-desc">Get notified when you earn a new badge.</span>
      </div>
      <input type="checkbox" name="email_on_badge" checked={notificationPrefs.email_on_badge} class="toggle" />
    </label>

    <label class="toggle-row">
      <div class="toggle-info">
        <span class="toggle-label">Leaderboard rank changes</span>
        <span class="toggle-desc">Get notified when your rank on the leaderboard changes.</span>
      </div>
      <input type="checkbox" name="email_on_rank_change" checked={notificationPrefs.email_on_rank_change} class="toggle" />
    </label>

    <div class="form-actions">
      <button type="submit" class="btn btn-primary">Save preferences</button>
    </div>
  </form>
</section>

<style>
  /* ---- Page header ---- */
  .page-header { margin-bottom: 28px; }
  h1 { font-size: 26px; color: #1a1f2e; }
  .subtitle { color: #6b7280; font-size: 14px; margin-top: 4px; }

  /* ---- Alerts ---- */
  .alert {
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 14px;
    margin-bottom: 20px;
  }
  .alert-success { background: #d1fae5; border: 1px solid #6ee7b7; color: #065f46; }
  .alert-error   { background: #fef2f2; border: 1px solid #fca5a5; color: #991b1b; }

  /* ---- Section cards ---- */
  .card {
    background: #fff;
    border-radius: 12px;
    padding: 28px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07);
  }
  .section { margin-bottom: 20px; }
  .section-title { font-size: 16px; font-weight: 600; color: #1a1f2e; margin-bottom: 4px; }
  .section-desc  { font-size: 13px; color: #6b7280; margin-bottom: 20px; }

  /* ---- Profile form ---- */
  .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .field { display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px; }

  label { font-size: 13px; font-weight: 600; color: #374151; }
  .optional { font-weight: 400; color: #9ca3af; }

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
  input:focus, textarea:focus {
    border-color: #4f8ef7;
    box-shadow: 0 0 0 3px rgba(79,142,247,0.12);
  }

  .field-hint { font-size: 12px; color: #9ca3af; margin-top: 2px; }

  .form-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 4px; }

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
  .btn-primary { background: #4f8ef7; color: #fff; }
  .btn-primary:hover { background: #3b7de8; }
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
  .btn-secondary-sm:hover { background: #e5e7eb; }
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
  .btn-danger-sm:hover { background: #fee2e2; }

  /* ---- Platform list (shared by market + social sections) ---- */
  .platform-list { display: flex; flex-direction: column; gap: 0; }
  .platform-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 0;
    border-bottom: 1px solid #f3f4f6;
    gap: 16px;
    flex-wrap: wrap;
  }
  .platform-item:last-of-type { border-bottom: none; }

  .platform-info { display: flex; align-items: center; gap: 12px; }
  .platform-dot  { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
  .platform-name { font-size: 14px; font-weight: 600; color: #1a1f2e; }
  .platform-desc { font-size: 12px; color: #9ca3af; }

  .platform-status {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .linked-info { display: flex; flex-direction: column; text-align: right; }
  .linked-id   { font-size: 13px; font-weight: 600; color: #374151; }
  .linked-since { font-size: 11px; color: #9ca3af; }

  .status-badge {
    font-size: 11px;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 20px;
    letter-spacing: 0.03em;
  }
  .status-badge.connected    { background: #d1fae5; color: #065f46; }
  .status-badge.disconnected { background: #f3f4f6; color: #9ca3af; }

  /* Active / Paused toggle chip */
  .toggle-form { display: inline-flex; }
  .toggle-chip {
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    cursor: pointer;
    border: none;
    background: #f3f4f6;
    color: #9ca3af;
    transition: background 0.15s, color 0.15s;
    letter-spacing: 0.03em;
  }
  .toggle-chip-on { background: #dbeafe; color: #1d4ed8; }

  /* ---- Inline link form ---- */
  .link-form-wrap {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 4px;
  }
  .link-form .field:last-of-type { margin-bottom: 0; }

  /* ---- Share tokens ---- */
  .share-token-list { display: flex; flex-direction: column; gap: 12px; }
  .share-token-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 14px 16px;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    flex-wrap: wrap;
  }
  .share-token-meta { display: flex; flex-direction: column; gap: 2px; }
  .share-token-label { font-size: 14px; font-weight: 600; color: #1a1f2e; }
  .share-token-created { font-size: 11px; color: #9ca3af; }

  .share-token-visibility { display: flex; gap: 6px; flex-wrap: wrap; }
  .vis-chip {
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 20px;
    background: #e0e7ff;
    color: #3730a3;
  }

  .share-token-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  .share-url {
    font-size: 12px;
    color: #6b7280;
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    padding: 3px 8px;
    font-family: monospace;
  }

  .empty-state { font-size: 13px; color: #9ca3af; font-style: italic; margin-bottom: 4px; }

  /* Visibility option checkboxes in create form */
  .visibility-options {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 4px;
  }
  .vis-label { font-size: 13px; font-weight: 600; color: #374151; }
  .vis-toggle {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: #374151;
    font-weight: 400;
    cursor: pointer;
  }
  .vis-toggle input[type="checkbox"] {
    width: 16px;
    height: 16px;
    accent-color: #4f8ef7;
    cursor: pointer;
  }

  /* ---- Notifications ---- */
  .notif-form { display: flex; flex-direction: column; gap: 0; }
  .toggle-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 0;
    border-bottom: 1px solid #f3f4f6;
    cursor: pointer;
    gap: 16px;
  }
  .toggle-row:last-of-type { border-bottom: none; }
  .toggle-info { display: flex; flex-direction: column; gap: 2px; }
  .toggle-label { font-size: 14px; font-weight: 500; color: #1a1f2e; }
  .toggle-desc  { font-size: 13px; color: #9ca3af; }
  .toggle {
    width: 18px;
    height: 18px;
    flex-shrink: 0;
    cursor: pointer;
    accent-color: #4f8ef7;
  }
  .notif-form .form-actions { margin-top: 16px; }

  @media (max-width: 600px) {
    .form-row { grid-template-columns: 1fr; }
    .share-token-item { flex-direction: column; align-items: flex-start; }
  }
</style>

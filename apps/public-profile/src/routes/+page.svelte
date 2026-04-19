<script>
  /** @type {import('./$types').PageData} */
  export let data;

  const { featured, demo_share_token } = data;

  const platformColors = {
    kalshi:     '#00b894',
    polymarket: '#6c5ce7',
    manifold:   '#e17055',
    metaculus:  '#0984e3',
  };
  function sourceColor(s) {
    return platformColors[s] ?? '#aaa';
  }
  function fmt(n, d = 3) {
    return n == null ? '—' : n.toFixed(d);
  }
</script>

<svelte:head>
  <title>Profiles — Tiresias</title>
  <meta
    name="description"
    content="Shareable forecaster profiles on Tiresias. See prediction accuracy across Kalshi, Polymarket, Manifold, and Metaculus."
  />
</svelte:head>

<!-- ===== Hero ===== -->
<header class="hero">
  <div class="tiresias-wordmark">Tiresias</div>
  <h1 class="hero-title">Forecaster Profiles</h1>
  <p class="hero-sub">
    "I see not what is, but what must be." Public, shareable accuracy scores
    across Kalshi, Polymarket, Manifold, and Metaculus.
  </p>
  <p class="hero-hint">
    Looking for a specific forecaster? Visit <code>/u/&lt;username&gt;</code>.
  </p>
</header>

<!-- ===== Featured ===== -->
<section class="section">
  <h2 class="section-title">Featured forecasters</h2>
  <div class="card-grid">
    {#each featured as f}
      <a class="forecaster-card" href="/u/{f.username}">
        <div class="avatar-placeholder">{f.display_name[0].toUpperCase()}</div>
        <div class="card-meta">
          <div class="display-name">{f.display_name}</div>
          <div class="handle">@{f.username}</div>
        </div>
        <div class="card-stats">
          <div class="stat">
            <div class="stat-value {f.brier_skill_score > 0 ? 'positive' : ''}">{fmt(f.brier_skill_score)}</div>
            <div class="stat-label">BSS</div>
          </div>
          <div class="stat">
            <div class="stat-value">{f.resolved_predictions}</div>
            <div class="stat-label">Resolved</div>
          </div>
        </div>
        <div class="platform-chips">
          {#each f.platforms as p}
            <span
              class="platform-chip"
              style="background:{sourceColor(p)}18;color:{sourceColor(p)}"
            >{p}</span>
          {/each}
        </div>
      </a>
    {/each}
  </div>
</section>

<!-- ===== Try it ===== -->
<section class="section try-it card">
  <h2 class="section-title">Try it out</h2>
  <ul class="try-list">
    <li>
      <strong>Public profile:</strong>
      <a href="/u/jeremiah_b">/u/jeremiah_b</a> — a fully populated demo profile.
    </li>
    <li>
      <strong>Anonymous share link:</strong>
      <a href="/share/{demo_share_token}">/share/{demo_share_token}</a> — mock shared-scores page.
    </li>
  </ul>
</section>

<style>
  :global(body) {
    background: #f5f6fa;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    color: #1a1f2e;
    margin: 0;
    padding: 0;
  }
  :global(*, *::before, *::after) { box-sizing: border-box; }
  :global(main) {
    max-width: 960px;
    margin: 0 auto;
    padding: 40px 24px 64px;
  }

  .card {
    background: #fff;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.07);
  }

  /* ---- Hero ---- */
  .hero {
    text-align: center;
    margin-bottom: 40px;
  }
  .tiresias-wordmark {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #4f8ef7;
    margin-bottom: 16px;
  }
  .hero-title {
    font-size: 30px;
    font-weight: 700;
    margin: 0 0 8px;
    line-height: 1.2;
  }
  .hero-sub {
    font-size: 15px;
    color: #6b7280;
    max-width: 560px;
    margin: 0 auto 10px;
    line-height: 1.5;
  }
  .hero-hint {
    font-size: 13px;
    color: #9ca3af;
    margin: 8px 0 0;
  }
  .hero-hint code {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    background: #f3f4f6;
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 12px;
  }

  /* ---- Sections ---- */
  .section { margin-bottom: 28px; }
  .section-title {
    font-size: 15px;
    font-weight: 600;
    color: #374151;
    margin: 0 0 16px;
  }

  /* ---- Card grid ---- */
  .card-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
  }

  .forecaster-card {
    background: #fff;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.07);
    display: flex;
    flex-direction: column;
    gap: 12px;
    text-decoration: none;
    color: inherit;
    transition: box-shadow 0.15s, transform 0.15s;
  }
  .forecaster-card:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    transform: translateY(-1px);
  }

  .avatar-placeholder {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    background: linear-gradient(135deg, #4f8ef7 0%, #6c5ce7 100%);
    color: #fff;
    font-weight: 700;
    font-size: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    user-select: none;
  }

  .card-meta { line-height: 1.25; }
  .display-name { font-size: 15px; font-weight: 600; color: #1a1f2e; }
  .handle { font-size: 12px; color: #9ca3af; }

  .card-stats {
    display: flex;
    gap: 20px;
    padding: 10px 0;
    border-top: 1px solid #f3f4f6;
    border-bottom: 1px solid #f3f4f6;
  }
  .stat-value {
    font-size: 20px;
    font-weight: 700;
    color: #1a1f2e;
    line-height: 1.1;
  }
  .stat-value.positive { color: #059669; }
  .stat-label {
    font-size: 10px;
    font-weight: 700;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-top: 2px;
  }

  .platform-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }
  .platform-chip {
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 20px;
    text-transform: capitalize;
  }

  /* ---- Try-it list ---- */
  .try-list {
    margin: 0;
    padding-left: 20px;
    line-height: 1.8;
    color: #4b5563;
    font-size: 14px;
  }
  .try-list a {
    color: #4f8ef7;
    text-decoration: none;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 13px;
  }
  .try-list a:hover { text-decoration: underline; }

  @media (max-width: 720px) {
    .card-grid { grid-template-columns: 1fr; }
  }
</style>

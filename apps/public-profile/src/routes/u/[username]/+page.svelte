<script>
  /** @type {import('./$types').PageData} */
  export let data;

  const { user, score, badges, recentPredictions } = data;

  // ---- Helpers ----

  function fmt(n, decimals = 3) {
    return n == null ? '—' : n.toFixed(decimals);
  }

  function fmtPct(n) {
    return n == null ? '—' : `${(n * 100).toFixed(1)}%`;
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  function fmtYear(iso) {
    if (!iso) return '';
    return new Date(iso).getFullYear();
  }

  // ---- Derived ----

  const displayName = user.display_name ?? user.username;
  const earnedBadges = badges.filter((b) => b.earned);
  const lockedBadges = badges.filter((b) => !b.earned);
  const resolutionRate = score.total_predictions
    ? ((score.resolved_predictions / score.total_predictions) * 100).toFixed(0)
    : 0;

  // ---- Platform config ----

  const platformColors = {
    kalshi:     '#00b894',
    polymarket: '#6c5ce7',
    manifold:   '#e17055',
    metaculus:  '#0984e3',
  };

  function sourceColor(source) {
    return platformColors[source] ?? '#aaa';
  }

  // Sort platforms best (lowest Brier) → worst
  const sortedPlatforms = Object.entries(score.per_source).sort((a, b) => a[1] - b[1]);

  // ---- Social links ----

  const socialDefs = [
    { key: 'twitter',    label: 'Twitter',    href: (v) => `https://twitter.com/${v}`,                 icon: '𝕏' },
    { key: 'kalshi',     label: 'Kalshi',     href: (v) => `https://kalshi.com/profile/${v}`,           icon: 'K' },
    { key: 'polymarket', label: 'Polymarket', href: (v) => `https://polymarket.com/profile/${v}`,       icon: 'P' },
    { key: 'manifold',   label: 'Manifold',   href: (v) => `https://manifold.markets/${v}`,             icon: 'M' },
    { key: 'metaculus',  label: 'Metaculus',  href: (v) => `https://metaculus.com/accounts/profile/${v}/`, icon: 'Q' },
    { key: 'website',    label: 'Website',    href: (v) => v.startsWith('http') ? v : `https://${v}`,  icon: '↗' },
  ];

  const activeSocials = socialDefs.filter(
    (s) => user.social_links?.[s.key]
  );
</script>

<svelte:head>
  <title>@{user.username} — Tiresias</title>
  <meta name="description" content="{displayName}'s forecasting profile on Tiresias — {score.resolved_predictions} resolved predictions, Brier Skill Score {fmt(score.brier_skill_score, 3)}." />
</svelte:head>

<!-- ===== Profile Header ===== -->
<header class="profile-header">
  <div class="avatar-wrap">
    {#if user.avatar_url}
      <img class="avatar" src={user.avatar_url} alt="{displayName} avatar" />
    {:else}
      <div class="avatar avatar-placeholder">
        {displayName[0].toUpperCase()}
      </div>
    {/if}
  </div>

  <div class="profile-meta">
    <h1 class="display-name">{displayName}</h1>
    <p class="username">@{user.username} · forecasting since {fmtYear(user.created_at)}</p>
    {#if user.bio}
      <p class="bio">{user.bio}</p>
    {/if}

    {#if activeSocials.length}
      <div class="socials">
        {#each activeSocials as social}
          <a
            class="social-link"
            href={social.href(user.social_links[social.key])}
            target="_blank"
            rel="noopener noreferrer"
            title={social.label}
          >
            <span class="social-icon">{social.icon}</span>
            <span class="social-label">{social.label}</span>
          </a>
        {/each}
      </div>
    {/if}
  </div>
</header>

<!-- ===== Stat Cards ===== -->
<section class="cards">
  <div class="card stat-card">
    <div class="stat-label">Mean Brier Score</div>
    <div class="stat-value">{fmt(score.mean_brier_score)}</div>
    <div class="stat-sub">lower is better · 0 = perfect</div>
  </div>
  <div class="card stat-card">
    <div class="stat-label">Brier Skill Score</div>
    <div class="stat-value {score.brier_skill_score > 0 ? 'positive' : ''}">{fmt(score.brier_skill_score)}</div>
    <div class="stat-sub">BSS &gt; 0 beats the baseline</div>
  </div>
  <div class="card stat-card">
    <div class="stat-label">Accuracy</div>
    <div class="stat-value">{fmtPct(score.accuracy)}</div>
    <div class="stat-sub">directional correctness</div>
  </div>
  <div class="card stat-card">
    <div class="stat-label">Predictions</div>
    <div class="stat-value">
      {score.resolved_predictions}<span class="stat-denom"> / {score.total_predictions}</span>
    </div>
    <div class="stat-sub">{resolutionRate}% resolved</div>
  </div>
</section>

<!-- ===== Badges + Platform side-by-side ===== -->
<section class="mid-row">

  <!-- Badges -->
  <div class="card badge-card">
    <h2 class="section-title">
      Badges
      <span class="badge-count">{earnedBadges.length} / {badges.length}</span>
    </h2>
    <div class="badge-grid">
      {#each earnedBadges as badge}
        <div class="badge badge-earned" title="{badge.description}\nEarned {fmtDate(badge.earned_at)}">
          <span class="badge-icon">{badge.icon}</span>
          <span class="badge-name">{badge.name}</span>
        </div>
      {/each}
      {#each lockedBadges as badge}
        <div class="badge badge-locked" title={badge.description}>
          <span class="badge-icon">🔒</span>
          <span class="badge-name">{badge.name}</span>
        </div>
      {/each}
    </div>
  </div>

  <!-- Platform Breakdown -->
  <div class="card platform-card">
    <h2 class="section-title">Platform Breakdown</h2>
    <p class="section-sub">Mean Brier score per platform — lower is better</p>
    <div class="platform-list">
      {#each sortedPlatforms as [platform, brierMean]}
        <div class="platform-row">
          <span
            class="platform-chip"
            style="background:{sourceColor(platform)}18;color:{sourceColor(platform)}"
          >{platform}</span>
          <div class="bar-wrap">
            <div
              class="bar"
              style="width:{Math.round((1 - brierMean) * 100)}%;background:{sourceColor(platform)}"
            ></div>
          </div>
          <span class="platform-score">{fmt(brierMean)}</span>
        </div>
      {/each}
    </div>
  </div>

</section>

<!-- ===== Recent Resolved Predictions ===== -->
<section class="card recent-card">
  <h2 class="section-title">Recent Predictions</h2>
  <table class="table">
    <thead>
      <tr>
        <th>Market</th>
        <th>Platform</th>
        <th>Probability</th>
        <th>Outcome</th>
        <th>Brier</th>
        <th>Resolved</th>
      </tr>
    </thead>
    <tbody>
      {#each recentPredictions as pred}
        <tr>
          <td class="market-title">{pred.market_title}</td>
          <td>
            <span class="source-chip" style="color:{sourceColor(pred.source)}">{pred.source}</span>
          </td>
          <td class="num">{fmtPct(pred.probability)}</td>
          <td>
            {#if pred.outcome === 'yes'}
              <span class="outcome yes">YES</span>
            {:else if pred.outcome === 'no'}
              <span class="outcome no">NO</span>
            {:else}
              <span class="outcome pending">Pending</span>
            {/if}
          </td>
          <td class="num">{pred.brier_score != null ? fmt(pred.brier_score) : '—'}</td>
          <td class="date">{fmtDate(pred.resolved_at)}</td>
        </tr>
      {/each}
    </tbody>
  </table>
</section>

<style>
  /* ===== Layout ===== */

  :global(body) {
    background: #f5f6fa;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    color: #1a1f2e;
    margin: 0;
    padding: 0;
  }

  :global(*, *::before, *::after) {
    box-sizing: border-box;
  }

  /* SvelteKit wraps in a <main> by default via app.html; we just control
     internal layout. Cap width and center for a clean profile feel. */
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

  /* ===== Profile Header ===== */

  .profile-header {
    display: flex;
    align-items: flex-start;
    gap: 24px;
    margin-bottom: 28px;
    flex-wrap: wrap;
  }

  .avatar-wrap {
    flex-shrink: 0;
  }

  .avatar {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    object-fit: cover;
  }

  .avatar-placeholder {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    background: linear-gradient(135deg, #4f8ef7 0%, #6c5ce7 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 32px;
    font-weight: 700;
    color: #fff;
    user-select: none;
  }

  .profile-meta {
    flex: 1;
    min-width: 0;
  }

  .display-name {
    font-size: 26px;
    font-weight: 700;
    color: #1a1f2e;
    margin: 0 0 4px;
    line-height: 1.2;
  }

  .username {
    font-size: 14px;
    color: #9ca3af;
    margin: 0 0 10px;
  }

  .bio {
    font-size: 14px;
    color: #4b5563;
    margin: 0 0 14px;
    line-height: 1.55;
    max-width: 540px;
  }

  .socials {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .social-link {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 13px;
    font-weight: 500;
    color: #4b5563;
    background: #f3f4f6;
    border-radius: 20px;
    padding: 4px 12px;
    text-decoration: none;
    transition: background 0.15s, color 0.15s;
  }

  .social-link:hover {
    background: #e5e7eb;
    color: #1a1f2e;
  }

  .social-icon {
    font-style: normal;
    font-size: 13px;
    font-weight: 700;
  }

  /* ===== Stat Cards ===== */

  .cards {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 20px;
  }

  .stat-card {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .stat-label {
    font-size: 11px;
    font-weight: 700;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 0.07em;
  }

  .stat-value {
    font-size: 30px;
    font-weight: 700;
    color: #1a1f2e;
    line-height: 1.1;
  }

  .stat-value.positive {
    color: #059669;
  }

  .stat-denom {
    font-size: 18px;
    font-weight: 400;
    color: #9ca3af;
  }

  .stat-sub {
    font-size: 12px;
    color: #9ca3af;
  }

  /* ===== Mid row (badges + platforms) ===== */

  .mid-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 20px;
  }

  .section-title {
    font-size: 15px;
    font-weight: 600;
    color: #374151;
    margin: 0 0 16px;
    display: flex;
    align-items: baseline;
    gap: 6px;
  }

  .section-sub {
    font-size: 12px;
    color: #9ca3af;
    margin: -10px 0 14px;
  }

  /* ===== Badges ===== */

  .badge-count {
    font-weight: 400;
    color: #9ca3af;
    font-size: 13px;
  }

  .badge-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
  }

  .badge {
    border-radius: 10px;
    padding: 12px 8px;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 5px;
    cursor: default;
  }

  .badge-earned {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
  }

  .badge-locked {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    opacity: 0.55;
  }

  .badge-icon {
    font-size: 22px;
  }

  .badge-name {
    font-size: 11px;
    font-weight: 600;
    color: #374151;
    line-height: 1.3;
  }

  /* ===== Platform Breakdown ===== */

  .platform-list {
    display: flex;
    flex-direction: column;
    gap: 13px;
  }

  .platform-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .platform-chip {
    font-size: 12px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 20px;
    width: 96px;
    text-align: center;
    flex-shrink: 0;
    text-transform: capitalize;
  }

  .bar-wrap {
    flex: 1;
    background: #f3f4f6;
    border-radius: 4px;
    height: 8px;
    overflow: hidden;
  }

  .bar {
    height: 100%;
    border-radius: 4px;
    transition: width 0.5s ease;
  }

  .platform-score {
    font-size: 13px;
    font-weight: 600;
    color: #374151;
    width: 40px;
    text-align: right;
    flex-shrink: 0;
  }

  /* ===== Recent Predictions ===== */

  .recent-card {
    /* full-width below mid-row */
  }

  .table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
  }

  .table th {
    text-align: left;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #9ca3af;
    padding: 0 12px 10px 0;
    border-bottom: 1px solid #f3f4f6;
  }

  .table td {
    padding: 12px 12px 12px 0;
    border-bottom: 1px solid #f9fafb;
    vertical-align: middle;
    color: #374151;
  }

  .table tbody tr:last-child td {
    border-bottom: none;
  }

  .market-title {
    max-width: 300px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: #1a1f2e;
    font-weight: 500;
  }

  .source-chip {
    font-size: 12px;
    font-weight: 600;
    text-transform: capitalize;
  }

  .num {
    font-variant-numeric: tabular-nums;
    font-weight: 500;
  }

  .outcome {
    display: inline-block;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 20px;
    letter-spacing: 0.04em;
  }

  .outcome.yes     { background: #d1fae5; color: #065f46; }
  .outcome.no      { background: #fee2e2; color: #991b1b; }
  .outcome.pending { background: #fef3c7; color: #92400e; }

  .date {
    color: #9ca3af;
    font-size: 13px;
    white-space: nowrap;
  }

  /* ===== Responsive ===== */

  @media (max-width: 860px) {
    .cards {
      grid-template-columns: repeat(2, 1fr);
    }
    .mid-row {
      grid-template-columns: 1fr;
    }
    .badge-grid {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  @media (max-width: 540px) {
    .cards {
      grid-template-columns: repeat(2, 1fr);
    }
    .badge-grid {
      grid-template-columns: repeat(2, 1fr);
    }
    .market-title {
      max-width: 160px;
    }
  }
</style>

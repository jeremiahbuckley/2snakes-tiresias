<script>
  /** @type {import('./$types').PageData} */
  export let data;

  const { user, score, badges, recentPredictions } = data;

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

  const earnedBadges = badges.filter((b) => b.earned);
  const lockedBadges = badges.filter((b) => !b.earned);

  const resolutionRate = score.total_predictions
    ? ((score.resolved_predictions / score.total_predictions) * 100).toFixed(0)
    : 0;

  // True when no market has resolved yet — scores are null
  const noScoringData = score.mean_brier_score == null;

  const platformColors = {
    kalshi: '#00b894',
    polymarket: '#6c5ce7',
    manifold: '#e17055',
    metaculus: '#0984e3',
  };

  function sourceColor(source) {
    return platformColors[source] ?? '#aaa';
  }

  const perSource = Object.entries(score.per_source ?? {});
</script>

<svelte:head>
  <title>Dashboard — Tiresias</title>
</svelte:head>

<div class="page-header">
  <div>
    <h1>Dashboard</h1>
    <p class="welcome">Welcome back, {user.display_name ?? user.username}</p>
  </div>
  {#if score.last_scored_at}
    <div class="last-scored">Last scored: {fmtDate(score.last_scored_at)}</div>
  {/if}
</div>

<!-- Score Summary Cards -->
<section class="cards">
  <div class="card stat-card">
    <div class="stat-label">Mean Brier Score</div>
    <div class="stat-value">{fmt(score.mean_brier_score)}</div>
    <div class="stat-sub">lower is better · 0 = perfect</div>
  </div>
  <div class="card stat-card">
    <div class="stat-label">Brier Skill Score</div>
    <div class="stat-value positive">{fmt(score.brier_skill_score)}</div>
    <div class="stat-sub">BSS &gt; 0 = beats baseline</div>
  </div>
  <div class="card stat-card">
    <div class="stat-label">Accuracy</div>
    <div class="stat-value">{fmtPct(score.accuracy)}</div>
    <div class="stat-sub">directional correctness</div>
  </div>
  <div class="card stat-card">
    <div class="stat-label">Predictions</div>
    <div class="stat-value">
      {score.resolved_predictions}
      <span class="stat-denom">/ {score.total_predictions}</span>
    </div>
    <div class="stat-sub">{resolutionRate}% resolved</div>
  </div>
</section>

<!-- Pending-data notice when no markets have resolved yet -->
{#if noScoringData && score.total_predictions > 0}
  <div class="pending-notice">
    <span class="pending-icon">⏳</span>
    <div>
      <strong>{score.total_predictions} prediction{score.total_predictions !== 1 ? 's' : ''} being tracked</strong>
      — Brier scores, calibration, and platform breakdown will appear as your predicted markets resolve.
    </div>
  </div>
{:else if score.total_predictions === 0}
  <div class="pending-notice">
    <span class="pending-icon">📡</span>
    <div>
      <strong>No predictions yet</strong>
      — Link a forecasting platform in <a href="/settings">Settings</a> to start tracking your predictions.
    </div>
  </div>
{/if}

<!-- Platform Breakdown + Badges (only show when there's data to display) -->
{#if perSource.length > 0 || earnedBadges.length > 0 || lockedBadges.length > 0}
  <section class="row-section">
    <!-- Platform Breakdown -->
    <div class="card platform-card">
      <h2 class="section-title">Platform Breakdown</h2>
      {#if perSource.length > 0}
        <div class="platform-list">
          {#each perSource as [platform, brierMean]}
            <div class="platform-row">
              <span class="platform-badge" style="background:{sourceColor(platform)}20;color:{sourceColor(platform)}">
                {platform}
              </span>
              <div class="platform-bar-wrap">
                <div class="platform-bar" style="width:{Math.round((1 - brierMean) * 100)}%;background:{sourceColor(platform)}"></div>
              </div>
              <span class="platform-score">{fmt(brierMean)}</span>
            </div>
          {/each}
        </div>
      {:else}
        <p class="section-empty">Appears after your first market resolves.</p>
      {/if}
    </div>

    <!-- Badges -->
    <div class="card badge-card">
      <h2 class="section-title">Badges <span class="badge-count">{earnedBadges.length}/{badges.length}</span></h2>
      {#if badges.length > 0}
        <div class="badge-grid">
          {#each earnedBadges as badge}
            <div class="badge badge-earned" title={badge.description}>
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
      {:else}
        <p class="section-empty">Badges unlock as you hit forecasting milestones.</p>
      {/if}
    </div>
  </section>
{/if}

<!-- Recent Activity -->
<section class="card">
  <div class="section-header">
    <h2 class="section-title">Recent Activity</h2>
    <a href="/predictions" class="view-all">View all →</a>
  </div>
  {#if recentPredictions.length === 0}
    <p class="section-empty" style="padding: 24px 0 8px;">No predictions yet — <a href="/settings">connect a platform</a> to get started.</p>
  {:else}
    <table class="table">
      <thead>
        <tr>
          <th>Market</th>
          <th>Platform</th>
          <th>Probability</th>
          <th>Outcome</th>
          <th>Brier</th>
          <th>Date</th>
        </tr>
      </thead>
      <tbody>
        {#each recentPredictions as pred}
          <tr>
            <td class="market-title">{pred.market_title}</td>
            <td>
              <span class="source-chip" style="color:{sourceColor(pred.source)};">
                {pred.source}
              </span>
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
            <td class="date">{fmtDate(pred.created_at)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</section>

<style>
  .page-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 28px;
    flex-wrap: wrap;
    gap: 8px;
  }

  h1 {
    font-size: 26px;
    color: #1a1f2e;
  }

  .welcome {
    color: #6b7280;
    font-size: 14px;
    margin-top: 4px;
  }

  .last-scored {
    font-size: 13px;
    color: #9ca3af;
    padding-top: 6px;
  }

  /* ---- Pending notice ---- */
  .pending-notice {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    background: #f0f9ff;
    border: 1px solid #bae6fd;
    border-radius: 10px;
    padding: 14px 18px;
    font-size: 14px;
    color: #0c4a6e;
    margin-bottom: 20px;
    line-height: 1.5;
  }

  .pending-notice a {
    color: #0284c7;
    font-weight: 500;
  }

  .pending-icon {
    font-size: 18px;
    flex-shrink: 0;
    margin-top: 1px;
  }

  /* ---- Cards ---- */
  .card {
    background: #fff;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.07);
  }

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
    font-size: 12px;
    font-weight: 600;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 0.06em;
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

  /* ---- Row section (platform + badges side by side) ---- */
  .row-section {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 20px;
  }

  .section-title {
    font-size: 15px;
    font-weight: 600;
    color: #374151;
    margin-bottom: 16px;
  }

  .section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  .section-header .section-title {
    margin-bottom: 0;
  }

  .section-empty {
    font-size: 13px;
    color: #9ca3af;
    line-height: 1.5;
  }

  .section-empty a {
    color: #4f8ef7;
  }

  .view-all {
    font-size: 13px;
    color: #4f8ef7;
    font-weight: 500;
  }

  /* ---- Platform breakdown ---- */
  .platform-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .platform-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .platform-badge {
    font-size: 12px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 20px;
    width: 90px;
    text-align: center;
    flex-shrink: 0;
    text-transform: capitalize;
  }

  .platform-bar-wrap {
    flex: 1;
    background: #f3f4f6;
    border-radius: 4px;
    height: 8px;
    overflow: hidden;
  }

  .platform-bar {
    height: 100%;
    border-radius: 4px;
    transition: width 0.4s ease;
  }

  .platform-score {
    font-size: 13px;
    font-weight: 600;
    color: #374151;
    width: 40px;
    text-align: right;
    flex-shrink: 0;
  }

  /* ---- Badges ---- */
  .badge-count {
    font-weight: 400;
    color: #9ca3af;
    margin-left: 6px;
    font-size: 13px;
  }

  .badge-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
  }

  .badge {
    border-radius: 10px;
    padding: 10px 8px;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
  }

  .badge-earned {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
  }

  .badge-locked {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    opacity: 0.6;
  }

  .badge-icon {
    font-size: 22px;
  }

  .badge-name {
    font-size: 11px;
    font-weight: 600;
    color: #374151;
    line-height: 1.3;
    text-align: center;
  }

  /* ---- Table ---- */
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

  @media (max-width: 1100px) {
    .cards {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  @media (max-width: 768px) {
    .row-section {
      grid-template-columns: 1fr;
    }

    .cards {
      grid-template-columns: repeat(2, 1fr);
    }
  }
</style>

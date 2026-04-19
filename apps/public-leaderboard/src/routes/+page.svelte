<script>
  /** @type {import('./$types').PageData} */
  export let data;

  const { entries, generated_at, snapshot_period, total_forecasters } = data;

  // ---- Sort state ----
  // Columns where lower is better: mean_brier_score
  // Everything else: higher is better
  const lowerIsBetter = new Set(['mean_brier_score']);

  let sortKey = 'rank';
  let sortDir = 'asc'; // 'asc' | 'desc'

  function setSort(key) {
    if (sortKey === key) {
      sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      sortKey = key;
      // Sensible defaults: rank ascending, everything else best-first
      if (key === 'rank') {
        sortDir = 'asc';
      } else {
        sortDir = lowerIsBetter.has(key) ? 'asc' : 'desc';
      }
    }
  }

  $: sortedEntries = [...entries].sort((a, b) => {
    const av = sortKey === 'username' ? a.user.username : a[sortKey];
    const bv = sortKey === 'username' ? b.user.username : b[sortKey];
    if (av === bv) return 0;
    const cmp = av > bv ? 1 : -1;
    return sortDir === 'asc' ? cmp : -cmp;
  });

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
  function fmtInt(n) {
    return n == null ? '—' : n.toLocaleString('en-US');
  }

  const platformColors = {
    kalshi:     '#00b894',
    polymarket: '#6c5ce7',
    manifold:   '#e17055',
    metaculus:  '#0984e3',
  };
  function sourceColor(s) {
    return platformColors[s] ?? '#aaa';
  }

  function sortIndicator(key) {
    if (sortKey !== key) return '';
    return sortDir === 'asc' ? ' ▲' : ' ▼';
  }
</script>

<svelte:head>
  <title>Leaderboard — Tiresias</title>
  <meta
    name="description"
    content="Top forecasters on Tiresias ranked by Brier Skill Score across Kalshi, Polymarket, Manifold, and Metaculus."
  />
</svelte:head>

<!-- ===== Header ===== -->
<header class="page-header">
  <div class="tiresias-wordmark">Tiresias</div>
  <h1 class="page-title">Leaderboard</h1>
  <p class="page-sub">
    Top forecasters by Brier Skill Score · {snapshot_period} · {fmtInt(total_forecasters)} ranked
  </p>
  <p class="page-sub dim">Updated {fmtDate(generated_at)}</p>
</header>

<!-- ===== Table ===== -->
<section class="card table-card">
  <div class="table-scroll">
    <table class="table">
      <thead>
        <tr>
          <th class="num-head sortable" on:click={() => setSort('rank')}>#{sortIndicator('rank')}</th>
          <th class="sortable" on:click={() => setSort('username')}>Forecaster{sortIndicator('username')}</th>
          <th class="num-head sortable" on:click={() => setSort('brier_skill_score')}>BSS{sortIndicator('brier_skill_score')}</th>
          <th class="num-head sortable" on:click={() => setSort('mean_brier_score')}>Brier{sortIndicator('mean_brier_score')}</th>
          <th class="num-head sortable" on:click={() => setSort('calibration_score')}>Calibration{sortIndicator('calibration_score')}</th>
          <th class="num-head sortable" on:click={() => setSort('accuracy')}>Accuracy{sortIndicator('accuracy')}</th>
          <th class="num-head sortable" on:click={() => setSort('resolved_predictions')}>Resolved{sortIndicator('resolved_predictions')}</th>
          <th>Platforms</th>
        </tr>
      </thead>
      <tbody>
        {#each sortedEntries as entry (entry.user.id)}
          <tr>
            <td class="num rank">{entry.rank}</td>
            <td class="name-cell">
              <a class="user-link" href="/{entry.user.username}">
                <span class="display-name">{entry.user.display_name}</span>
                <span class="handle">@{entry.user.username}</span>
              </a>
            </td>
            <td class="num {entry.brier_skill_score > 0 ? 'positive' : 'negative'}">
              {fmt(entry.brier_skill_score)}
            </td>
            <td class="num">{fmt(entry.mean_brier_score)}</td>
            <td class="num">{fmtPct(entry.calibration_score)}</td>
            <td class="num">{fmtPct(entry.accuracy)}</td>
            <td class="num">{fmtInt(entry.resolved_predictions)}</td>
            <td>
              <div class="platform-chips">
                {#each entry.platforms as p}
                  <span
                    class="platform-chip"
                    style="background:{sourceColor(p)}18;color:{sourceColor(p)}"
                  >{p}</span>
                {/each}
              </div>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</section>

<!-- ===== Legend ===== -->
<section class="legend card">
  <h2 class="section-title">How scoring works</h2>
  <dl class="legend-grid">
    <div>
      <dt>BSS — Brier Skill Score</dt>
      <dd>How much better than a naive baseline (climatology). &gt; 0 beats the baseline; &lt; 0 is worse.</dd>
    </div>
    <div>
      <dt>Brier — Mean Brier Score</dt>
      <dd>Average squared error across resolved predictions. Lower is better (0 = perfect).</dd>
    </div>
    <div>
      <dt>Calibration</dt>
      <dd>How closely stated probabilities match realized frequencies. Higher is better.</dd>
    </div>
    <div>
      <dt>Accuracy</dt>
      <dd>Directional correctness — share of predictions where the forecaster was on the right side of 50%.</dd>
    </div>
  </dl>
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
    max-width: 1040px;
    margin: 0 auto;
    padding: 40px 24px 64px;
  }

  .card {
    background: #fff;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.07);
  }

  /* ---- Page header ---- */
  .page-header {
    margin-bottom: 24px;
  }
  .tiresias-wordmark {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #4f8ef7;
    margin-bottom: 12px;
  }
  .page-title {
    font-size: 28px;
    font-weight: 700;
    margin: 0 0 4px;
    line-height: 1.2;
  }
  .page-sub {
    font-size: 13px;
    color: #6b7280;
    margin: 2px 0;
  }
  .page-sub.dim { color: #9ca3af; font-size: 12px; }

  /* ---- Table ---- */
  .table-card { padding: 8px 8px; }
  .table-scroll { overflow-x: auto; }
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
    padding: 14px 12px;
    border-bottom: 1px solid #f3f4f6;
    white-space: nowrap;
    background: #fafbfc;
    user-select: none;
  }
  .table th.sortable { cursor: pointer; }
  .table th.sortable:hover { color: #4f8ef7; }
  .table th.num-head { text-align: right; }
  .table td {
    padding: 14px 12px;
    border-bottom: 1px solid #f9fafb;
    vertical-align: middle;
    color: #374151;
  }
  .table tbody tr:last-child td { border-bottom: none; }
  .table tbody tr:hover { background: #f9fafb; }

  .num {
    font-variant-numeric: tabular-nums;
    font-weight: 500;
    text-align: right;
    white-space: nowrap;
  }
  .num.rank {
    font-weight: 700;
    color: #1a1f2e;
    width: 48px;
  }
  .num.positive { color: #059669; }
  .num.negative { color: #dc2626; }

  /* ---- Forecaster name cell ---- */
  .name-cell { min-width: 180px; }
  .user-link {
    display: flex;
    flex-direction: column;
    text-decoration: none;
    color: inherit;
    line-height: 1.25;
  }
  .user-link:hover .display-name { color: #4f8ef7; }
  .display-name {
    font-size: 14px;
    font-weight: 600;
    color: #1a1f2e;
  }
  .handle {
    font-size: 12px;
    color: #9ca3af;
  }

  /* ---- Platform chips ---- */
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
    white-space: nowrap;
  }

  /* ---- Legend ---- */
  .legend { margin-top: 20px; }
  .section-title {
    font-size: 15px;
    font-weight: 600;
    color: #374151;
    margin: 0 0 16px;
  }
  .legend-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px 24px;
    margin: 0;
  }
  .legend-grid dt {
    font-size: 13px;
    font-weight: 700;
    color: #1a1f2e;
    margin-bottom: 3px;
  }
  .legend-grid dd {
    font-size: 13px;
    color: #6b7280;
    line-height: 1.5;
    margin: 0;
  }

  @media (max-width: 720px) {
    .legend-grid { grid-template-columns: 1fr; }
    .table th, .table td { padding: 10px 8px; font-size: 13px; }
  }
</style>

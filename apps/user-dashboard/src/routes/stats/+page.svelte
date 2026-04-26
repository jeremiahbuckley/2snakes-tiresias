<script>
  /** @type {import('./$types').PageData} */
  export let data;

  const { score, calibration, brierTimeline } = data;

  function fmt(n, d = 3) {
    return n == null ? '—' : n.toFixed(d);
  }

  function fmtPct(n) {
    return n == null ? '—' : `${(n * 100).toFixed(1)}%`;
  }

  // ---- Calibration SVG chart ----
  const hasCalibration = calibration.length > 0;

  const CAL_W = 500;
  const CAL_H = 260;
  const CAL_PAD = { top: 20, right: 20, bottom: 50, left: 52 };
  const calInnerW = CAL_W - CAL_PAD.left - CAL_PAD.right;
  const calInnerH = CAL_H - CAL_PAD.top - CAL_PAD.bottom;

  const numBins = calibration.length || 1; // avoid division by zero
  const barWidth = calInnerW / numBins;
  const BAR_GAP = 4;

  function calX(i) {
    return CAL_PAD.left + i * barWidth + BAR_GAP / 2;
  }

  function calY(frac) {
    return CAL_PAD.top + calInnerH - frac * calInnerH;
  }

  // ---- Brier timeline SVG chart ----
  const hasTimeline = brierTimeline.length > 1;

  const TL_W = 600;
  const TL_H = 220;
  const TL_PAD = { top: 20, right: 20, bottom: 40, left: 52 };
  const tlInnerW = TL_W - TL_PAD.left - TL_PAD.right;
  const tlInnerH = TL_H - TL_PAD.top - TL_PAD.bottom;

  const tlScores = brierTimeline.map((d) => d.score);
  const tlMin = hasTimeline ? Math.max(0, Math.min(...tlScores) - 0.02) : 0;
  const tlMax = hasTimeline ? Math.min(1, Math.max(...tlScores) + 0.02) : 1;

  function tlX(i) {
    return TL_PAD.left + (i / Math.max(brierTimeline.length - 1, 1)) * tlInnerW;
  }

  function tlY(s) {
    const range = tlMax - tlMin || 1;
    return TL_PAD.top + tlInnerH - ((s - tlMin) / range) * tlInnerH;
  }

  const timelinePath =
    'M ' +
    brierTimeline
      .map((d, i) => `${tlX(i)} ${tlY(d.score)}`)
      .join(' L ');

  const areaPath =
    `M ${tlX(0)} ${TL_PAD.top + tlInnerH} L ` +
    brierTimeline.map((d, i) => `${tlX(i)} ${tlY(d.score)}`).join(' L ') +
    ` L ${tlX(brierTimeline.length - 1)} ${TL_PAD.top + tlInnerH} Z`;

  const tlTicks = [tlMin, (tlMin + tlMax) / 2, tlMax].map((v) => ({
    y: tlY(v),
    label: v.toFixed(2),
  }));

  const tlXLabels = brierTimeline
    .map((d, i) => ({ i, label: d.date }))
    .filter((_, i) => i % 3 === 0);

  // Domain breakdown sorted best → worst
  const domains = Object.entries(score.per_domain ?? {}).sort((a, b) => a[1] - b[1]);

  // Platform breakdown sorted best → worst
  const platforms = Object.entries(score.per_source ?? {}).sort((a, b) => a[1] - b[1]);

  const platformColors = {
    kalshi: '#00b894',
    polymarket: '#6c5ce7',
    manifold: '#e17055',
    metaculus: '#0984e3',
  };
</script>

<svelte:head>
  <title>Stats — Tiresias</title>
</svelte:head>

<div class="page-header">
  <h1>Stats</h1>
  <p class="subtitle">Your forecasting accuracy over time</p>
</div>

<!-- Top stat row -->
<section class="cards">
  <div class="card stat-card">
    <div class="stat-label">Mean Brier Score</div>
    <div class="stat-value">{fmt(score.mean_brier_score)}</div>
    <div class="stat-sub">lower is better</div>
  </div>
  <div class="card stat-card">
    <div class="stat-label">Brier Skill Score</div>
    <div class="stat-value positive">{fmt(score.brier_skill_score)}</div>
    <div class="stat-sub">vs. uninformed baseline</div>
  </div>
  <div class="card stat-card">
    <div class="stat-label">Calibration Score</div>
    <div class="stat-value">{fmtPct(score.calibration_score)}</div>
    <div class="stat-sub">100% = perfectly calibrated</div>
  </div>
  <div class="card stat-card">
    <div class="stat-label">Accuracy</div>
    <div class="stat-value">{fmtPct(score.accuracy)}</div>
    <div class="stat-sub">directional correctness</div>
  </div>
</section>

<!-- Charts row -->
<section class="charts-row">
  <!-- Calibration Chart -->
  <div class="card chart-card">
    <h2 class="section-title">Calibration Curve</h2>
    <p class="chart-desc">
      When you say 70%, does it happen 70% of the time?
      Bars show your actual frequencies; the line shows perfect calibration.
    </p>
    {#if hasCalibration}
      <div class="chart-scroll">
        <svg viewBox="0 0 {CAL_W} {CAL_H}" width="100%" class="cal-svg">
          <!-- Y axis ticks -->
          {#each [0, 0.25, 0.5, 0.75, 1.0] as tick}
            <line
              x1={CAL_PAD.left}
              y1={calY(tick)}
              x2={CAL_PAD.left + calInnerW}
              y2={calY(tick)}
              stroke="#f3f4f6"
              stroke-width="1"
            />
            <text
              x={CAL_PAD.left - 8}
              y={calY(tick) + 4}
              text-anchor="end"
              font-size="11"
              fill="#9ca3af"
            >{(tick * 100).toFixed(0)}%</text>
          {/each}

          <!-- Bars (actual frequencies) -->
          {#each calibration as bucket, i}
            {#if bucket.actual != null}
              <rect
                x={calX(i)}
                y={calY(bucket.actual)}
                width={barWidth - BAR_GAP}
                height={calInnerH - (calY(bucket.actual) - CAL_PAD.top)}
                fill="#4f8ef7"
                opacity="0.75"
                rx="2"
              />
            {/if}
            <!-- Predicted tick -->
            <line
              x1={calX(i)}
              y1={calY(bucket.predicted)}
              x2={calX(i) + barWidth - BAR_GAP}
              y2={calY(bucket.predicted)}
              stroke="#1a1f2e"
              stroke-width="2"
              stroke-dasharray="3,2"
            />
            <!-- X axis label -->
            <text
              x={calX(i) + (barWidth - BAR_GAP) / 2}
              y={CAL_PAD.top + calInnerH + 18}
              text-anchor="middle"
              font-size="10"
              fill="#9ca3af"
            >{bucket.bin}</text>
          {/each}

          <!-- Perfect calibration line -->
          <line
            x1={CAL_PAD.left}
            y1={calY(0)}
            x2={CAL_PAD.left + calInnerW}
            y2={calY(1)}
            stroke="#10b981"
            stroke-width="1.5"
            stroke-dasharray="5,4"
            opacity="0.6"
          />

          <!-- Legend -->
          <rect x={CAL_PAD.left} y={CAL_H - 14} width="10" height="10" fill="#4f8ef7" rx="2" opacity="0.75" />
          <text x={CAL_PAD.left + 14} y={CAL_H - 5} font-size="11" fill="#6b7280">Actual frequency</text>
          <line x1={CAL_PAD.left + 110} y1={CAL_H - 9} x2={CAL_PAD.left + 126} y2={CAL_H - 9} stroke="#10b981" stroke-width="1.5" stroke-dasharray="4,3" />
          <text x={CAL_PAD.left + 130} y={CAL_H - 5} font-size="11" fill="#6b7280">Perfect calibration</text>
        </svg>
      </div>
    {:else}
      <div class="chart-empty">
        <span class="chart-empty-icon">📊</span>
        <p>Calibration data appears once your predicted markets start resolving.</p>
      </div>
    {/if}
  </div>

  <!-- Brier Timeline -->
  <div class="card chart-card">
    <h2 class="section-title">Brier Score Over Time</h2>
    <p class="chart-desc">
      Rolling monthly mean Brier score. Downward trend = improving accuracy.
    </p>
    {#if hasTimeline}
      <div class="chart-scroll">
        <svg viewBox="0 0 {TL_W} {TL_H}" width="100%" class="tl-svg">
          <!-- Y-axis gridlines -->
          {#each tlTicks as tick}
            <line
              x1={TL_PAD.left}
              y1={tick.y}
              x2={TL_PAD.left + tlInnerW}
              y2={tick.y}
              stroke="#f3f4f6"
              stroke-width="1"
            />
            <text
              x={TL_PAD.left - 8}
              y={tick.y + 4}
              text-anchor="end"
              font-size="11"
              fill="#9ca3af"
            >{tick.label}</text>
          {/each}

          <!-- Shaded area -->
          <path d={areaPath} fill="#4f8ef7" opacity="0.08" />

          <!-- Line -->
          <path d={timelinePath} fill="none" stroke="#4f8ef7" stroke-width="2.5" stroke-linejoin="round" />

          <!-- Data points -->
          {#each brierTimeline as point, i}
            <circle
              cx={tlX(i)}
              cy={tlY(point.score)}
              r="3"
              fill="#4f8ef7"
              stroke="#fff"
              stroke-width="1.5"
            />
          {/each}

          <!-- X-axis labels -->
          {#each tlXLabels as lbl}
            <text
              x={tlX(lbl.i)}
              y={TL_PAD.top + tlInnerH + 20}
              text-anchor="middle"
              font-size="11"
              fill="#9ca3af"
            >{lbl.label}</text>
          {/each}
        </svg>
      </div>
    {:else}
      <div class="chart-empty">
        <span class="chart-empty-icon">📈</span>
        <p>Score history appears after markets resolve across multiple months.</p>
      </div>
    {/if}
  </div>
</section>

<!-- Domain + Platform breakdowns -->
{#if domains.length > 0 || platforms.length > 0}
  <section class="breakdown-row">
    <!-- Domain breakdown -->
    <div class="card">
      <h2 class="section-title">By Domain</h2>
      {#if domains.length > 0}
        <div class="breakdown-list">
          {#each domains as [domain, s]}
            <div class="breakdown-row-item">
              <span class="breakdown-label">{domain}</span>
              <div class="breakdown-bar-wrap">
                <div
                  class="breakdown-bar domain-bar"
                  style="width:{Math.round((1 - s) * 100)}%"
                ></div>
              </div>
              <span class="breakdown-score">{s.toFixed(3)}</span>
            </div>
          {/each}
        </div>
      {:else}
        <p class="section-empty">Appears after markets resolve.</p>
      {/if}
    </div>

    <!-- Platform breakdown -->
    <div class="card">
      <h2 class="section-title">By Platform</h2>
      {#if platforms.length > 0}
        <div class="breakdown-list">
          {#each platforms as [platform, bs]}
            <div class="breakdown-row-item">
              <span
                class="platform-badge"
                style="background:{platformColors[platform] ?? '#aaa'}20;color:{platformColors[platform] ?? '#aaa'}"
              >{platform}</span>
              <div class="breakdown-bar-wrap">
                <div
                  class="breakdown-bar"
                  style="width:{Math.round((1 - bs) * 100)}%;background:{platformColors[platform] ?? '#aaa'}"
                ></div>
              </div>
              <span class="breakdown-score">{bs.toFixed(3)}</span>
            </div>
          {/each}
        </div>
      {:else}
        <p class="section-empty">Appears after markets resolve.</p>
      {/if}
    </div>
  </section>
{:else}
  <div class="no-breakdown-notice">
    Platform and domain breakdowns will appear once your predicted markets start resolving.
  </div>
{/if}

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

  .card {
    background: #fff;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.07);
  }

  /* ---- Top stat row ---- */
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

  .stat-value.positive { color: #059669; }

  .stat-sub {
    font-size: 12px;
    color: #9ca3af;
  }

  /* ---- Charts row ---- */
  .charts-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 20px;
  }

  .chart-card {
    overflow: hidden;
  }

  .section-title {
    font-size: 15px;
    font-weight: 600;
    color: #374151;
    margin-bottom: 6px;
  }

  .section-empty {
    font-size: 13px;
    color: #9ca3af;
  }

  .chart-desc {
    font-size: 13px;
    color: #9ca3af;
    margin-bottom: 16px;
    line-height: 1.5;
  }

  .chart-scroll {
    overflow-x: auto;
  }

  .cal-svg, .tl-svg {
    display: block;
    min-width: 360px;
  }

  /* Chart empty state */
  .chart-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 32px 24px;
    text-align: center;
    gap: 10px;
  }

  .chart-empty-icon {
    font-size: 32px;
    opacity: 0.4;
  }

  .chart-empty p {
    font-size: 13px;
    color: #9ca3af;
    max-width: 260px;
    line-height: 1.5;
  }

  /* ---- Breakdown rows ---- */
  .breakdown-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }

  .breakdown-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .breakdown-row-item {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .breakdown-label {
    font-size: 13px;
    font-weight: 500;
    color: #374151;
    width: 90px;
    flex-shrink: 0;
    text-transform: capitalize;
  }

  .breakdown-bar-wrap {
    flex: 1;
    background: #f3f4f6;
    border-radius: 4px;
    height: 8px;
    overflow: hidden;
  }

  .breakdown-bar {
    height: 100%;
    border-radius: 4px;
    transition: width 0.4s ease;
  }

  .domain-bar {
    background: #4f8ef7;
  }

  .breakdown-score {
    font-size: 13px;
    font-weight: 600;
    color: #374151;
    width: 40px;
    text-align: right;
    flex-shrink: 0;
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

  .no-breakdown-notice {
    font-size: 13px;
    color: #9ca3af;
    text-align: center;
    padding: 20px;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07);
  }

  @media (max-width: 1100px) {
    .cards, .charts-row, .breakdown-row {
      grid-template-columns: 1fr 1fr;
    }
  }

  @media (max-width: 768px) {
    .cards, .charts-row, .breakdown-row {
      grid-template-columns: 1fr;
    }
  }
</style>

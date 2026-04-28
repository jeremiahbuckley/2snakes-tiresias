<script>
  import { goto } from '$app/navigation';
  import TagFilter from '$lib/components/TagFilter.svelte';

  /** @type {import('./$types').PageData} */
  export let data;

  const { shareData } = data;

  $: tagFilter = data.tagFilter ?? '';
  $: availableTags = shareData.available_tags ?? [];

  function onTagChange(e) {
    const tag = e.detail;
    const params = new URLSearchParams(typeof window !== 'undefined' ? window.location.search : '');
    if (tag) { params.set('tag', tag); } else { params.delete('tag'); }
    goto(`?${params.toString()}`, { replaceState: true });
  }

  function fmt(n, decimals = 3) {
    if (n === null || n === undefined) return '—';
    return Number(n).toFixed(decimals);
  }

  function pct(n) {
    if (n === null || n === undefined) return '—';
    return (Number(n) * 100).toFixed(1) + '%';
  }

  // Brier score: lower is better (0 = perfect, 1 = maximally wrong)
  function brierLabel(score) {
    if (score === null || score === undefined) return '';
    if (score < 0.1) return 'Excellent';
    if (score < 0.2) return 'Good';
    if (score < 0.3) return 'Fair';
    return 'Developing';
  }

  const scores = shareData.show_scores ? shareData.scores : null;
</script>

<svelte:head>
  <title>{shareData.label ? shareData.label + ' — ' : ''}Tiresias Forecaster</title>
  <meta name="description" content="A Tiresias forecaster has shared their prediction accuracy scores." />
  <!-- Open Graph card for link previews -->
  <meta property="og:title" content="Tiresias Forecaster Profile" />
  <meta property="og:description" content="Prediction accuracy scores shared anonymously via Tiresias." />
  <meta property="og:type" content="website" />
</svelte:head>

<main class="share-page">
  <header class="share-header">
    <div class="tiresias-wordmark">Tiresias</div>
    <h1 class="share-title">
      {#if shareData.label}
        {shareData.label}
      {:else}
        Anonymous Forecaster
      {/if}
    </h1>
    <p class="share-tagline">
      "I see not what is, but what must be."
    </p>
  </header>

  {#if shareData.show_predictions && availableTags.length > 0}
    <div class="page-controls">
      <TagFilter availableTags={availableTags} selectedTag={tagFilter} on:change={onTagChange} />
      {#if tagFilter}<span class="tag-indicator">Showing: {tagFilter}</span>{/if}
    </div>
  {/if}

  <!-- Scores panel -->
  {#if shareData.show_scores && scores}
    <section class="panel">
      <h2 class="panel-title">Accuracy Scores</h2>
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-value">{scores.resolved_predictions ?? '—'}</div>
          <div class="stat-label">Resolved predictions</div>
          <div class="stat-sub">of {scores.total_predictions ?? '—'} total</div>
        </div>

        <div class="stat-card stat-card-highlight">
          <div class="stat-value">{fmt(scores.mean_brier_score)}</div>
          <div class="stat-label">Mean Brier Score</div>
          <div class="stat-sub quality-label">{brierLabel(scores.mean_brier_score)} · lower is better</div>
        </div>

        <div class="stat-card">
          <div class="stat-value">{pct(scores.calibration_score)}</div>
          <div class="stat-label">Calibration</div>
          <div class="stat-sub">How well probabilities match outcomes</div>
        </div>

        <div class="stat-card">
          <div class="stat-value">{pct(scores.accuracy)}</div>
          <div class="stat-label">Directional accuracy</div>
          <div class="stat-sub">Correct side of 50%</div>
        </div>
      </div>

      {#if scores.last_scored_at}
        <p class="score-timestamp">
          Scores computed {new Date(scores.last_scored_at).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
        </p>
      {/if}
    </section>
  {/if}

  <!-- Badges panel — placeholder; real badge data would be fetched by the API -->
  {#if shareData.show_badges}
    <section class="panel">
      <h2 class="panel-title">Badges</h2>
      <p class="panel-placeholder">
        Badges earned by this forecaster will appear here once the badge service is integrated.
      </p>
    </section>
  {/if}

  <!-- Footer -->
  <footer class="share-footer">
    <p>
      Powered by <a href="https://tiresias.app" class="tiresias-link">Tiresias</a> — a cross-platform prediction accuracy tracker.
    </p>
    <p class="privacy-note">
      This forecaster's identity is not disclosed. Only the information they chose to share is shown here.
    </p>
  </footer>
</main>

<style>
  :global(body) {
    background: #f8fafc;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    margin: 0;
    color: #1a1f2e;
  }

  .share-page {
    max-width: 720px;
    margin: 0 auto;
    padding: 40px 24px 64px;
  }

  /* ---- Header ---- */
  .share-header {
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

  .share-title {
    font-size: 28px;
    font-weight: 700;
    color: #1a1f2e;
    margin: 0 0 12px;
  }

  .share-tagline {
    font-size: 15px;
    color: #6b7280;
    font-style: italic;
    margin: 0;
  }

  /* ---- Panels ---- */
  .panel {
    background: #fff;
    border-radius: 14px;
    padding: 28px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07);
    margin-bottom: 20px;
  }

  .panel-title {
    font-size: 15px;
    font-weight: 700;
    color: #1a1f2e;
    margin: 0 0 20px;
    letter-spacing: -0.01em;
  }

  .panel-placeholder {
    font-size: 14px;
    color: #9ca3af;
    font-style: italic;
  }

  /* ---- Stats grid ---- */
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;
    margin-bottom: 16px;
  }

  .stat-card {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 18px 16px;
  }

  .stat-card-highlight {
    border-color: #bfdbfe;
    background: #eff6ff;
  }

  .stat-value {
    font-size: 28px;
    font-weight: 700;
    color: #1a1f2e;
    line-height: 1.1;
    margin-bottom: 4px;
  }

  .stat-label {
    font-size: 13px;
    font-weight: 600;
    color: #374151;
    margin-bottom: 2px;
  }

  .stat-sub {
    font-size: 11px;
    color: #9ca3af;
  }

  .quality-label { color: #1d4ed8; font-weight: 600; }

  .score-timestamp {
    font-size: 12px;
    color: #9ca3af;
    margin: 0;
  }

  /* ---- Footer ---- */
  .share-footer {
    text-align: center;
    margin-top: 40px;
  }

  .share-footer p {
    font-size: 13px;
    color: #9ca3af;
    margin: 4px 0;
  }

  .tiresias-link { color: #4f8ef7; text-decoration: none; font-weight: 600; }
  .tiresias-link:hover { text-decoration: underline; }

  .privacy-note { font-style: italic; }

  .page-controls {
    max-width: 680px;
    margin: 0 auto 1.5rem;
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .tag-indicator {
    font-size: 0.875rem;
    color: var(--text-muted, #888);
    font-style: italic;
  }

  @media (max-width: 500px) {
    .stats-grid { grid-template-columns: 1fr; }
    .share-title { font-size: 22px; }
  }
</style>

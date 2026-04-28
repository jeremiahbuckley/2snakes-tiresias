<script>
  import { goto } from '$app/navigation';
  import { navigating } from '$app/stores';
  import TagFilter from '$lib/components/TagFilter.svelte';

  /** @type {import('./$types').PageData} */
  export let data;

  // Reactive — re-evaluated whenever SvelteKit updates data after goto() navigation.
  // Using const here was the filter bug: const destructuring captures values once at
  // component mount and never updates when the data prop changes.
  $: predictions = data.predictions;
  $: totals = data.totals;

  // Keep filter UI in sync with the current URL state after navigation.
  let sourceFilter = data.filters.sourceFilter;
  let statusFilter = data.filters.statusFilter;
  let sortBy = data.filters.sortBy;
  let tagFilter = data.filters.tagFilter ?? '';
  $: sourceFilter = data.filters.sourceFilter;
  $: statusFilter = data.filters.statusFilter;
  $: sortBy = data.filters.sortBy;
  $: tagFilter = data.filters.tagFilter ?? '';
  $: availableTags = data.availableTags ?? [];

  const sources = ['all', 'kalshi', 'polymarket', 'manifold', 'metaculus'];

  const sortOptions = [
    { value: 'date_desc', label: 'Newest first' },
    { value: 'date_asc', label: 'Oldest first' },
    { value: 'brier_asc', label: 'Best score first' },
    { value: 'brier_desc', label: 'Worst score first' },
  ];

  function applyFilters() {
    const params = new URLSearchParams();
    if (sourceFilter !== 'all') params.set('source', sourceFilter);
    if (statusFilter !== 'all') params.set('status', statusFilter);
    if (sortBy !== 'date_desc') params.set('sort', sortBy);
    if (tagFilter) params.set('tag', tagFilter);
    const query = params.toString();
    goto(`/predictions${query ? '?' + query : ''}`, { replaceState: true, keepFocus: true });
  }

  function onTagChange(e) {
    tagFilter = e.detail;
    applyFilters();
  }

  function fmt(n, d = 3) {
    return n == null ? '—' : n.toFixed(d);
  }

  function fmtPct(n) {
    return n == null ? '—' : `${(n * 100).toFixed(0)}%`;
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  const platformColors = {
    kalshi: '#00b894',
    polymarket: '#6c5ce7',
    manifold: '#e17055',
    metaculus: '#0984e3',
  };

  function sourceColor(source) {
    return platformColors[source] ?? '#aaa';
  }

  function scoreClass(bs) {
    if (bs == null) return '';
    if (bs < 0.1) return 'score-great';
    if (bs < 0.2) return 'score-good';
    if (bs < 0.3) return 'score-ok';
    return 'score-poor';
  }
</script>

<svelte:head>
  <title>Predictions — Tiresias</title>
</svelte:head>

<div class="page-header">
  <div>
    <h1>Predictions</h1>
    <p class="subtitle">
      {totals.resolved} resolved · {totals.pending} pending · {totals.all} total
    </p>
  </div>
</div>

<!-- Filter bar -->
<div class="filter-bar">
  <div class="filter-group">
    <label class="filter-label">Platform</label>
    <div class="source-tabs">
      {#each sources as src}
        <button
          class="tab"
          class:active={sourceFilter === src}
          on:click={() => { sourceFilter = src; applyFilters(); }}
        >
          {src === 'all' ? 'All' : src}
        </button>
      {/each}
    </div>
  </div>

  <div class="filter-group">
    <label class="filter-label">Status</label>
    <div class="source-tabs">
      <button class="tab" class:active={statusFilter === 'all'} on:click={() => { statusFilter = 'all'; applyFilters(); }}>All</button>
      <button class="tab" class:active={statusFilter === 'resolved'} on:click={() => { statusFilter = 'resolved'; applyFilters(); }}>Resolved</button>
      <button class="tab" class:active={statusFilter === 'pending'} on:click={() => { statusFilter = 'pending'; applyFilters(); }}>Pending</button>
    </div>
  </div>

  <div class="filter-group sort-group">
    <label class="filter-label" for="sort">Sort</label>
    <select id="sort" bind:value={sortBy} on:change={applyFilters}>
      {#each sortOptions as opt}
        <option value={opt.value}>{opt.label}</option>
      {/each}
    </select>
  </div>

  <TagFilter availableTags={availableTags} selectedTag={tagFilter} on:change={onTagChange} />
</div>

<!-- Table -->
<div class="card" class:loading={$navigating}>
  {#if predictions.length === 0}
    <div class="empty-state">
      <span class="empty-icon">📭</span>
      <p>No predictions match the current filters.</p>
    </div>
  {:else}
    <table class="table">
      <thead>
        <tr>
          <th>Market</th>
          <th>Platform</th>
          <th>Tags</th>
          <th>Probability</th>
          <th>Outcome</th>
          <th>Brier Score</th>
          <th>Date</th>
        </tr>
      </thead>
      <tbody>
        {#each predictions as pred}
          <tr>
            <td class="market-title" title={pred.market_title}>{pred.market_title}</td>
            <td>
              <span class="source-chip" style="color:{sourceColor(pred.source)};">
                {pred.source}
              </span>
            </td>
            <td class="col-tags">
              {#each (pred.tags ?? []) as tag}
                <button
                  class="tag-pill"
                  class:active={tagFilter === tag}
                  on:click={() => { tagFilter = tag; applyFilters(); }}
                >
                  {tag}
                </button>
              {/each}
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
            <td class="num {scoreClass(pred.brier_score)}">
              {fmt(pred.brier_score)}
            </td>
            <td class="date">{fmtDate(pred.placed_at ?? pred.created_at)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>

<style>
  .page-header {
    margin-bottom: 20px;
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

  /* ---- Filters ---- */
  .filter-bar {
    display: flex;
    align-items: flex-end;
    gap: 24px;
    margin-bottom: 20px;
    flex-wrap: wrap;
  }

  .filter-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .filter-label {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #9ca3af;
  }

  .source-tabs {
    display: flex;
    gap: 4px;
  }

  .tab {
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    background: #f3f4f6;
    border: 1px solid transparent;
    color: #6b7280;
    transition: all 0.15s;
    text-transform: capitalize;
  }

  .tab:hover {
    background: #e5e7eb;
  }

  .tab.active {
    background: #1a1f2e;
    color: #fff;
    border-color: #1a1f2e;
  }

  .sort-group select {
    padding: 7px 10px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    font-size: 13px;
    color: #374151;
    background: #fff;
    cursor: pointer;
    outline: none;
  }

  .sort-group select:focus {
    border-color: #4f8ef7;
    box-shadow: 0 0 0 3px rgba(79, 142, 247, 0.1);
  }

  /* ---- Table ---- */
  .card {
    background: #fff;
    border-radius: 12px;
    padding: 0;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.07);
    overflow: hidden;
    transition: opacity 0.15s;
  }

  .card.loading {
    opacity: 0.55;
    pointer-events: none;
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
    padding: 16px 16px;
    background: #f9fafb;
    border-bottom: 1px solid #f3f4f6;
  }

  .table td {
    padding: 14px 16px;
    border-bottom: 1px solid #f9fafb;
    vertical-align: middle;
    color: #374151;
  }

  .table tbody tr:last-child td {
    border-bottom: none;
  }

  .table tbody tr:hover {
    background: #fafbfc;
  }

  .market-title {
    max-width: 280px;
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

  .category {
    font-size: 12px;
    color: #6b7280;
    text-transform: capitalize;
  }

  .num {
    font-variant-numeric: tabular-nums;
    font-weight: 500;
  }

  .score-great { color: #059669; }
  .score-good  { color: #2563eb; }
  .score-ok    { color: #d97706; }
  .score-poor  { color: #dc2626; }

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

  .tag-pill {
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 999px;
    border: 1px solid var(--border, #ddd);
    background: #f3f4f6;
    font-size: 0.75rem;
    cursor: pointer;
    margin-right: 0.25rem;
    color: #374151;
  }

  .tag-pill.active {
    background: #1a1f2e;
    color: #fff;
    border-color: #1a1f2e;
  }

  .tag-pill:hover:not(.active) {
    background: #e5e7eb;
  }

  /* ---- Empty ---- */
  .empty-state {
    padding: 60px;
    text-align: center;
    color: #9ca3af;
  }

  .empty-icon {
    font-size: 36px;
    display: block;
    margin-bottom: 12px;
  }
</style>

<script>
  /** @type {string[]} */
  export let availableTags = [];

  /** @type {string} */
  export let selectedTag = '';

  import { createEventDispatcher } from 'svelte';
  const dispatch = createEventDispatcher();

  function onChange(e) {
    dispatch('change', e.target.value);
  }
</script>

{#if availableTags.length > 0}
  <div class="filter-group">
    <label class="filter-label" for="tag-filter">Tag</label>
    <select
      id="tag-filter"
      class="tag-select"
      value={selectedTag}
      on:change={onChange}
    >
      <option value="">All tags</option>
      {#each availableTags as tag}
        <option value={tag}>{tag}</option>
      {/each}
    </select>
  </div>
{/if}

<style>
  .filter-group {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .filter-label {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted, #888);
  }

  .tag-select {
    padding: 0.35rem 0.6rem;
    border: 1px solid var(--border, #ddd);
    border-radius: 6px;
    background: var(--surface, #fff);
    font-size: 0.875rem;
    cursor: pointer;
  }

  .tag-select:focus {
    outline: 2px solid var(--accent, #6c5ce7);
    outline-offset: 1px;
  }
</style>

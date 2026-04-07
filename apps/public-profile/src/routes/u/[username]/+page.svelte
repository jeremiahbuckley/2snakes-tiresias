<script>
  /** @type {import('./$types').PageData} */
  export let data;

  // TODO: render badges, score summary, platform breakdown
  // data is loaded in +page.server.js via GET /users/:username/profile
</script>

<main>
  <h1>@{data?.username ?? 'forecaster'}</h1>
  <p>Profile page — badges and stats coming soon.</p>
</main>

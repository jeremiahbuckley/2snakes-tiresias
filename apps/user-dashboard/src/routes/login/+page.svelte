<script>
  import { enhance } from '$app/forms';

  /** @type {import('./$types').ActionData} */
  export let form;

  let loading = false;
</script>

<svelte:head>
  <title>Sign In — Tiresias</title>
</svelte:head>

<div class="login-page">
  <div class="login-card">
    <div class="login-header">
      <span class="logo">🔮</span>
      <h1>Tiresias</h1>
      <p class="subtitle">Sign in to your forecasting dashboard</p>
    </div>

    {#if form?.error}
      <div class="alert alert-error">{form.error}</div>
    {/if}

    <div class="dev-notice">
      <strong>Development mode</strong> — auth backend is not yet active.
      Use the bypass button below to access the dashboard with mock data.
    </div>

    <form
      method="POST"
      action="?/login"
      use:enhance={() => {
        loading = true;
        return async ({ update }) => {
          loading = false;
          await update();
        };
      }}
    >
      <div class="field">
        <label for="email">Email</label>
        <input
          id="email"
          name="email"
          type="email"
          placeholder="you@example.com"
          autocomplete="email"
          required
        />
      </div>

      <div class="field">
        <label for="password">Password</label>
        <input
          id="password"
          name="password"
          type="password"
          placeholder="••••••••"
          autocomplete="current-password"
          required
        />
      </div>

      <button type="submit" class="btn btn-primary" disabled={loading}>
        {loading ? 'Signing in…' : 'Sign in'}
      </button>
    </form>

    <div class="divider">or</div>

    <form method="POST" action="?/devBypass">
      <button type="submit" class="btn btn-secondary">
        Continue with mock data (dev)
      </button>
    </form>
  </div>
</div>

<style>
  .login-page {
    min-height: 100vh;
    background: #f4f6f9;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }

  .login-card {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 16px rgba(0, 0, 0, 0.1);
    padding: 40px;
    width: 100%;
    max-width: 400px;
  }

  .login-header {
    text-align: center;
    margin-bottom: 28px;
  }

  .logo {
    font-size: 40px;
    display: block;
    margin-bottom: 8px;
  }

  h1 {
    font-size: 24px;
    font-weight: 700;
    color: #1a1f2e;
    margin-bottom: 6px;
  }

  .subtitle {
    color: #6b7280;
    font-size: 14px;
  }

  .dev-notice {
    background: #fffbeb;
    border: 1px solid #fcd34d;
    border-radius: 8px;
    padding: 12px 14px;
    font-size: 13px;
    color: #92400e;
    margin-bottom: 20px;
    line-height: 1.5;
  }

  .alert {
    border-radius: 8px;
    padding: 12px 14px;
    font-size: 14px;
    margin-bottom: 16px;
  }

  .alert-error {
    background: #fef2f2;
    border: 1px solid #fca5a5;
    color: #991b1b;
  }

  .field {
    margin-bottom: 16px;
  }

  label {
    display: block;
    font-size: 13px;
    font-weight: 600;
    color: #374151;
    margin-bottom: 6px;
  }

  input {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    font-size: 14px;
    color: #1a1f2e;
    transition: border-color 0.15s, box-shadow 0.15s;
    outline: none;
  }

  input:focus {
    border-color: #4f8ef7;
    box-shadow: 0 0 0 3px rgba(79, 142, 247, 0.15);
  }

  .btn {
    width: 100%;
    padding: 11px 16px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    border: none;
    transition: background 0.15s, opacity 0.15s;
  }

  .btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .btn-primary {
    background: #4f8ef7;
    color: #fff;
  }

  .btn-primary:hover:not(:disabled) {
    background: #3b7de8;
  }

  .btn-secondary {
    background: #f3f4f6;
    color: #374151;
    border: 1px solid #d1d5db;
  }

  .btn-secondary:hover {
    background: #e5e7eb;
  }

  .divider {
    text-align: center;
    color: #9ca3af;
    font-size: 13px;
    margin: 16px 0;
    position: relative;
  }

  .divider::before,
  .divider::after {
    content: '';
    position: absolute;
    top: 50%;
    width: 42%;
    height: 1px;
    background: #e5e7eb;
  }

  .divider::before { left: 0; }
  .divider::after { right: 0; }
</style>

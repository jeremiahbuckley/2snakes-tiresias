<script>
  import { enhance } from '$app/forms';

  /** @type {import('./$types').ActionData} */
  export let form;

  let loading = false;
  let password = '';
  let password_confirm = '';

  // Live mismatch indicator — only shown once the user has typed in
  // the confirmation field, to avoid yelling at them mid-typing.
  $: passwordsMismatch = password_confirm.length > 0 && password !== password_confirm;
</script>

<svelte:head>
  <title>Create an account — Tiresias</title>
</svelte:head>

<div class="register-page">
  <div class="register-card">
    <div class="register-header">
      <span class="logo">🔮</span>
      <h1>Tiresias</h1>
      <p class="subtitle">Create your forecasting account</p>
    </div>

    {#if form?.error}
      <div class="alert alert-error">{form.error}</div>
    {/if}

    <form
      method="POST"
      use:enhance={({ cancel }) => {
        // Client-side guard: match check here saves a round-trip. The
        // server still checks independently — don't rely on this alone.
        if (password !== password_confirm) {
          cancel();
          return;
        }
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
          value={form?.email ?? ''}
          required
        />
      </div>

      <div class="field">
        <label for="username">Username</label>
        <input
          id="username"
          name="username"
          type="text"
          placeholder="your-handle"
          autocomplete="username"
          minlength="3"
          maxlength="64"
          pattern="[a-zA-Z0-9_\-]+"
          title="Letters, numbers, underscore, dash. 3–64 characters."
          value={form?.username ?? ''}
          required
        />
        <p class="hint">3–64 characters. Letters, numbers, underscore, dash.</p>
      </div>

      <div class="field">
        <label for="display_name">Display name <span class="optional">(optional)</span></label>
        <input
          id="display_name"
          name="display_name"
          type="text"
          placeholder="How your name appears on your profile"
          autocomplete="name"
          maxlength="128"
          value={form?.display_name ?? ''}
        />
      </div>

      <div class="field">
        <label for="password">Password</label>
        <input
          id="password"
          name="password"
          type="password"
          placeholder="••••••••"
          autocomplete="new-password"
          minlength="8"
          bind:value={password}
          required
        />
        <p class="hint">At least 8 characters.</p>
      </div>

      <div class="field">
        <label for="password_confirm">Confirm password</label>
        <input
          id="password_confirm"
          name="password_confirm"
          type="password"
          placeholder="••••••••"
          autocomplete="new-password"
          minlength="8"
          aria-invalid={passwordsMismatch}
          aria-describedby="password_confirm_hint"
          bind:value={password_confirm}
          required
        />
        {#if passwordsMismatch}
          <p id="password_confirm_hint" class="hint hint-error">Passwords don't match.</p>
        {:else}
          <p id="password_confirm_hint" class="hint">Retype your password to confirm.</p>
        {/if}
      </div>

      <button
        type="submit"
        class="btn btn-primary"
        disabled={loading || passwordsMismatch}
      >
        {loading ? 'Creating account…' : 'Create account'}
      </button>
    </form>

    <p class="signin-link">
      Already have an account? <a href="/login">Sign in</a>
    </p>
  </div>
</div>

<style>
  .register-page {
    min-height: 100vh;
    background: #f4f6f9;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }

  .register-card {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 16px rgba(0, 0, 0, 0.1);
    padding: 40px;
    width: 100%;
    max-width: 400px;
  }

  .register-header {
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

  .optional {
    font-weight: 400;
    color: #9ca3af;
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

  .hint {
    color: #6b7280;
    font-size: 12px;
    margin-top: 6px;
  }

  .hint-error {
    color: #991b1b;
  }

  input[aria-invalid='true'] {
    border-color: #fca5a5;
  }

  input[aria-invalid='true']:focus {
    border-color: #dc2626;
    box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.15);
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

  .signin-link {
    text-align: center;
    color: #6b7280;
    font-size: 13px;
    margin-top: 20px;
  }

  .signin-link a {
    color: #4f8ef7;
    font-weight: 600;
    text-decoration: none;
  }

  .signin-link a:hover {
    text-decoration: underline;
  }
</style>

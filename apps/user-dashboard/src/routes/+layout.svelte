<script>
  import { page } from '$app/stores';

  const navItems = [
    { href: '/dashboard', label: 'Dashboard', icon: '⬛' },
    { href: '/predictions', label: 'Predictions', icon: '📋' },
    { href: '/stats', label: 'Stats', icon: '📈' },
    { href: '/settings', label: 'Settings', icon: '⚙️' },
  ];

  $: currentPath = $page.url.pathname;

  function isActive(href) {
    return currentPath === href || currentPath.startsWith(href + '/');
  }
</script>

<div class="app">
  <!-- Sidebar -->
  <nav class="sidebar">
    <div class="brand">
      <span class="brand-icon">🔮</span>
      <span class="brand-name">Tiresias</span>
    </div>

    <ul class="nav-list">
      {#each navItems as item}
        <li>
          <a
            href={item.href}
            class="nav-link"
            class:active={isActive(item.href)}
          >
            <span class="nav-icon">{item.icon}</span>
            <span class="nav-label">{item.label}</span>
          </a>
        </li>
      {/each}
    </ul>

    <div class="sidebar-footer">
      <form method="POST" action="/login?/logout">
        <button type="submit" class="sign-out-btn">Sign out</button>
      </form>
    </div>
  </nav>

  <!-- Main content -->
  <main class="main">
    <slot />
  </main>
</div>

<style>
  :global(*, *::before, *::after) {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  :global(body) {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f4f6f9;
    color: #1a1f2e;
  }

  :global(h1, h2, h3, h4) {
    font-weight: 600;
    line-height: 1.3;
  }

  :global(a) {
    color: inherit;
    text-decoration: none;
  }

  .app {
    display: flex;
    min-height: 100vh;
  }

  /* ---- Sidebar ---- */
  .sidebar {
    width: 220px;
    flex-shrink: 0;
    background: #1a1f2e;
    color: #c8cdd8;
    display: flex;
    flex-direction: column;
    position: fixed;
    top: 0;
    left: 0;
    height: 100vh;
    z-index: 100;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 24px 20px 20px;
    border-bottom: 1px solid #2d3347;
  }

  .brand-icon {
    font-size: 22px;
  }

  .brand-name {
    font-size: 18px;
    font-weight: 700;
    color: #fff;
    letter-spacing: 0.02em;
  }

  .nav-list {
    list-style: none;
    padding: 12px 0;
    flex: 1;
  }

  .nav-link {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 20px;
    border-radius: 0;
    font-size: 14px;
    font-weight: 500;
    color: #8b92a5;
    transition: background 0.15s, color 0.15s;
  }

  .nav-link:hover {
    background: #252b3d;
    color: #e0e4ef;
  }

  .nav-link.active {
    background: #252b3d;
    color: #fff;
    border-left: 3px solid #4f8ef7;
  }

  .nav-icon {
    font-size: 16px;
    width: 20px;
    text-align: center;
    /* Use a neutral square for the dashboard icon */
    filter: grayscale(1);
  }

  .nav-link.active .nav-icon {
    filter: none;
  }

  .sidebar-footer {
    padding: 16px 20px;
    border-top: 1px solid #2d3347;
  }

  .sign-out-btn {
    background: none;
    border: 1px solid #3a4054;
    color: #8b92a5;
    padding: 7px 14px;
    border-radius: 6px;
    font-size: 13px;
    cursor: pointer;
    width: 100%;
    transition: background 0.15s, color 0.15s;
  }

  .sign-out-btn:hover {
    background: #2d3347;
    color: #e0e4ef;
  }

  /* ---- Main content ---- */
  .main {
    margin-left: 220px;
    flex: 1;
    padding: 32px 40px;
    min-height: 100vh;
  }

  @media (max-width: 768px) {
    .sidebar {
      width: 60px;
    }

    .brand-name,
    .nav-label {
      display: none;
    }

    .main {
      margin-left: 60px;
      padding: 24px 20px;
    }
  }
</style>

import { Outlet } from '@tanstack/react-router';

import { IS_TAURI } from '@/bridge/cli';

/**
 * Root layout component.
 *
 * Renders the top bar and main content outlet for all routes.
 */
export function RootLayout() {
  return (
    <div className="shell">
      {/* Top bar */}
      <div className="topbar">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <circle cx="9" cy="9" r="8" stroke="#7c3aed" strokeWidth="1.2" />
          <circle cx="9" cy="9" r="4" fill="#7c3aed" opacity=".4" />
          <circle cx="9" cy="9" r="1.5" fill="#7c3aed" />
        </svg>
        <span className="topbar-title">SQLfy - Schema Graph Engine</span>
        <span className="topbar-sub">Flyway → AST → Vector Context</span>
        {/* Show mode badge so it's obvious which runtime is active */}
        <span className="mode-badge" data-mode={IS_TAURI ? 'tauri' : 'browser'}>
          {IS_TAURI ? '⚡ CLI' : '🌐 Browser'}
        </span>
      </div>

      {/* Main content outlet */}
      <Outlet />
    </div>
  );
}

export default RootLayout;

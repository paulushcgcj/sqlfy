import { useSyncExternalStore } from 'react';

function getQuery() {
  return typeof window !== 'undefined' && 'matchMedia' in window
    ? window.matchMedia('(prefers-color-scheme: dark)')
    : null;
}

function subscribe(callback: () => void) {
  const q = getQuery();
  if (!q) return () => {};
  q.addEventListener('change', callback);
  return () => q.removeEventListener('change', callback);
}

function getSnapshot() {
  const q = getQuery();
  return q ? q.matches : false;
}

function getServerSnapshot() {
  return false;
}

/**
 * Returns true when the OS/browser prefers dark color scheme.
 * Subscribes to media query changes — re-renders the component whenever
 * the user switches OS appearance.
 */
export function usePrefersDark(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

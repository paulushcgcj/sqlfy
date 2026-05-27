import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { usePrefersDark } from './usePrefersDark';

describe('usePrefersDark', () => {
  let changeCallback: ((e: { matches: boolean }) => void) | null = null;
  let mockMatches = false;

  beforeEach(() => {
    changeCallback = null;
    mockMatches = false;
    vi.stubGlobal('matchMedia', (query: string) => ({
      matches: mockMatches,
      media: query,
      addEventListener: (_: string, cb: (e: { matches: boolean }) => void) => {
        changeCallback = cb;
      },
      removeEventListener: vi.fn(),
    }));
  });

  it('returns false in light mode', () => {
    const { result } = renderHook(() => usePrefersDark());
    expect(result.current).toBe(false);
  });

  it('returns true when dark mode is active', () => {
    mockMatches = true;
    const { result } = renderHook(() => usePrefersDark());
    expect(result.current).toBe(true);
  });

  it('updates when media query fires', () => {
    const { result } = renderHook(() => usePrefersDark());
    mockMatches = true;
    act(() => {
      changeCallback?.({ matches: true });
    });
    expect(result.current).toBe(true);
  });
});

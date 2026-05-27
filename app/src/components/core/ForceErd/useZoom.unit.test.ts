import { describe, it, expect } from 'vitest';
import { setupZoom } from './useZoom';

describe('useZoom:setupZoom', () => {
  it('returns a cleanup function and tolerates null inputs', () => {
    const cleanup = setupZoom(null as any, null as any, { current: null } as any);
    expect(typeof cleanup).toBe('function');
    expect(() => cleanup()).not.toThrow();
  });
});

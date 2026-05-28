import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

import { useSimulationControls } from './useSimulationControls';

describe('useSimulationControls', () => {
  it('returns fitView and reheat functions and tolerates null refs', () => {
    const { result } = renderHook(() =>
      useSimulationControls({
        svgRef: { current: null },
        zoomRef: { current: null },
        simRef: { current: null },
        height: 300,
      }),
    );

    expect(typeof result.current.fitView).toBe('function');
    expect(typeof result.current.reheat).toBe('function');

    act(() => {
      result.current.fitView();
      result.current.reheat();
    });
  });

  it('calls simRef.alpha and restart on reheat', () => {
    const restart = vi.fn();
    const alpha = vi.fn().mockReturnValue({ restart });
    const simRef: { current: { alpha(n: number): { restart(): unknown } } | null } = {
      current: { alpha },
    };

    const { result } = renderHook(() =>
      useSimulationControls({
        svgRef: { current: null },
        zoomRef: { current: null },
        simRef,
        height: 400,
      }),
    );

    act(() => {
      result.current.reheat();
    });

    expect(alpha).toHaveBeenCalledWith(0.4);
    expect(restart).toHaveBeenCalled();
  });
});

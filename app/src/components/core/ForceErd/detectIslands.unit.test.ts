import { describe, it, expect } from 'vitest';
import { getComponents } from './detectIslands';

describe('detectIslands:getComponents', () => {
  it('groups connected nodes into a single component', () => {
    const nodes = [{ id: 'A' }, { id: 'B' }, { id: 'C' }];
    const edges = [
      { fromTable: 'A', toTable: 'B' },
      { fromTable: 'B', toTable: 'C' },
    ];

    const comps = getComponents(nodes as any, edges as any);
    // All nodes should be in one component
    expect(comps.length).toBe(1);
    expect(comps[0].sort()).toEqual(['A', 'B', 'C']);
  });

  it('returns separate components for disconnected nodes', () => {
    const nodes = [{ id: 'A' }, { id: 'B' }, { id: 'C' }];
    const edges = [{ fromTable: 'A', toTable: 'B' }];

    const comps = getComponents(nodes as any, edges as any);
    // One component should include A and B, one component should be C alone
    expect(comps.length).toBe(2);
    expect(comps.some((c) => c.includes('C'))).toBe(true);
    expect(comps.some((c) => c.includes('A') && c.includes('B'))).toBe(true);
  });
});

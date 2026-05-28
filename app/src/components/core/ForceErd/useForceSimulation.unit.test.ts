import * as d3 from 'd3';
import { describe, it, expect } from 'vitest';

import { createForceSimulation } from './useForceSimulation';

describe('useForceSimulation:createForceSimulation', () => {
  it('returns sim and stop without throwing', () => {
    const nodeData = [{ id: 'A', x: 0, y: 0 }];
    const linkData: d3.SimulationLinkDatum<d3.SimulationNodeDatum & { id: string }>[] = [];
    const nodeSel = d3.create('g').selectAll('g');
    const linkSel = d3.create('g').selectAll('path');
    const islandPaths = d3.create('g').selectAll('path');
    const nodeById = new Map([['A', { x: 0, y: 0 }]]);

    const { sim, stop } = createForceSimulation({
      nodeData,
      linkData,
      nodeSel,
      linkSel,
      islandPaths,
      nodeById,
      width: 800,
      height: 400,
      pal: {},
    });

    expect(sim).toBeDefined();
    expect(typeof stop).toBe('function');
    expect(() => stop()).not.toThrow();
  });
});

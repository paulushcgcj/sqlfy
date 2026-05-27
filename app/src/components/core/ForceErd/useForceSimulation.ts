import * as d3 from 'd3';

const NODE_W = 140;
const NODE_H = 52;
const R = 8;

export function createForceSimulation(options: {
  nodeData: any[];
  linkData: any[];
  nodeSel: any;
  linkSel: any;
  islandPaths: any;
  nodeById: Map<string, any>;
  width: number;
  height: number;
  pal: any;
}) {
  const { nodeData, linkData, nodeSel, linkSel, islandPaths, nodeById, width, height, pal } = options;

  const sim = d3
    .forceSimulation(nodeData)
    .force(
      'link',
      d3
        .forceLink(linkData)
        .id((d: any) => d.id)
        .distance(220)
        .strength(0.4),
    )
    .force('charge', d3.forceManyBody().strength(-600))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide(NODE_W * 0.72))
    .force('x', d3.forceX(width / 2).strength(0.04))
    .force('y', d3.forceY(height / 2).strength(0.04));

  sim.on('tick', () => {
    linkSel.attr('d', (l: any) => {
      const s = l.source as any;
      const t = l.target as any;
      const sx = (s.x ?? 0) + NODE_W / 2;
      const sy = (s.y ?? 0) + NODE_H;
      const tx = (t.x ?? 0) + NODE_W / 2;
      const ty = t.y ?? 0;
      const dx = tx - sx;
      const dy = ty - sy;
      const len = Math.sqrt(dx * dx + dy * dy) || 1;
      const ex = tx - (dx / len) * (R + 2);
      const ey = ty - (dy / len) * (R + 2);
      const mx = (sx + ex) / 2 - dy * 0.15;
      const my = (sy + ey) / 2 + dx * 0.15;
      return `M ${sx} ${sy} Q ${mx} ${my} ${ex} ${ey}`;
    });

    nodeSel.attr(
      'transform',
      (d: any) => `translate(${(d.x ?? 0) - NODE_W / 2}, ${(d.y ?? 0) - NODE_H / 2})`,
    );

    islandPaths.attr('d', (comp: string[]) => {
      const pts = comp
        .map((id) => nodeById.get(id))
        .filter((n: any): n is any => !!n)
        .flatMap((n: any) => [
          [(n.x ?? 0) - NODE_W * 0.7, (n.y ?? 0) - NODE_H * 0.7],
          [(n.x ?? 0) + NODE_W * 0.7, (n.y ?? 0) - NODE_H * 0.7],
          [(n.x ?? 0) - NODE_W * 0.7, (n.y ?? 0) + NODE_H * 0.7],
          [(n.x ?? 0) + NODE_W * 0.7, (n.y ?? 0) + NODE_H * 0.7],
        ]) as [number, number][];
      const hull = d3.polygonHull(pts as any);
      if (!hull) return '';
      const line = d3.line().curve(d3.curveCatmullRomClosed);
      return line(hull) ?? '';
    });
  });

  return {
    sim,
    stop: () => sim.stop(),
  };
}

import * as d3 from 'd3';
import { useCallback, useEffect, useRef } from 'react';
import { type FC } from 'react';

import type { SchemaGraph } from '@/core/types';

import './index.scss';

// ─── Layout constants ──────────────────────────────────────────────────────

const NODE_W = 140;
const NODE_H = 52;
const R = 8; // border-radius
const CHARGE = -600; // repulsion strength
const LINK_D = 220; // target edge length
const ALPHA = 0.3; // simulation re-heat on drag

// ─── Colour helpers ────────────────────────────────────────────────────────

function palette(isDark: boolean) {
  return {
    nodeFill: isDark ? '#1e2235' : '#f8f7ff',
    nodeStroke: isDark ? '#2d3748' : '#d1d5db',
    nodeSelFill: isDark ? '#3c2f6b' : '#ede9fe',
    nodeSelStroke: '#7c3aed',
    nodeDimFill: isDark ? '#161b2e' : '#f3f4f6',
    nodeDimStroke: isDark ? '#1e2235' : '#e5e7eb',
    orphanFill: isDark ? '#1a1f30' : '#fafafa',
    orphanStroke: isDark ? '#2d3748' : '#e5e7eb',
    labelColor: isDark ? '#e2e8f0' : '#111827',
    labelSel: '#7c3aed',
    labelDim: isDark ? '#4b5563' : '#9ca3af',
    subColor: isDark ? '#64748b' : '#9ca3af',
    edgeColor: '#d97706',
    edgeDim: isDark ? '#2d3748' : '#e5e7eb',
    arrowColor: '#d97706',
    arrowDim: isDark ? '#2d3748' : '#e5e7eb',
    bgColor: isDark ? '#0f172a' : '#f3f4f6',
    islandColor: isDark ? 'rgba(124,58,237,0.04)' : 'rgba(124,58,237,0.03)',
  };
}

// ─── Graph data types ──────────────────────────────────────────────────────

interface NodeDatum extends d3.SimulationNodeDatum {
  id: string;
  name: string;
  schema: string | null;
  colCount: number;
  isOrphan: boolean;
}

interface LinkDatum extends d3.SimulationLinkDatum<NodeDatum> {
  constraintName: string | null;
  onDelete: string | null;
  edgeId: string;
}

// ─── Props ─────────────────────────────────────────────────────────────────

/** Props for the {@link ForceErd} component. */
export interface ForceErdProps {
  /** The parsed schema graph. */
  readonly graph: SchemaGraph;
  /** The key of the currently selected table, or `null`. */
  readonly selectedTable: string | null;
  /** Callback invoked when the user selects a table node. */
  readonly onSelectTable: (key: string) => void;
  /** Canvas height in pixels. Defaults to `360`. */
  readonly height?: number;
}

// ─────────────────────────────────────────────
// COMPONENT
// ─────────────────────────────────────────────

/**
 * Interactive force-directed ERD using D3.
 *
 * Features
 * ─────────
 *  • Force simulation — tables repel each other, FK edges act as springs
 *  • Drag — nodes draggable, simulation re-heats on drag
 *  • Zoom & pan — mouse wheel zoom, drag-to-pan on the canvas background
 *  • Hover — hovering a node highlights its direct FK neighbours and dims others
 *  • Click — clicking a node selects it (calls `onSelectTable`)
 *  • Orphan styling — tables with no FK edges rendered with dashed border + muted colour
 *  • Island detection — disconnected clusters get a subtle background tint
 *  • Edge labels — FK constraint name shown on edge hover
 *  • Dark-mode aware — reads `prefers-color-scheme` media query
 *  • Fit & Reheat controls — toolbar buttons to reset the viewport or restart the simulation
 *
 * @component
 * @example
 * ```tsx
 * <ForceErd graph={graph} selectedTable={selected} onSelectTable={setSelected} height={340} />
 * ```
 * @param props - {@link ForceErdProps}
 * @returns An SVG canvas with a D3 force simulation and interactive controls.
 */
const ForceErd: FC<ForceErdProps> = ({ graph, selectedTable, onSelectTable, height = 360 }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const simRef = useRef<d3.Simulation<NodeDatum, LinkDatum> | null>(null);
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const isDark = globalThis.matchMedia('(prefers-color-scheme: dark)').matches;
  const pal = palette(isDark);

  // ── Build graph data ──────────────────────────────────────────────

  const { tables, edges } = graph;

  const connectedIds = new Set<string>();
  edges.forEach((e) => {
    connectedIds.add(e.fromTable);
    connectedIds.add(e.toTable);
  });

  const nodeData: NodeDatum[] = [...tables.entries()].map(([id, t]) => ({
    id,
    name: t.name,
    schema: t.schema,
    colCount: t.columns.length,
    isOrphan: !connectedIds.has(id),
  }));

  const nodeById = new Map(nodeData.map((n) => [n.id, n]));

  const linkData: LinkDatum[] = edges.map((e) => ({
    source: nodeById.get(e.fromTable) ?? e.fromTable,
    target: nodeById.get(e.toTable) ?? e.toTable,
    constraintName: e.constraintName,
    onDelete: e.onDelete,
    edgeId: e.id,
  }));

  // ── Main D3 effect ────────────────────────────────────────────────

  useEffect(() => {
    const svg = d3.select(svgRef.current!);
    svg.selectAll('*').remove();

    const width = svgRef.current!.clientWidth || 800;

    // ── Arrow markers (normal + dimmed) ──────────────────────────────
    const defs = svg.append('defs');
    function addMarker(id: string, color: string) {
      defs
        .append('marker')
        .attr('id', id)
        .attr('markerWidth', 8)
        .attr('markerHeight', 8)
        .attr('refX', 6)
        .attr('refY', 3)
        .attr('orient', 'auto')
        .append('polygon')
        .attr('points', '0 0, 6 3, 0 6')
        .attr('fill', color);
    }
    addMarker('arrow', pal.arrowColor);
    addMarker('arrow-dim', pal.arrowDim);

    // ── Root group (zoom target) ──────────────────────────────────────
    const root = svg.append('g').attr('class', 'root');

    // ── Zoom & pan ────────────────────────────────────────────────────
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 3])
      .on('zoom', (event) => root.attr('transform', event.transform));
    svg.call(zoom);
    svg.on('dblclick.zoom', null);
    zoomRef.current = zoom;

    // ── Island background blobs (convex hull per component) ───────────
    const adjList = new Map<string, Set<string>>();
    nodeData.forEach((n) => adjList.set(n.id, new Set()));
    edges.forEach((e) => {
      adjList.get(e.fromTable)?.add(e.toTable);
      adjList.get(e.toTable)?.add(e.fromTable);
    });

    function getComponents(): string[][] {
      const visited = new Set<string>();
      const comps: string[][] = [];
      for (const n of nodeData) {
        if (visited.has(n.id)) continue;
        const comp: string[] = [];
        const stack = [n.id];
        while (stack.length) {
          const cur = stack.pop()!;
          if (visited.has(cur)) continue;
          visited.add(cur);
          comp.push(cur);
          adjList.get(cur)?.forEach((nb) => {
            if (!visited.has(nb)) stack.push(nb);
          });
        }
        comps.push(comp);
      }
      return comps;
    }

    const components = getComponents();
    const islandGroup = root.append('g').attr('class', 'islands');
    const islandPaths = islandGroup
      .selectAll<SVGPathElement, string[]>('path')
      .data(components.filter((c) => c.length !== 1))
      .join('path')
      .attr('fill', pal.islandColor)
      .attr('stroke', 'none');

    // ── Edges ─────────────────────────────────────────────────────────
    const edgeGroup = root.append('g').attr('class', 'edges');
    const linkSel = edgeGroup
      .selectAll<SVGPathElement, LinkDatum>('path')
      .data(linkData)
      .join('path')
      .attr('fill', 'none')
      .attr('stroke', pal.edgeColor)
      .attr('stroke-width', 1.4)
      .attr('opacity', 0.7)
      .attr('marker-end', 'url(#arrow)')
      .attr('class', 'edge');

    // Edge hover tooltip
    const tooltip = d3
      .select(document.body)
      .append('div')
      .style('position', 'fixed')
      .style('pointer-events', 'none')
      .style('background', isDark ? '#1e2235' : '#fff')
      .style('border', `1px solid ${isDark ? '#374151' : '#e5e7eb'}`)
      .style('border-radius', '6px')
      .style('padding', '5px 10px')
      .style('font-size', '11px')
      .style('color', isDark ? '#e2e8f0' : '#111827')
      .style('box-shadow', '0 2px 8px rgba(0,0,0,.15)')
      .style('opacity', 0)
      .style('z-index', 9999);

    linkSel
      .on('mouseover', (_event, d) => {
        const label = d.constraintName
          ? `${d.constraintName}${d.onDelete ? ` · ON DELETE ${d.onDelete}` : ''}`
          : d.onDelete
            ? `ON DELETE ${d.onDelete}`
            : 'FK';
        tooltip.style('opacity', 1).text(label);
      })
      .on('mousemove', (event) => {
        tooltip.style('left', `${event.clientX + 12}px`).style('top', `${event.clientY - 8}px`);
      })
      .on('mouseleave', () => tooltip.style('opacity', 0));

    // ── Nodes ─────────────────────────────────────────────────────────
    const nodeGroup = root.append('g').attr('class', 'nodes');
    const nodeSel = nodeGroup
      .selectAll<SVGGElement, NodeDatum>('g')
      .data(nodeData)
      .join('g')
      .attr('class', 'node')
      .attr('cursor', 'pointer')
      .style('user-select', 'none');

    nodeSel
      .append('rect')
      .attr('width', NODE_W)
      .attr('height', NODE_H)
      .attr('rx', R)
      .attr('ry', R)
      .attr('fill', (d) => (d.isOrphan ? pal.orphanFill : pal.nodeFill))
      .attr('stroke', (d) => (d.isOrphan ? pal.orphanStroke : pal.nodeStroke))
      .attr('stroke-width', 1)
      .attr('stroke-dasharray', (d) => (d.isOrphan ? '4 3' : 'none'));

    nodeSel
      .append('text')
      .attr('x', NODE_W / 2)
      .attr('y', 22)
      .attr('text-anchor', 'middle')
      .attr('font-size', 12)
      .attr('font-weight', 600)
      .attr('fill', pal.labelColor)
      .attr('class', 'node-label')
      .text((d) => d.name);

    nodeSel
      .append('text')
      .attr('x', NODE_W / 2)
      .attr('y', 38)
      .attr('text-anchor', 'middle')
      .attr('font-size', 10)
      .attr('fill', pal.subColor)
      .text((d) => `${d.colCount} cols${d.schema ? ` · ${d.schema}` : ''}`);

    nodeSel
      .filter((d) => d.isOrphan)
      .append('text')
      .attr('x', NODE_W - 8)
      .attr('y', 14)
      .attr('text-anchor', 'end')
      .attr('font-size', 9)
      .attr('fill', pal.subColor)
      .text('orphan');

    // ── Interaction ───────────────────────────────────────────────────

    function highlightNeighbours(hoveredId: string | null) {
      if (!hoveredId) {
        nodeSel
          .select('rect')
          .attr('fill', (d) => (d.isOrphan ? pal.orphanFill : pal.nodeFill))
          .attr('stroke', (d) => (d.isOrphan ? pal.orphanStroke : pal.nodeStroke))
          .attr('stroke-width', 1);
        nodeSel.select('.node-label').attr('fill', pal.labelColor);
        linkSel
          .attr('stroke', pal.edgeColor)
          .attr('opacity', 0.7)
          .attr('marker-end', 'url(#arrow)');
        return;
      }

      const neighbours = new Set<string>([hoveredId]);
      linkData.forEach((l) => {
        const src = (l.source as NodeDatum).id;
        const tgt = (l.target as NodeDatum).id;
        if (src === hoveredId) neighbours.add(tgt);
        if (tgt === hoveredId) neighbours.add(src);
      });

      nodeSel
        .select('rect')
        .attr('fill', (d) => {
          if (d.id === hoveredId) return pal.nodeSelFill;
          if (neighbours.has(d.id)) return d.isOrphan ? pal.orphanFill : pal.nodeFill;
          return pal.nodeDimFill;
        })
        .attr('stroke', (d) => {
          if (d.id === hoveredId) return pal.nodeSelStroke;
          if (neighbours.has(d.id)) return d.isOrphan ? pal.orphanStroke : pal.nodeStroke;
          return pal.nodeDimStroke;
        })
        .attr('stroke-width', (d) => (d.id === hoveredId ? 2 : 1));

      nodeSel.select('.node-label').attr('fill', (d) => {
        if (d.id === hoveredId) return pal.labelSel;
        return neighbours.has(d.id) ? pal.labelColor : pal.labelDim;
      });

      linkSel
        .attr('stroke', (l) => {
          const src = (l.source as NodeDatum).id;
          const tgt = (l.target as NodeDatum).id;
          return src === hoveredId || tgt === hoveredId ? pal.edgeColor : pal.edgeDim;
        })
        .attr('opacity', (l) => {
          const src = (l.source as NodeDatum).id;
          const tgt = (l.target as NodeDatum).id;
          return src === hoveredId || tgt === hoveredId ? 1 : 0.15;
        })
        .attr('marker-end', (l) => {
          const src = (l.source as NodeDatum).id;
          const tgt = (l.target as NodeDatum).id;
          return src === hoveredId || tgt === hoveredId ? 'url(#arrow)' : 'url(#arrow-dim)';
        });
    }

    nodeSel
      .on('mouseover', (_, d) => highlightNeighbours(d.id))
      .on('mouseleave', () => highlightNeighbours(null))
      .on('click', (event, d) => {
        event.stopPropagation();
        onSelectTable(d.id);
      });

    svg.on('click', () => highlightNeighbours(null));

    // ── Drag ──────────────────────────────────────────────────────────
    const drag = d3
      .drag<SVGGElement, NodeDatum>()
      .on('start', (ev: d3.D3DragEvent<SVGGElement, NodeDatum, NodeDatum>, d) => {
        if (!ev.active) simRef.current?.alphaTarget(ALPHA).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on('drag', (ev: d3.D3DragEvent<SVGGElement, NodeDatum, NodeDatum>, d) => {
        d.fx = ev.x;
        d.fy = ev.y;
      })
      .on('end', (ev: d3.D3DragEvent<SVGGElement, NodeDatum, NodeDatum>, _d) => {
        if (!ev.active) simRef.current?.alphaTarget(0);
      });

    nodeSel.call(drag);

    // ── Force simulation ──────────────────────────────────────────────
    const sim = d3
      .forceSimulation<NodeDatum>(nodeData)
      .force(
        'link',
        d3
          .forceLink<NodeDatum, LinkDatum>(linkData)
          .id((d) => d.id)
          .distance(LINK_D)
          .strength(0.4),
      )
      .force('charge', d3.forceManyBody().strength(CHARGE))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide(NODE_W * 0.72))
      .force('x', d3.forceX(width / 2).strength(0.04))
      .force('y', d3.forceY(height / 2).strength(0.04));

    simRef.current = sim;

    // ── Tick ──────────────────────────────────────────────────────────
    sim.on('tick', () => {
      linkSel.attr('d', (l) => {
        const s = l.source as NodeDatum;
        const t = l.target as NodeDatum;
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
        (d) => `translate(${(d.x ?? 0) - NODE_W / 2}, ${(d.y ?? 0) - NODE_H / 2})`,
      );

      islandPaths.attr('d', (comp) => {
        const pts = comp
          .map((id) => nodeById.get(id))
          .filter((n): n is NodeDatum => !!n)
          .flatMap((n) => [
            [(n.x ?? 0) - NODE_W * 0.7, (n.y ?? 0) - NODE_H * 0.7],
            [(n.x ?? 0) + NODE_W * 0.7, (n.y ?? 0) - NODE_H * 0.7],
            [(n.x ?? 0) - NODE_W * 0.7, (n.y ?? 0) + NODE_H * 0.7],
            [(n.x ?? 0) + NODE_W * 0.7, (n.y ?? 0) + NODE_H * 0.7],
          ]) as [number, number][];
        const hull = d3.polygonHull(pts);
        if (!hull) return '';
        const line = d3.line().curve(d3.curveCatmullRomClosed);
        return line(hull) ?? '';
      });
    });

    return () => {
      sim.stop();
      tooltip.remove();
    };
    // Full rebuild only when the graph changes. selectedTable + onSelectTable are
    // handled by the sync effect below and direct closure respectively.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph]);

  // ── Sync selected node highlight ─────────────────────────────────────
  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    const p = palette(isDark);
    svg.selectAll<SVGGElement, NodeDatum>('.node').each(function (d) {
      const isSel = d.id === selectedTable;
      d3.select(this)
        .select('rect')
        .attr('fill', isSel ? p.nodeSelFill : d.isOrphan ? p.orphanFill : p.nodeFill)
        .attr('stroke', isSel ? p.nodeSelStroke : d.isOrphan ? p.orphanStroke : p.nodeStroke)
        .attr('stroke-width', isSel ? 2 : 1);
      d3.select(this)
        .select('.node-label')
        .attr('fill', isSel ? p.labelSel : p.labelColor);
    });
  }, [selectedTable, isDark]);

  // ── Fit-to-view ───────────────────────────────────────────────────────
  const fitView = useCallback(() => {
    const svg = d3.select(svgRef.current!);
    const root = svg.select<SVGGElement>('.root');
    const bbox = (root.node() as SVGGElement).getBBox();
    if (!bbox.width || !bbox.height) return;
    const W = svgRef.current!.clientWidth;
    const scale = 0.85 * Math.min(W / bbox.width, height / bbox.height);
    const tx = W / 2 - scale * (bbox.x + bbox.width / 2);
    const ty = height / 2 - scale * (bbox.y + bbox.height / 2);
    zoomRef.current?.transform(
      d3.select(svgRef.current!).transition().duration(500),
      d3.zoomIdentity.translate(tx, ty).scale(scale),
    );
  }, [height]);

  const reheat = useCallback(() => {
    simRef.current?.alpha(0.4).restart();
  }, []);

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        background: palette(isDark).bgColor,
      }}
    >
      {/* Controls */}
      <div
        style={{
          position: 'absolute',
          top: 8,
          right: 8,
          zIndex: 10,
          display: 'flex',
          gap: 4,
        }}
      >
        <button
          onClick={reheat}
          title="Re-run simulation"
          style={{
            padding: '3px 9px',
            fontSize: 11,
            cursor: 'pointer',
            background: isDark ? '#1e2235' : '#fff',
            border: `1px solid ${isDark ? '#374151' : '#d1d5db'}`,
            borderRadius: 5,
            color: isDark ? '#9ca3af' : '#6b7280',
          }}
        >
          ⟲ Reheat
        </button>
        <button
          onClick={fitView}
          title="Fit all nodes in view"
          style={{
            padding: '3px 9px',
            fontSize: 11,
            cursor: 'pointer',
            background: isDark ? '#1e2235' : '#fff',
            border: `1px solid ${isDark ? '#374151' : '#d1d5db'}`,
            borderRadius: 5,
            color: isDark ? '#9ca3af' : '#6b7280',
          }}
        >
          ⊡ Fit
        </button>
      </div>

      {/* Legend */}
      <div
        style={{
          position: 'absolute',
          bottom: 8,
          left: 8,
          zIndex: 10,
          display: 'flex',
          gap: 10,
          fontSize: 10,
          color: isDark ? '#6b7280' : '#9ca3af',
        }}
      >
        <span>── FK edge</span>
        <span
          style={{
            borderBottom: '1.5px dashed currentColor',
            paddingBottom: 1,
          }}
        >
          ╌ orphan
        </span>
        <span>hover to highlight · drag to move · scroll to zoom</span>
      </div>

      <svg ref={svgRef} width="100%" height={height} style={{ display: 'block' }} />
    </div>
  );
};

export default ForceErd;

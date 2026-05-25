import { useMemo } from 'react';
import { computeLayout } from '../core/core';
import type { SchemaGraph } from '../core/types';

const BW = 130, BH = 48, SVW = 580, SVH = 240;

interface Props {
  graph: SchemaGraph;
  selectedTable: string | null;
  onSelectTable: (key: string) => void;
}

export function ErdCanvas({ graph, selectedTable, onSelectTable }: Props) {
  const { tables, edges } = graph;
  const pos = useMemo(() => computeLayout(tables, edges), [tables, edges]);
  const isDark = window.matchMedia('(prefers-color-scheme:dark)').matches;

  return (
    <div className="erd-wrap">
      <svg viewBox={`0 0 ${SVW} ${SVH}`} style={{ display: 'block', width: '100%', height: '240px' }}>
        <defs>
          <marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <polygon points="0 0, 6 3, 0 6" fill="#d97706" />
          </marker>
        </defs>

        {/* Edges */}
        {edges.map(e => {
          const fp = pos.get(e.fromTable), tp = pos.get(e.toTable);
          if (!fp || !tp) return null;
          const [x1, y1, x2, y2] = [fp.x, fp.y + BH / 2, tp.x, tp.y - BH / 2];
          const mid = (y1 + y2) / 2;
          return (
            <path
              key={e.id}
              d={`M ${x1} ${y1} C ${x1} ${mid} ${x2} ${mid} ${x2} ${y2}`}
              stroke="#d97706" strokeWidth="1.2" fill="none"
              opacity="0.6" markerEnd="url(#arr)"
            />
          );
        })}

        {/* Nodes */}
        {[...tables.entries()].map(([key, t]) => {
          const p = pos.get(key);
          if (!p) return null;
          const isSel = key === selectedTable;
          return (
            <g key={key} style={{ cursor: 'pointer' }} onClick={() => onSelectTable(key)}>
              <rect
                x={p.x - BW / 2} y={p.y - BH / 2}
                width={BW} height={BH} rx="5"
                fill={isSel ? (isDark ? '#3c2f6b' : '#ede9fe') : (isDark ? '#1e2235' : '#f8f7ff')}
                stroke={isSel ? '#7c3aed' : (isDark ? '#2d3748' : '#d1d5db')}
                strokeWidth={isSel ? 1.8 : 0.8}
              />
              <text
                x={p.x} y={p.y - 4} textAnchor="middle"
                fontSize="11" fontWeight="500"
                fill={isSel ? '#7c3aed' : (isDark ? '#e2e8f0' : '#111827')}
              >
                {t.name}
              </text>
              <text
                x={p.x} y={p.y + 11} textAnchor="middle"
                fontSize="9"
                fill={isDark ? '#64748b' : '#9ca3af'}
              >
                {t.columns.length} cols · V{t.createdIn}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
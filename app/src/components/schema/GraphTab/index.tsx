import type { SchemaGraph } from '@/core/types';
import type { FC } from 'react';

import ForceErd from '@/components/core/ForceErd';
import TableDetail from '@/components/core/TableDetail';

/** Props for the {@link GraphTab} component. */
export interface GraphTabProps {
  /** The parsed schema graph. */
  readonly graph: SchemaGraph;
  /** The key of the currently selected table, or `null`. */
  readonly selectedTable: string | null;
  /** Callback invoked when the user selects a table. */
  readonly onSelectTable: (key: string) => void;
}

/**
 * Schema graph tab combining a sidebar table/sequence list with an ERD canvas and detail panel.
 *
 * @component
 * @example
 * ```tsx
 * <GraphTab graph={graph} selectedTable={selected} onSelectTable={setSelected} />
 * ```
 * @param props - {@link GraphTabProps}
 * @returns A split-panel layout with a sidebar and an ERD canvas + detail panel.
 */
const GraphTab: FC<GraphTabProps> = ({ graph, selectedTable, onSelectTable }) => {
  const { tables, seqs, edges } = graph;

  return (
    <div className="split">
      {/* Sidebar */}
      <div className="sidebar">
        <div className="sbar-sect">Tables ({tables.size})</div>
        {[...tables.entries()].map(([key, t]) => {
          const out = edges.filter((e) => e.fromTable === key).length;
          const inn = edges.filter((e) => e.toTable === key).length;
          return (
            <button
              key={key}
              className={`sbar-item${key === selectedTable ? ' active' : ''}`}
              onClick={() => onSelectTable(key)}
            >
              {t.name}
              <div className="sub">
                {t.columns.length} cols · {out + inn} rels · V{t.createdIn}
              </div>
            </button>
          );
        })}

        {seqs.size > 0 && (
          <>
            <div className="sbar-sect">Sequences ({seqs.size})</div>
            {[...seqs.values()].map((s) => (
              <div key={s.full} className="sbar-item" style={{ cursor: 'default' }}>
                {s.name}
                <div className="sub">
                  START {s.startWith} INC {s.incrementBy}
                </div>
              </div>
            ))}
          </>
        )}
      </div>

      {/* Main */}
      <div className="main">
        <div style={{ borderBottom: '0.5px solid var(--border-sub)' }}>
          <ForceErd
            graph={graph}
            selectedTable={selectedTable}
            onSelectTable={onSelectTable}
            height={340}
          />
        </div>
        {selectedTable ? (
          <TableDetail tableKey={selectedTable} graph={graph} />
        ) : (
          <div className="no-data">Select a table to view details</div>
        )}
      </div>
    </div>
  );
};

export default GraphTab;

import { ErdCanvas } from './ErdCanvas';
import { TableDetail } from './TableDetail';
import type { SchemaGraph } from '../core/types';

interface Props {
  graph: SchemaGraph;
  selectedTable: string | null;
  onSelectTable: (key: string) => void;
}

export function GraphTab({ graph, selectedTable, onSelectTable }: Props) {
  const { tables, seqs, edges } = graph;

  return (
    <div className="split">
      {/* Sidebar */}
      <div className="sidebar">
        <div className="sbar-sect">Tables ({tables.size})</div>
        {[...tables.entries()].map(([key, t]) => {
          const out = edges.filter(e => e.fromTable === key).length;
          const inn = edges.filter(e => e.toTable   === key).length;
          return (
            <button
              key={key}
              className={`sbar-item${key === selectedTable ? ' active' : ''}`}
              onClick={() => onSelectTable(key)}
            >
              {t.name}
              <div className="sub">{t.columns.length} cols · {out + inn} rels · V{t.createdIn}</div>
            </button>
          );
        })}

        {seqs.size > 0 && (
          <>
            <div className="sbar-sect">Sequences ({seqs.size})</div>
            {[...seqs.values()].map(s => (
              <div key={s.full} className="sbar-item" style={{ cursor: 'default' }}>
                {s.name}
                <div className="sub">START {s.startWith} INC {s.incrementBy}</div>
              </div>
            ))}
          </>
        )}
      </div>

      {/* Main */}
      <div className="main">
        <ErdCanvas graph={graph} selectedTable={selectedTable} onSelectTable={onSelectTable} />
        {selectedTable
          ? <TableDetail tableKey={selectedTable} graph={graph} />
          : <div className="no-data">Select a table to view details</div>
        }
      </div>
    </div>
  );
}
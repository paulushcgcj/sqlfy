import type { FC } from 'react';
import { typeStr } from '@/core/core';
import type { SchemaGraph } from '@/core/types';
import './index.scss';

/** Props for the {@link TableDetail} component. */
export interface TableDetailProps {
  /** The fully-qualified table key (e.g. `"APP.USERS"`). */
  readonly tableKey: string;
  /** The parsed schema graph containing tables and edges. */
  readonly graph: SchemaGraph;
}

/**
 * Detailed view for a single database table.
 *
 * Renders column definitions (type, flags, defaults, comments), FK relationships
 * (outbound and inbound), indexes, and check constraints.
 *
 * @component
 * @example
 * ```tsx
 * <TableDetail tableKey="APP.USERS" graph={graph} />
 * ```
 * @param props - {@link TableDetailProps}
 * @returns A structured detail panel for the selected table, or a fallback prompt.
 */
const TableDetail: FC<TableDetailProps> = ({ tableKey, graph }) => {
  const { tables, edges } = graph;
  const t = tables.get(tableKey);
  if (!t) return <div className="no-data">Select a table to view details</div>;

  const pk   = t.constraints.find(c => c.type === 'primary_key');
  const uqs  = t.constraints.filter(c => c.type === 'unique');
  const cks  = t.constraints.filter(c => c.type === 'check');
  const outE = edges.filter(e => e.fromTable === tableKey);
  const inE  = edges.filter(e => e.toTable   === tableKey);

  return (
    <div>
      {/* Header */}
      <div className="tbl-hdr">
        <div className="tbl-name">{t.full}</div>
        <div className="tbl-meta">
          V{t.createdIn}
          {t.modifiedIn.length > 0 && ` · modified V${t.modifiedIn.join(', ')}`}
          {' '}· {t.columns.length} columns
          {t.indexes.length > 0 && ` · ${t.indexes.length} indexes`}
        </div>
        {t.comments['__table__'] && (
          <div className="tbl-comment">{t.comments['__table__']}</div>
        )}
      </div>

      {/* Columns */}
      <div className="sect">
        <div className="sect-title">Columns</div>
        <div className="col-row col-head">
          <span>Column</span><span>Type</span><span>Flags</span><span>Default</span><span>Comment</span>
        </div>
        {t.columns.map(col => (
          <div className="col-row" key={col.name}>
            <span className="col-name">{col.name}</span>
            <span className="col-type">{typeStr(col)}</span>
            <span>
              {pk?.columns.includes(col.name)               && <span className="badge pk">PK</span>}
              {!col.nullable                                 && <span className="badge nn">NN</span>}
              {uqs.some(u => u.columns.includes(col.name))  && <span className="badge uq">UQ</span>}
              {outE.some(e => e.fromCols.includes(col.name)) && <span className="badge fk">FK</span>}
            </span>
            <span className="col-def">{col.default ?? '—'}</span>
            <span className="col-comment">{t.comments[col.name] ?? ''}</span>
          </div>
        ))}
      </div>

      {/* Relationships */}
      {(outE.length > 0 || inE.length > 0) && (
        <div className="sect">
          <div className="sect-title">Relationships</div>
          <div className="rel-grid">
            {outE.length > 0 && (
              <div>
                <div className="rel-dir-label">REFERENCES ▶</div>
                {outE.map(e => (
                  <div className="rel-card" key={e.id}>
                    <div className="rl">{e.fromCols.join(',')} → {e.toTable}</div>
                    <div className="rm2">
                      {e.constraintName}
                      {e.onDelete && ` · ON DELETE ${e.onDelete}`}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {inE.length > 0 && (
              <div>
                <div className="rel-dir-label">◀ REFERENCED BY</div>
                {inE.map(e => (
                  <div className="rel-card in" key={e.id}>
                    <div className="rl">{e.fromTable}</div>
                    <div className="rm2">{e.fromCols.join(',')} → {e.toCols.join(',')}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Indexes */}
      {t.indexes.length > 0 && (
        <div className="sect">
          <div className="sect-title">Indexes</div>
          {t.indexes.map(idx => (
            <div className="idx-row" key={idx.name}>
              <span className="idx-name">{idx.name}</span>
              <span className="idx-cols">({idx.columns.join(', ')})</span>
              {idx.unique && <span className="badge uq">UNIQUE</span>}
              <span className="idx-ver" style={{ marginLeft: 'auto' }}>V{idx.createdIn}</span>
            </div>
          ))}
        </div>
      )}

      {/* Check Constraints */}
      {cks.length > 0 && (
        <div className="sect">
          <div className="sect-title">Check Constraints</div>
          {cks.map((ck, i) => (
            <div className="ck-row" key={i}>
              <span className="ck-name">{ck.name ?? 'unnamed'}: </span>
              <span className="ck-expr">CHECK ({ck.checkExpr})</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default TableDetail;

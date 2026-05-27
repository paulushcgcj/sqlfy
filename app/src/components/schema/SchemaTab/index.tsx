/**
 * Schema CLI panel — surfaces every CLI command available in `sqlfy`:
 *
 *  • Dump   — full Schema State Dictionary (JSON)
 *  • Graph  — Mermaid ERD / Graphviz DOT / ASCII summary
 *  • Insights — automated schema analysis (orphan tables, missing PKs, etc.)
 *
 * When the Python CLI is available (Tauri or Vite dev server), each panel
 * calls the real CLI for maximum fidelity.  In pure-browser mode, lightweight
 * TypeScript implementations provide equivalent output.
 */

import DumpPanel from './DumpPanel';

import type { MigrationFile, SchemaGraph } from '@/core/types';
import type { FC } from 'react';
import './index.scss';

// ─── Types ────────────────────────────────────────────────────────────────────

type SubTab = 'dump';
/** Props for the {@link SchemaTab} component. */
export interface SchemaTabProps {
  /** Parsed schema graph (used for client-side fallbacks). */
  readonly graph: SchemaGraph;
  /** Raw migration files (used to call the CLI). */
  readonly files: MigrationFile[];
}

const SchemaTab: FC<SchemaTabProps> = ({ graph, files }) => {
  return (
    <div className="schema-tab">
      <DumpPanel files={files} graph={graph} />
    </div>
  );
};

export default SchemaTab;

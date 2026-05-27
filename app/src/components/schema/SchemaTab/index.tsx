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

import { useState, useCallback } from 'react';

import type { DumpFormat, DumpOptions } from '@/bridge/cli';
import type { MigrationFile, SchemaGraph, Edge } from '@/core/types';
import type { FC } from 'react';

import {
  IS_TAURI,
  dumpWithOptions,
  graphMermaid,
  graphDot,
  graphSummary,
  insights as cliInsights,
} from '@/bridge/cli';
import './index.scss';

// ─── Types ────────────────────────────────────────────────────────────────────

type SubTab = 'dump' | 'graph' | 'insights';
type GraphFormat = 'mermaid' | 'dot' | 'summary';

/** Severity levels for client-side insights. */
type Severity = 'error' | 'warning' | 'info';

interface Finding {
  severity: Severity;
  rule: string;
  message: string;
  target?: string;
}

/** Props for the {@link SchemaTab} component. */
export interface SchemaTabProps {
  /** Parsed schema graph (used for client-side fallbacks). */
  readonly graph: SchemaGraph;
  /** Raw migration files (used to call the CLI). */
  readonly files: MigrationFile[];
}

// ─── Client-side fallbacks ────────────────────────────────────────────────────

/** Generate a JSON dump of the schema state from the parsed graph. */
function browserDump(graph: SchemaGraph): string {
  const state = {
    version: graph.migHist.at(-1)?.version ?? '?',
    migration_history: graph.migHist,
    tables: Object.fromEntries(
      [...graph.tables.entries()].map(([key, t]) => [
        key,
        {
          name: t.name,
          schema: t.schema,
          full: t.full,
          created_in: t.createdIn,
          modified_in: t.modifiedIn,
          columns: t.columns.map((c) => ({
            name: c.name,
            type: c.type,
            nullable: c.nullable,
            default: c.default,
            primary_key: c.primaryKey,
            unique: c.unique,
            references: c.references ?? null,
          })),
          constraints: t.constraints,
          indexes: t.indexes,
        },
      ]),
    ),
    sequences: Object.fromEntries(
      [...graph.seqs.entries()].map(([key, s]) => [
        key,
        {
          name: s.name,
          full: s.full,
          start_with: s.startWith,
          increment_by: s.incrementBy,
          created_in: s.createdIn,
        },
      ]),
    ),
    edges: graph.edges.map((e) => ({
      id: e.id,
      from_table: e.fromTable,
      from_cols: e.fromCols,
      to_table: e.toTable,
      to_cols: e.toCols,
      constraint_name: e.constraintName,
      on_delete: e.onDelete,
    })),
  };
  return JSON.stringify(state, null, 2);
}

/** Generate a YAML dump of the schema state from the parsed graph. */
function browserDumpYaml(graph: SchemaGraph): string {
  const lines: string[] = [];
  const version = graph.migHist.at(-1)?.version ?? '?';

  lines.push(`version: "${version}"`, '');

  lines.push('migration_history:');
  for (const m of graph.migHist) {
    const desc = m.description;
    lines.push(`  - version: "${m.version}"`, `    description: "${desc}"`);
  }
  lines.push('');

  lines.push('tables:');
  for (const [key, t] of graph.tables) {
    const modifiedInList = t.modifiedIn.map((v) => `"${v}"`).join(', ');
    lines.push(
      `  ${key}:`,
      `    name: "${t.name}"`,
      `    schema: ${t.schema ?? 'null'}`,
      `    full: "${t.full}"`,
      `    created_in: "${t.createdIn}"`,
      `    modified_in: [${modifiedInList}]`,
      `    columns:`,
    );
    for (const c of t.columns) {
      const refStr = c.references
        ? `{ table: "${c.references.table}", column: "${c.references.column}" }`
        : 'null';
      lines.push(
        `      - name: "${c.name}"`,
        `        type: "${c.type}"`,
        `        nullable: ${c.nullable}`,
        `        default: ${c.default ?? 'null'}`,
        `        primary_key: ${c.primaryKey}`,
        `        unique: ${c.unique}`,
        `        references: ${refStr}`,
      );
    }
  }
  lines.push('');

  lines.push('sequences:');
  for (const [key, s] of graph.seqs) {
    lines.push(
      `  ${key}:`,
      `    name: "${s.name}"`,
      `    full: "${s.full}"`,
      `    start_with: ${s.startWith}`,
      `    increment_by: ${s.incrementBy}`,
      `    created_in: "${s.createdIn}"`,
    );
  }
  lines.push('');

  lines.push('edges:');
  for (const e of graph.edges) {
    const fromColsList = e.fromCols.map((c) => `"${c}"`).join(', ');
    const toColsList = e.toCols.map((c) => `"${c}"`).join(', ');
    const constraintStr = e.constraintName ? `"${e.constraintName}"` : 'null';
    const onDeleteStr = e.onDelete ? `"${e.onDelete}"` : 'null';
    lines.push(
      `  - id: "${e.id}"`,
      `    from_table: "${e.fromTable}"`,
      `    from_cols: [${fromColsList}]`,
      `    to_table: "${e.toTable}"`,
      `    to_cols: [${toColsList}]`,
      `    constraint_name: ${constraintStr}`,
      `    on_delete: ${onDeleteStr}`,
    );
  }

  return lines.join('\n');
}

/** Generate a summary dump of the schema state from the parsed graph. */
function browserDumpSummary(graph: SchemaGraph): string {
  const lines: string[] = [];
  const version = graph.migHist.at(-1)?.version ?? '?';

  lines.push(`Schema State Summary — Version ${version}`, '='.repeat(60), '');

  lines.push(`Migration History: ${graph.migHist.length} migrations`);
  for (const m of graph.migHist) {
    lines.push(`  V${m.version}: ${m.description}`);
  }
  lines.push('');

  lines.push(`Tables: ${graph.tables.size}`);
  for (const [, t] of graph.tables) {
    const pkCount = t.columns.filter((c) => c.primaryKey).length;
    const fkCount = t.columns.filter((c) => c.references !== null).length;
    const idxCount = t.indexes.length;
    lines.push(
      `  ${t.full}: ${t.columns.length} cols, ${pkCount} PK, ${fkCount} FK, ${idxCount} idx (V${t.createdIn})`,
    );
  }
  lines.push('');

  lines.push(`Sequences: ${graph.seqs.size}`);
  for (const [, s] of graph.seqs) {
    lines.push(`  ${s.full}: START ${s.startWith} INC ${s.incrementBy} (V${s.createdIn})`);
  }
  lines.push('');

  lines.push(`Foreign Key Relationships: ${graph.edges.length}`);
  for (const e of graph.edges) {
    const fromTable = graph.tables.get(e.fromTable)?.full ?? e.fromTable;
    const toTable = graph.tables.get(e.toTable)?.full ?? e.toTable;
    const constraint = e.constraintName ?? 'unnamed';
    lines.push(`  ${fromTable} → ${toTable} (${constraint})`);
  }

  return lines.join('\n');
}

/** Generate a Mermaid ERD diagram from the parsed graph. */
function browserMermaid(graph: SchemaGraph): string {
  const lines: string[] = ['erDiagram'];

  for (const [, t] of graph.tables) {
    lines.push(`  ${sanitiseName(t.name)} {`);
    for (const col of t.columns) {
      const flags: string[] = [];
      if (col.primaryKey) flags.push('PK');
      if (col.references !== null) flags.push('FK');
      if (col.unique && !col.primaryKey) flags.push('UK');
      const suffix = flags.length ? ` "${flags.join(', ')}"` : '';
      const rawType = col.type.split('(')[0].replace(/\s+/g, '_');
      lines.push(`    ${rawType} ${sanitiseName(col.name)}${suffix}`);
    }
    lines.push('  }');
  }

  const seen = new Set<string>();
  for (const e of graph.edges) {
    const from = graph.tables.get(e.fromTable)?.name ?? e.fromTable;
    const to = graph.tables.get(e.toTable)?.name ?? e.toTable;
    const key = `${from}→${to}`;
    if (seen.has(key)) continue;
    seen.add(key);
    lines.push(`  ${sanitiseName(from)} }o--|| ${sanitiseName(to)} : "FK"`);
  }

  return lines.join('\n');
}

/** Generate a Graphviz DOT diagram. */
function browserDot(graph: SchemaGraph): string {
  const lines: string[] = [
    'digraph schema {',
    '  rankdir=LR;',
    '  node [shape=record, fontname="Helvetica", fontsize=10];',
    '  edge [fontsize=9];',
  ];

  for (const [key, t] of graph.tables) {
    const cols = t.columns
      .map((c) => {
        const pk = c.primaryKey ? ' [PK]' : '';
        const fk = c.references ? ' [FK]' : '';
        return `${c.name}: ${c.type}${pk}${fk}`;
      })
      .join('\\l');
    const label = `{${t.full}|${cols}\\l}`;
    lines.push(`  "${key}" [label="${label.replace(/"/g, '\\"')}"];`);
  }

  for (const e of graph.edges) {
    const label = e.constraintName ?? '';
    lines.push(`  "${e.fromTable}" -> "${e.toTable}" [label="${label}"];`);
  }

  lines.push('}');
  return lines.join('\n');
}

/** Generate an ASCII summary. */
function browserSummary(graph: SchemaGraph): string {
  const lines: string[] = [];
  lines.push(`Schema V${graph.migHist.at(-1)?.version ?? '?'}`);
  lines.push(
    `Tables: ${graph.tables.size}  Sequences: ${graph.seqs.size}  Edges: ${graph.edges.length}`,
  );
  lines.push('');

  for (const [key, t] of graph.tables) {
    const out = graph.edges.filter((e: Edge) => e.fromTable === key).length;
    const inn = graph.edges.filter((e: Edge) => e.toTable === key).length;
    lines.push(
      `  ${t.full}  (${t.columns.length} cols, ${out + inn} rels, created V${t.createdIn})`,
    );
  }

  if (graph.seqs.size > 0) {
    lines.push('');
    lines.push('Sequences:');
    for (const s of graph.seqs.values()) {
      lines.push(`  ${s.full}  START ${s.startWith} INC ${s.incrementBy}`);
    }
  }

  return lines.join('\n');
}

/** Analyse the schema graph and return findings. */
function browserInsights(graph: SchemaGraph): Finding[] {
  const findings: Finding[] = [];

  for (const [key, t] of graph.tables) {
    // Missing primary key
    const hasPk =
      t.constraints.some((c) => c.type === 'primary_key') || t.columns.some((c) => c.primaryKey);
    if (!hasPk) {
      findings.push({
        severity: 'error',
        rule: 'missing-pk',
        message: 'No primary key defined',
        target: t.full,
      });
    }

    // Orphan table (no FK in or out)
    if (graph.tables.size > 1) {
      const hasEdge = graph.edges.some((e) => e.fromTable === key || e.toTable === key);
      if (!hasEdge) {
        findings.push({
          severity: 'warning',
          rule: 'orphan-table',
          message: 'No foreign key relationships',
          target: t.full,
        });
      }
    }

    // Wide table
    if (t.columns.length > 15) {
      findings.push({
        severity: 'info',
        rule: 'wide-table',
        message: `${t.columns.length} columns — consider normalising`,
        target: t.full,
      });
    }

    // Potential unresolved FK columns (_id suffix, not actually FK)
    for (const col of t.columns) {
      if (col.name.endsWith('_id') && !col.primaryKey && col.references === null) {
        const declaredFk = t.constraints.some(
          (c) => c.type === 'foreign_key' && c.columns.includes(col.name),
        );
        if (!declaredFk) {
          findings.push({
            severity: 'info',
            rule: 'potential-fk',
            message: 'Column looks like a FK but has no FK constraint',
            target: `${t.full}.${col.name}`,
          });
        }
      }
    }
  }

  // Nullable PK columns
  for (const [, t] of graph.tables) {
    for (const col of t.columns) {
      if (col.primaryKey && col.nullable) {
        findings.push({
          severity: 'error',
          rule: 'nullable-pk',
          message: 'Primary key column is nullable',
          target: `${t.full}.${col.name}`,
        });
      }
    }
  }

  // Duplicate indexes
  for (const [, t] of graph.tables) {
    const seen = new Map<string, string>();
    for (const idx of t.indexes) {
      const sig = idx.columns.slice().sort().join(',');
      if (seen.has(sig)) {
        findings.push({
          severity: 'warning',
          rule: 'duplicate-index',
          message: `Duplicate index on (${idx.columns.join(', ')}) — same as ${seen.get(sig)}`,
          target: `${t.full}.${idx.name}`,
        });
      } else {
        seen.set(sig, idx.name);
      }
    }
  }

  return findings;
}

/** Parse CLI insights JSON output into Finding[]. */
function parseCliInsights(raw: string): Finding[] {
  try {
    const data = JSON.parse(raw) as {
      findings?: Array<{ severity: string; rule: string; message: string; target?: string }>;
    };
    return (data.findings ?? []).map((f) => ({
      severity: (f.severity as Severity) ?? 'info',
      rule: f.rule ?? '',
      message: f.message ?? '',
      target: f.target,
    }));
  } catch {
    return [];
  }
}

function sanitiseName(name: string): string {
  return name.replace(/[^a-zA-Z0-9_]/g, '_');
}

function download(content: string, filename: string, mime = 'text/plain') {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ─── Component ────────────────────────────────────────────────────────────────

const isCli = IS_TAURI || import.meta.env.DEV;

/**
 * Schema CLI panel exposing all CLI functionalities in the UI.
 *
 * @component
 * @param props - {@link SchemaTabProps}
 */
const SchemaTab: FC<SchemaTabProps> = ({ graph, files }) => {
  const [activeSubTab, setActiveSubTab] = useState<SubTab>('dump');

  // ── Dump state ──
  const [dumpOutput, setDumpOutput] = useState<string | null>(null);
  const [dumpLoading, setDumpLoading] = useState(false);
  const [dumpError, setDumpError] = useState<string | null>(null);
  const [dumpCopied, setDumpCopied] = useState(false);
  const [dumpFormat, setDumpFormat] = useState<DumpFormat>('json');
  const [dumpAtVersion, setDumpAtVersion] = useState<number | undefined>(undefined);

  // ── Graph state ──
  const [graphOutput, setGraphOutput] = useState<string | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphError, setGraphError] = useState<string | null>(null);
  const [graphCopied, setGraphCopied] = useState(false);
  const [graphFormat, setGraphFormat] = useState<GraphFormat>('mermaid');

  // ── Insights state ──
  const [insightsFindings, setInsightsFindings] = useState<Finding[] | null>(null);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [insightsError, setInsightsError] = useState<string | null>(null);

  // ── Handlers ──

  const handleDump = useCallback(async () => {
    setDumpLoading(true);
    setDumpError(null);
    try {
      let out: string;
      if (isCli) {
        const options: DumpOptions = { format: dumpFormat };
        if (dumpAtVersion !== undefined) {
          options.atVersion = dumpAtVersion;
        }
        out = await dumpWithOptions(files, options);
      } else {
        // Browser fallback
        if (dumpFormat === 'json') out = browserDump(graph);
        else if (dumpFormat === 'yaml') out = browserDumpYaml(graph);
        else out = browserDumpSummary(graph);
      }
      setDumpOutput(out);
    } catch (err) {
      setDumpError((err as Error).message);
      // Fall back to browser implementation
      if (dumpFormat === 'json') setDumpOutput(browserDump(graph));
      else if (dumpFormat === 'yaml') setDumpOutput(browserDumpYaml(graph));
      else setDumpOutput(browserDumpSummary(graph));
    } finally {
      setDumpLoading(false);
    }
  }, [files, graph, dumpFormat, dumpAtVersion]);

  const handleGraph = useCallback(async () => {
    setGraphLoading(true);
    setGraphError(null);
    try {
      let out: string;
      if (isCli) {
        if (graphFormat === 'mermaid') out = await graphMermaid(files);
        else if (graphFormat === 'dot') out = await graphDot(files);
        else out = await graphSummary(files);
      } else {
        if (graphFormat === 'mermaid') out = browserMermaid(graph);
        else if (graphFormat === 'dot') out = browserDot(graph);
        else out = browserSummary(graph);
      }
      setGraphOutput(out);
    } catch (err) {
      setGraphError((err as Error).message);
      // Fall back to browser implementation
      if (graphFormat === 'mermaid') setGraphOutput(browserMermaid(graph));
      else if (graphFormat === 'dot') setGraphOutput(browserDot(graph));
      else setGraphOutput(browserSummary(graph));
    } finally {
      setGraphLoading(false);
    }
  }, [files, graph, graphFormat]);

  const handleInsights = useCallback(async () => {
    setInsightsLoading(true);
    setInsightsError(null);
    try {
      if (isCli) {
        const raw = await cliInsights(files);
        setInsightsFindings(parseCliInsights(raw));
      } else {
        setInsightsFindings(browserInsights(graph));
      }
    } catch (err) {
      setInsightsError((err as Error).message);
      setInsightsFindings(browserInsights(graph));
    } finally {
      setInsightsLoading(false);
    }
  }, [files, graph]);

  function copyText(text: string, setCopied: (v: boolean) => void) {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }

  // ── Render helpers ──

  function renderDump() {
    const extMap: Record<DumpFormat, string> = { json: 'json', yaml: 'yaml', summary: 'txt' };
    const mimeMap: Record<DumpFormat, string> = {
      json: 'application/json',
      yaml: 'application/x-yaml',
      summary: 'text/plain',
    };

    return (
      <div className="schema-panel">
        <div className="schema-panel-actions">
          <select
            className="schema-fmt-select"
            value={dumpFormat}
            onChange={(e) => {
              setDumpFormat(e.target.value as DumpFormat);
              setDumpOutput(null);
            }}
          >
            <option value="json">JSON</option>
            <option value="yaml">YAML</option>
            <option value="summary">Summary</option>
          </select>
          <select
            className="schema-version-select"
            value={dumpAtVersion ?? ''}
            onChange={(e) => {
              const val = e.target.value;
              setDumpAtVersion(val === '' ? undefined : parseInt(val, 10));
              setDumpOutput(null);
            }}
            title="Export state at specific migration version"
          >
            <option value="">Current state</option>
            {graph.migHist.map((m) => (
              <option key={m.version} value={m.version}>
                V{m.version}: {m.description}
              </option>
            ))}
          </select>
          <button className="schema-run-btn" onClick={handleDump} disabled={dumpLoading}>
            {dumpLoading ? '⏳ Running…' : '▶ Run dump'}
          </button>
          <button
            className={`schema-copy-btn${dumpCopied ? ' copied' : ''}`}
            onClick={() => dumpOutput && copyText(dumpOutput, setDumpCopied)}
            disabled={!dumpOutput}
          >
            {dumpCopied ? '✓ Copied' : '⎘ Copy'}
          </button>
          <button
            className="schema-dl-btn"
            onClick={() =>
              dumpOutput &&
              download(dumpOutput, `schema_state.${extMap[dumpFormat]}`, mimeMap[dumpFormat])
            }
            disabled={!dumpOutput}
          >
            ⬇ Download
          </button>
          <span className="schema-hint">{isCli ? '⚡ CLI' : '🌐 Browser fallback'}</span>
        </div>

        {dumpError && (
          <div className="schema-error">⚠ CLI error (showing browser fallback): {dumpError}</div>
        )}

        {dumpLoading && <div className="schema-loading">Running sqlfy dump…</div>}

        {dumpOutput && !dumpLoading && (
          <div className="schema-output">
            <pre>{dumpOutput}</pre>
          </div>
        )}
      </div>
    );
  }

  function renderGraph() {
    const extMap: Record<GraphFormat, string> = { mermaid: 'mmd', dot: 'dot', summary: 'txt' };

    return (
      <div className="schema-panel">
        <div className="schema-panel-actions">
          <select
            className="schema-fmt-select"
            value={graphFormat}
            onChange={(e) => {
              setGraphFormat(e.target.value as GraphFormat);
              setGraphOutput(null);
            }}
          >
            <option value="mermaid">Mermaid ERD</option>
            <option value="dot">Graphviz DOT</option>
            <option value="summary">ASCII Summary</option>
          </select>
          <button className="schema-run-btn" onClick={handleGraph} disabled={graphLoading}>
            {graphLoading ? '⏳ Running…' : '▶ Run graph'}
          </button>
          <button
            className={`schema-copy-btn${graphCopied ? ' copied' : ''}`}
            onClick={() => graphOutput && copyText(graphOutput, setGraphCopied)}
            disabled={!graphOutput}
          >
            {graphCopied ? '✓ Copied' : '⎘ Copy'}
          </button>
          <button
            className="schema-dl-btn"
            onClick={() => graphOutput && download(graphOutput, `schema.${extMap[graphFormat]}`)}
            disabled={!graphOutput}
          >
            ⬇ Download
          </button>
          <span className="schema-hint">{isCli ? '⚡ CLI' : '🌐 Browser fallback'}</span>
        </div>

        {graphError && (
          <div className="schema-error">⚠ CLI error (showing browser fallback): {graphError}</div>
        )}

        {graphLoading && <div className="schema-loading">Running sqlfy graph…</div>}

        {graphOutput && !graphLoading && (
          <div className="schema-output">
            <pre>{graphOutput}</pre>
          </div>
        )}
      </div>
    );
  }

  function renderInsights() {
    const counts = insightsFindings
      ? {
          errors: insightsFindings.filter((f) => f.severity === 'error').length,
          warnings: insightsFindings.filter((f) => f.severity === 'warning').length,
          infos: insightsFindings.filter((f) => f.severity === 'info').length,
        }
      : null;

    return (
      <div className="schema-panel">
        <div className="schema-panel-actions">
          <button className="schema-run-btn" onClick={handleInsights} disabled={insightsLoading}>
            {insightsLoading ? '⏳ Running…' : '▶ Run insights'}
          </button>
          {counts && (
            <>
              {counts.errors > 0 && (
                <span className="insight-sev" data-sev="error">
                  {counts.errors} errors
                </span>
              )}
              {counts.warnings > 0 && (
                <span className="insight-sev" data-sev="warning">
                  {counts.warnings} warnings
                </span>
              )}
              {counts.infos > 0 && (
                <span className="insight-sev" data-sev="info">
                  {counts.infos} info
                </span>
              )}
            </>
          )}
          <span className="schema-hint">{isCli ? '⚡ CLI' : '🌐 Browser fallback'}</span>
        </div>

        {insightsError && (
          <div className="schema-error">
            ⚠ CLI error (showing browser fallback): {insightsError}
          </div>
        )}

        {insightsLoading && <div className="schema-loading">Running sqlfy insights…</div>}

        {insightsFindings && !insightsLoading && (
          <>
            {insightsFindings.length === 0 ? (
              <div className="insights-empty">✓ No issues found</div>
            ) : (
              <div className="insights-list">
                {insightsFindings.map((f, i) => (
                  <div key={i} className="insight-item">
                    <span className="insight-sev" data-sev={f.severity}>
                      {f.severity}
                    </span>
                    <div className="insight-body">
                      <span className="insight-msg">{f.message}</span>
                      {f.target && <span className="insight-target">{f.target}</span>}
                      <span className="insight-target" style={{ opacity: 0.6 }}>
                        rule: {f.rule}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    );
  }

  return (
    <div className="schema-tab">
      <div className="schema-subtabs">
        <button
          className={`schema-subtab${activeSubTab === 'dump' ? ' active' : ''}`}
          onClick={() => setActiveSubTab('dump')}
        >
          State Dump
        </button>
        <button
          className={`schema-subtab${activeSubTab === 'graph' ? ' active' : ''}`}
          onClick={() => setActiveSubTab('graph')}
        >
          Graph Export
        </button>
        <button
          className={`schema-subtab${activeSubTab === 'insights' ? ' active' : ''}`}
          onClick={() => setActiveSubTab('insights')}
        >
          Insights
        </button>
      </div>

      {activeSubTab === 'dump' && renderDump()}
      {activeSubTab === 'graph' && renderGraph()}
      {activeSubTab === 'insights' && renderInsights()}
    </div>
  );
};

export default SchemaTab;

/**
 * sqlfy — src/bridge/cli.ts
 *
 * Tauri ↔ Python CLI bridge.
 *
 * When running inside Tauri:
 *   1. Serialises migrations to a temp JSON file
 *   2. Spawns the Python CLI with --json-input --all --json
 *   3. Parses the combined { graph, chunks } JSON response
 *   4. Cleans up the temp file
 *
 * When running in a plain browser (dev without Tauri):
 *   Falls back to the in-browser TypeScript core — same results,
 *   no subprocess needed.
 *
 * ─── Tauri plugin prerequisites ───────────────
 *   npm install @tauri-apps/plugin-shell @tauri-apps/plugin-fs
 *   cargo add tauri-plugin-shell tauri-plugin-fs
 */

import type { MigrationFile, SchemaGraph, VectorChunk } from '@/core/types';

import { applyMigrations, buildChunks } from '@/core/core';

// ── Tauri detection ──────────────────────────────────────────────────────────
export const IS_TAURI = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;

// ── CLI path config ──────────────────────────────────────────────────────────
//
// DEV  → PYTHONPATH=../../cli/src python3 -m sqlfy
//         Invokes the CLI as a module (supports relative imports)
// PROD → sidecar  binaries/sqlfy  (PyInstaller binary bundled in step 7)
//
// You can override DEV_CLI_PATH via the VITE_CLI_PATH env var in .env.local
const DEV_CLI_CMD = 'python3';
const DEV_CLI_ARGS = ['-m', 'sqlfy'];
const DEV_PYTHONPATH = '../../cli/src';

// ── Result type returned to the app ─────────────────────────────────────────
export interface ParseResult {
  graph: SchemaGraph;
  chunks: VectorChunk[];
  source: 'cli' | 'browser'; // for debugging
}

// ─────────────────────────────────────────────
// TAURI PATH: write temp file → spawn CLI → parse output
// ─────────────────────────────────────────────

async function parseWithTauri(files: MigrationFile[]): Promise<ParseResult> {
  // Dynamic imports — only available in Tauri context
  const { Command } = await import('@tauri-apps/plugin-shell');
  const { writeTextFile, remove } = await import('@tauri-apps/plugin-fs');
  const { tempDir, join } = await import('@tauri-apps/api/path');

  // Write migrations to a temp JSON file
  const tmp = await join(await tempDir(), `sqlfy-input-${Date.now()}.json`);
  await writeTextFile(tmp, JSON.stringify(files));

  try {
    // Spawn CLI: dev uses python3 -m sqlfy with PYTHONPATH, prod uses sidecar binary
    let command;
    if (import.meta.env.DEV) {
      // Dev: invoke CLI as module with PYTHONPATH to support relative imports
      // Use sh -c to set PYTHONPATH environment variable
      const shellCmd = `PYTHONPATH="${DEV_PYTHONPATH}" ${DEV_CLI_CMD} ${DEV_CLI_ARGS.join(' ')} --json-input "${tmp}" --all --json`;
      command = Command.create('sh', ['-c', shellCmd]);
    } else {
      // Prod: use sidecar binary (PyInstaller bundle)
      command = Command.sidecar('binaries/sqlfy', ['--json-input', tmp, '--all', '--json']);
    }

    const output = await command.execute();

    if (output.code !== 0) {
      throw new Error(`CLI exited with code ${output.code}.\n${output.stderr || '(no stderr)'}`);
    }

    if (!output.stdout.trim()) {
      throw new Error('CLI produced no output. Is python3 available and the CLI path correct?');
    }

    const result = JSON.parse(output.stdout) as { graph: unknown; chunks: unknown[] };

    // The Python CLI returns snake_case; massage into the TypeScript shape
    return {
      graph: deserialiseGraph(result.graph),
      chunks: deserialiseChunks(result.chunks),
      source: 'cli',
    };
  } finally {
    // Always clean up the temp file
    await remove(tmp).catch(() => {
      /* best-effort */
    });
  }
}

// ─────────────────────────────────────────────
// DEV-SERVER PATH: proxy through Vite middleware → Python CLI
// ─────────────────────────────────────────────

async function parseWithDevServer(files: MigrationFile[]): Promise<ParseResult> {
  const resp = await fetch('/api/sqlfy/parse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(files),
  });

  if (!resp.ok) {
    const err = (await resp.json().catch(() => ({ error: resp.statusText }))) as { error: string };
    throw new Error(`Dev-server CLI error: ${err.error}`);
  }

  const result = (await resp.json()) as { graph: unknown; chunks: unknown[] };
  return {
    graph: deserialiseGraph(result.graph),
    chunks: deserialiseChunks(result.chunks),
    source: 'cli',
  };
}

// ─────────────────────────────────────────────
// BROWSER FALLBACK: run TypeScript core in-process
// ─────────────────────────────────────────────

function parseInBrowser(files: MigrationFile[]): ParseResult {
  const graph = applyMigrations(files);
  const chunks = buildChunks(graph);
  return { graph, chunks, source: 'browser' };
}

// ─────────────────────────────────────────────
// PUBLIC API
// ─────────────────────────────────────────────

/**
 * Parse a set of Flyway migration files.
 *
 * Routing:
 *  1. Tauri desktop  → spawn Python CLI via plugin-shell
 *  2. Vite dev server → proxy to Python CLI via /api/sqlfy/parse
 *  3. Pure browser    → TypeScript in-process fallback (core.ts)
 */
export async function parse(files: MigrationFile[]): Promise<ParseResult> {
  if (IS_TAURI) return parseWithTauri(files);
  if (import.meta.env.DEV) return parseWithDevServer(files);
  return parseInBrowser(files);
}

// ─────────────────────────────────────────────
// GENERIC CLI COMMAND RUNNER
// ─────────────────────────────────────────────

export type CliSubcommand = 'dump' | 'insights' | 'graph' | 'export';

/**
 * Run an arbitrary CLI subcommand and return stdout as a string.
 *
 * Routing:
 *  1. Tauri desktop  → spawn Python CLI via plugin-shell
 *  2. Vite dev server → proxy via /api/sqlfy/run
 *  3. Pure browser    → throws (CLI not available)
 */
export async function runCliCommand(
  subcommand: CliSubcommand,
  files: MigrationFile[],
  extraArgs: string[] = [],
): Promise<string> {
  if (IS_TAURI) return runCliCommandTauri(subcommand, files, extraArgs);
  if (import.meta.env.DEV) return runCliCommandDevServer(subcommand, files, extraArgs);
  throw new Error('CLI not available in pure-browser mode');
}

async function runCliCommandTauri(
  subcommand: CliSubcommand,
  files: MigrationFile[],
  extraArgs: string[],
): Promise<string> {
  const { Command } = await import('@tauri-apps/plugin-shell');
  const { writeTextFile, remove } = await import('@tauri-apps/plugin-fs');
  const { tempDir, join } = await import('@tauri-apps/api/path');

  const tmp = await join(await tempDir(), `sqlfy-input-${Date.now()}.json`);
  await writeTextFile(tmp, JSON.stringify(files));

  try {
    let command;
    if (import.meta.env.DEV) {
      // Dev: invoke CLI as module with PYTHONPATH to support relative imports
      const args = [subcommand, '--json-input', tmp, ...extraArgs].map(arg => `"${arg}"`).join(' ');
      const shellCmd = `PYTHONPATH="${DEV_PYTHONPATH}" ${DEV_CLI_CMD} ${DEV_CLI_ARGS.join(' ')} ${args}`;
      command = Command.create('sh', ['-c', shellCmd]);
    } else {
      // Prod: use sidecar binary (PyInstaller bundle)
      command = Command.sidecar('binaries/sqlfy', [subcommand, '--json-input', tmp, ...extraArgs]);
    }

    const output = await command.execute();
    if (output.code !== 0) {
      throw new Error(`CLI exited with code ${output.code}.\n${output.stderr || '(no stderr)'}`);
    }
    return output.stdout;
  } finally {
    await remove(tmp).catch(() => {
      /* best-effort */
    });
  }
}

async function runCliCommandDevServer(
  subcommand: CliSubcommand,
  files: MigrationFile[],
  extraArgs: string[],
): Promise<string> {
  const resp = await fetch('/api/sqlfy/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ subcommand, args: extraArgs, files }),
  });

  if (!resp.ok) {
    const err = (await resp.json().catch(() => ({ error: resp.statusText }))) as { error: string };
    throw new Error(`Dev-server CLI error: ${err.error}`);
  }

  const result = (await resp.json()) as { output: string };
  return result.output;
}

// ─────────────────────────────────────────────
// NAMED COMMAND SHORTCUTS
// ─────────────────────────────────────────────

/** Output the Schema State Dictionary as JSON. */
export function dump(files: MigrationFile[]): Promise<string> {
  return runCliCommand('dump', files, ['--format', 'json']);
}

/** Run schema insights analysis, returning JSON. */
export function insights(files: MigrationFile[]): Promise<string> {
  return runCliCommand('insights', files, ['--format', 'json']);
}

/** Export the schema as a Mermaid ERD string. */
export function graphMermaid(files: MigrationFile[]): Promise<string> {
  return runCliCommand('graph', files, ['--format', 'mermaid']);
}

/** Export the schema as a Graphviz DOT string. */
export function graphDot(files: MigrationFile[]): Promise<string> {
  return runCliCommand('graph', files, ['--format', 'dot']);
}

/** Export the schema as an ASCII summary string. */
export function graphSummary(files: MigrationFile[]): Promise<string> {
  return runCliCommand('graph', files, ['--format', 'summary']);
}

// ─────────────────────────────────────────────
// DESERIALISERS  (Python snake_case → TS camelCase)
// ─────────────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function deserialiseGraph(raw: any): SchemaGraph {
  const tables = new Map<string, import('../core/types').Table>();
  const seqs = new Map<string, import('../core/types').Sequence>();

  for (const [key, t] of Object.entries(raw.tables ?? {})) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const rt = t as any;
    tables.set(key, {
      id: rt.id,
      schema: rt.schema,
      name: rt.name,
      full: rt.full,
      columns: (rt.columns ?? []).map(deserialiseColumn),
      constraints: (rt.constraints ?? []).map(deserialiseConstraint),
      indexes: (rt.indexes ?? []).map(deserialiseIndex),
      comments: rt.comments ?? {},
      createdIn: rt.created_in,
      modifiedIn: rt.modified_in ?? [],
    });
  }

  for (const [key, s] of Object.entries(raw.sequences ?? {})) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const rs = s as any;
    seqs.set(key, {
      name: rs.name,
      schema: rs.schema,
      full: rs.full,
      startWith: rs.start_with,
      incrementBy: rs.increment_by,
      createdIn: rs.created_in,
    });
  }

  const edges = (raw.edges ?? []).map(deserialiseEdge);
  const migHist = (raw.migration_history ?? []).map(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (m: any) => ({ version: m.version, description: m.description }),
  );

  return { tables, seqs, edges, migHist };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function deserialiseColumn(c: any): import('../core/types').Column {
  return {
    name: c.name,
    type: c.type,
    precision: c.precision,
    scale: c.scale,
    nullable: c.nullable,
    default: c.default,
    primaryKey: c.primary_key,
    unique: c.unique,
    references: c.references ? { table: c.references.table, column: c.references.column } : null,
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function deserialiseConstraint(c: any): import('../core/types').Constraint {
  return {
    name: c.name,
    type: c.type,
    columns: c.columns ?? [],
    references: c.references
      ? {
          table: c.references.table,
          columns: c.references.columns,
          onDelete: c.references.on_delete,
        }
      : undefined,
    checkExpr: c.check_expr,
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function deserialiseIndex(i: any): import('../core/types').Index {
  return { name: i.name, columns: i.columns, unique: i.unique, createdIn: i.created_in };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function deserialiseEdge(e: any): import('../core/types').Edge {
  return {
    id: e.id,
    fromTable: e.from_table,
    fromCols: e.from_cols,
    toTable: e.to_table,
    toCols: e.to_cols,
    constraintName: e.constraint_name,
    onDelete: e.on_delete,
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function deserialiseChunks(raw: any[]): VectorChunk[] {
  return (raw ?? []).map((c) => ({
    id: c.id,
    type: c.type,
    title: c.title,
    content: c.content,
    meta: c.metadata ?? c.meta ?? {},
    hint: c.hint,
  }));
}

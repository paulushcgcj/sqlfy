#!/usr/bin/env node
/**
 * sqlfy — cli/index.js
 *
 * CLI entry point. Reads Flyway migration files from a directory,
 * applies migrations via core.js, and outputs the result.
 *
 * Usage:
 *   node cli/index.js <migrations-dir> [--chunks] [--json]
 *
 * Examples:
 *   node cli/index.js ./migrations
 *   node cli/index.js ./migrations --chunks
 *   node cli/index.js ./migrations --chunks --json
 */

import { readdir, readFile } from 'fs/promises';
import { join, extname } from 'path';
import { applyMigrations, buildChunks, typeStr } from './core.js';

// ─── Helpers ───────────────────────────────────────────────────────────────

function usage() {
  console.error(`
Usage: node cli/index.js <migrations-dir> [options]

Options:
  --chunks    Output LLM vector chunks instead of schema graph
  --json      Output raw JSON (default: human-readable)

Examples:
  node cli/index.js ./migrations
  node cli/index.js ./migrations --chunks --json
`);
  process.exit(1);
}

function printHumanGraph(graph) {
  const { tables, seqs, edges, migHist } = graph;

  console.log('\n╔══════════════════════════════════════════╗');
  console.log('║          SCHEMA GRAPH — SUMMARY          ║');
  console.log('╚══════════════════════════════════════════╝\n');

  console.log(`Migration history:`);
  for (const m of migHist) console.log(`  V${m.version}  ${m.description}`);

  console.log(`\nTables (${tables.size}):`);
  for (const [, t] of tables) {
    const pk    = t.constraints.find(c => c.type === 'primary_key');
    const outE  = edges.filter(e => e.fromTable === t.full);
    const inE   = edges.filter(e => e.toTable   === t.full);
    console.log(`\n  ┌─ ${t.full} ──────────────────────────────`);
    if (t.comments['__table__']) console.log(`  │  ${t.comments['__table__']}`);
    console.log(`  │  Created: V${t.createdIn}${t.modifiedIn.length ? `  Modified: V${t.modifiedIn.join(', ')}` : ''}`);
    console.log(`  │  Columns:`);
    for (const col of t.columns) {
      const flags = [];
      if (pk?.columns.includes(col.name)) flags.push('PK');
      if (!col.nullable)                  flags.push('NN');
      if (col.default)                    flags.push(`DEFAULT ${col.default}`);
      const comment = t.comments[col.name];
      console.log(`  │    ${col.name.padEnd(24)} ${typeStr(col).padEnd(18)} ${flags.join(' ')}${comment ? `  -- ${comment}` : ''}`);
    }
    if (outE.length) {
      console.log(`  │  References:`);
      for (const e of outE) console.log(`  │    ${e.fromCols.join(',')} → ${e.toTable}(${e.toCols.join(',')})${e.onDelete ? ` ON DELETE ${e.onDelete}` : ''}`);
    }
    if (inE.length) {
      console.log(`  │  Referenced by:`);
      for (const e of inE) console.log(`  │    ${e.fromTable}.${e.fromCols.join(',')}`);
    }
    if (t.indexes.length) {
      console.log(`  │  Indexes:`);
      for (const idx of t.indexes) console.log(`  │    ${idx.name}  (${idx.columns.join(', ')})${idx.unique ? ' UNIQUE' : ''}`);
    }
    console.log(`  └────────────────────────────────────────`);
  }

  if (seqs.size > 0) {
    console.log(`\nSequences (${seqs.size}):`);
    for (const [, s] of seqs) {
      console.log(`  ${s.full.padEnd(30)} START ${s.startWith}  INCREMENT ${s.incrementBy}  [V${s.createdIn}]`);
    }
  }

  console.log(`\nRelationships (${edges.length}):`);
  for (const e of edges) {
    console.log(`  ${e.fromTable}.${e.fromCols.join(',')}  →  ${e.toTable}.${e.toCols.join(',')}${e.onDelete ? `  [ON DELETE ${e.onDelete}]` : ''}`);
  }
  console.log('');
}

function printHumanChunks(chunks) {
  console.log('\n╔══════════════════════════════════════════╗');
  console.log('║         LLM VECTOR CHUNKS                ║');
  console.log('╚══════════════════════════════════════════╝\n');
  for (const chunk of chunks) {
    console.log(`━━━ [${chunk.type}] ${chunk.title} ${'─'.repeat(Math.max(0, 50 - chunk.title.length))}`);
    console.log(`Hint: ${chunk.hint}`);
    console.log('');
    console.log(chunk.content);
    console.log('');
    console.log('Metadata:', JSON.stringify(chunk.meta, null, 2));
    console.log('');
  }
}

// ─── Main ──────────────────────────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2);

  const migrationsDir = args.find(a => !a.startsWith('--'));
  const wantChunks    = args.includes('--chunks');
  const wantJson      = args.includes('--json');

  if (!migrationsDir) usage();

  // Read migration files
  let entries;
  try {
    entries = await readdir(migrationsDir);
  } catch (err) {
    console.error(`Error reading directory: ${migrationsDir}\n${err.message}`);
    process.exit(1);
  }

  const sqlFiles = entries
    .filter(f => extname(f).toLowerCase() === '.sql')
    .sort();

  if (!sqlFiles.length) {
    console.error(`No .sql files found in ${migrationsDir}`);
    process.exit(1);
  }

  const files = await Promise.all(
    sqlFiles.map(async filename => ({
      filename,
      sql: await readFile(join(migrationsDir, filename), 'utf8'),
    }))
  );

  console.error(`Loaded ${files.length} migration file(s) from ${migrationsDir}`);

  // Run
  const graph = applyMigrations(files);

  if (wantChunks) {
    const chunks = buildChunks(graph);
    if (wantJson) {
      console.log(JSON.stringify(chunks.map(c => ({
        id:       c.id,
        type:     c.type,
        title:    c.title,
        content:  c.content,
        metadata: c.meta,
        hint:     c.hint,
      })), null, 2));
    } else {
      printHumanChunks(chunks);
    }
  } else {
    if (wantJson) {
      // Serialise Maps to plain objects
      const out = {
        migrationHistory: graph.migHist,
        tables: Object.fromEntries(
          [...graph.tables.entries()].map(([k, t]) => [k, t])
        ),
        sequences: Object.fromEntries(
          [...graph.seqs.entries()].map(([k, s]) => [k, s])
        ),
        edges: graph.edges,
      };
      console.log(JSON.stringify(out, null, 2));
    } else {
      printHumanGraph(graph);
    }
  }
}

main().catch(err => {
  console.error('Fatal error:', err.message);
  process.exit(1);
});
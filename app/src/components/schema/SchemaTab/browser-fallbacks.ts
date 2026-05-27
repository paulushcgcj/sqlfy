import type { SchemaGraph } from '@/core/types';

/** Generate a JSON dump of the schema state from the parsed graph. */
export function browserDump(graph: SchemaGraph): string {
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
export function browserDumpYaml(graph: SchemaGraph): string {
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
export function browserDumpSummary(graph: SchemaGraph): string {
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

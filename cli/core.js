/**
 * sqlfy — core.js
 *
 * Pure logic module: SQL parsing, Flyway orchestration,
 * schema graph construction, and LLM vector chunk building.
 *
 * No DOM, no Node.js APIs — importable in both browser (ES module)
 * and Node.js (CommonJS via the CLI wrapper).
 */

// ─────────────────────────────────────────────
// SQL TOKENISER UTILITIES
// ─────────────────────────────────────────────

/** Remove block and line comments from SQL */
export function stripComments(sql) {
  sql = sql.replace(/\/\*[\s\S]*?\*\//g, ' ');
  sql = sql.replace(/--[^\n]*/g, ' ');
  return sql;
}

/**
 * Split SQL into individual statements on `;`,
 * respecting string literals and nested parentheses.
 */
export function splitStmts(sql) {
  const r = [];
  let depth = 0, cur = '', inStr = false;
  for (let i = 0; i < sql.length; i++) {
    const c = sql[i];
    if (inStr) {
      cur += c;
      if (c === "'") {
        if (sql[i + 1] === "'") cur += sql[++i]; // escaped quote
        else inStr = false;
      }
    } else if (c === "'")          { inStr = true; cur += c; }
    else if (c === '(')            { depth++; cur += c; }
    else if (c === ')')            { depth--; cur += c; }
    else if (c === ';' && depth === 0) { const s = cur.trim(); if (s) r.push(s); cur = ''; }
    else                           { cur += c; }
  }
  const s = cur.trim(); if (s) r.push(s);
  return r;
}

/**
 * Extract the content of the outermost parentheses in a string.
 * e.g. "CREATE TABLE foo (a NUMBER, b VARCHAR2)" → "a NUMBER, b VARCHAR2"
 */
export function extractParen(str) {
  const start = str.indexOf('(');
  if (start < 0) return '';
  let d = 0;
  for (let i = start; i < str.length; i++) {
    if      (str[i] === '(') d++;
    else if (str[i] === ')') { if (--d === 0) return str.slice(start + 1, i); }
  }
  return '';
}

/**
 * Split a comma-delimited string, respecting nested parens and strings.
 */
export function splitComma(str) {
  const r = [];
  let d = 0, cur = '', inStr = false;
  for (let i = 0; i < str.length; i++) {
    const c = str[i];
    if (inStr)          { cur += c; if (c === "'") inStr = false; }
    else if (c === "'") { inStr = true; cur += c; }
    else if (c === '(') { d++; cur += c; }
    else if (c === ')') { d--; cur += c; }
    else if (c === ',' && d === 0) { const p = cur.trim(); if (p) r.push(p); cur = ''; }
    else                { cur += c; }
  }
  const p = cur.trim(); if (p) r.push(p);
  return r;
}

// ─────────────────────────────────────────────
// NAME / TYPE PARSING
// ─────────────────────────────────────────────

/**
 * Parse a potentially schema-qualified name: "APP.USERS" → { schema, name, full }
 */
export function parseName(str) {
  str = str.trim().replace(/"/g, '');
  const p = str.split('.');
  if (p.length >= 2) {
    return {
      schema: p[0].toUpperCase(),
      name:   p[1].toUpperCase(),
      full:   `${p[0].toUpperCase()}.${p[1].toUpperCase()}`,
    };
  }
  return { schema: null, name: str.toUpperCase(), full: str.toUpperCase() };
}

/**
 * Parse a data-type token into { type, precision, scale }.
 * e.g. "NUMBER(10,2)" → { type: 'NUMBER', precision: 10, scale: 2 }
 */
export function parseDataType(s) {
  const m = s.match(/^([A-Z][A-Z0-9 ]*)(?:\(([^)]+)\))?$/i);
  if (!m) return { type: s.trim().toUpperCase(), precision: null, scale: null };
  const type = m[1].trim().toUpperCase();
  if (!m[2]) return { type, precision: null, scale: null };
  const a = m[2].split(',').map(x => x.trim());
  return {
    type,
    precision: a[0] ? parseInt(a[0]) : null,
    scale:     a[1] ? parseInt(a[1]) : null,
  };
}

/** Render a column's data type back to a string, e.g. NUMBER(10,2) */
export function typeStr(col) {
  if (col.precision !== null && col.scale !== null) return `${col.type}(${col.precision},${col.scale})`;
  if (col.precision !== null)                        return `${col.type}(${col.precision})`;
  return col.type;
}

// ─────────────────────────────────────────────
// COLUMN + CONSTRAINT PARSERS
// ─────────────────────────────────────────────

/**
 * Parse a single column definition inside a CREATE TABLE body.
 * Returns null if the token looks like a constraint, not a column.
 *
 * @returns {{ name, type, precision, scale, nullable, default, primaryKey, unique, references } | null}
 */
export function parseColDef(def) {
  def = def.replace(/\s+/g, ' ').trim();
  const nm = def.match(/^"?(\w+)"?\s+/);
  if (!nm) return null;
  const name = nm[1].toUpperCase();
  let rest = def.slice(nm[0].length).trim();

  // Extract data type (may contain parens)
  let typeS = '', d = 0, i = 0;
  for (; i < rest.length; i++) {
    const c = rest[i];
    if      (c === '(') { d++; typeS += c; }
    else if (c === ')') { d--; typeS += c; }
    else if (c === ' ' && d === 0) break;
    else                typeS += c;
  }
  const { type, precision, scale } = parseDataType(typeS);
  rest = rest.slice(i).trim();

  let nullable = true, defVal = null, primaryKey = false, unique = false, references = null;

  // DEFAULT value (must come before NOT NULL in Oracle)
  const dm = rest.match(/DEFAULT\s+(.+?)(?=\s+(?:NOT\s+NULL|NULL|CONSTRAINT|PRIMARY|UNIQUE|REFERENCES|ENABLE|DISABLE)|$)/i);
  if (dm) { defVal = dm[1].trim(); rest = rest.replace(dm[0], ' ').trim(); }

  if (/NOT\s+NULL/i.test(rest))         nullable = false;
  if (/\bPRIMARY\s+KEY\b/i.test(rest))  primaryKey = true;
  if (/\bUNIQUE\b/i.test(rest))         unique = true;

  const rm = rest.match(/REFERENCES\s+"?(\w+(?:\.\w+)?)"?\s*\("?(\w+)"?\)/i);
  if (rm) {
    const rn = parseName(rm[1]);
    references = { table: rn.full, column: rm[2].toUpperCase() };
  }

  return { name, type, precision, scale, nullable, default: defVal, primaryKey, unique, references };
}

/**
 * Parse a table constraint (PRIMARY KEY, UNIQUE, FOREIGN KEY, CHECK).
 * Handles both bare constraints and CONSTRAINT <name> ... forms.
 *
 * @returns {{ name, type, columns, references?, checkExpr? } | null}
 */
export function parseConstraint(def) {
  def = def.replace(/\s+/g, ' ').trim();
  let cname = null;
  const cn = def.match(/^CONSTRAINT\s+"?(\w+)"?\s+/i);
  if (cn) { cname = cn[1].toUpperCase(); def = def.slice(cn[0].length).trim(); }

  if (/^PRIMARY\s+KEY/i.test(def)) {
    const cols = extractParen(def).split(',')
      .map(c => c.trim().replace(/"/g, '').toUpperCase()).filter(Boolean);
    return { name: cname, type: 'primary_key', columns: cols };
  }

  if (/^UNIQUE/i.test(def)) {
    const cols = extractParen(def).split(',')
      .map(c => c.trim().replace(/"/g, '').toUpperCase()).filter(Boolean);
    return { name: cname, type: 'unique', columns: cols };
  }

  if (/^FOREIGN\s+KEY/i.test(def)) {
    const fromCols = extractParen(def).split(',')
      .map(c => c.trim().replace(/"/g, '').toUpperCase()).filter(Boolean);
    const rm = def.match(/REFERENCES\s+"?(\w+(?:\.\w+)?)"?\s*\(([^)]+)\)/i);
    let toTable = '', toCols = [];
    if (rm) {
      toTable = parseName(rm[1]).full;
      toCols  = rm[2].split(',').map(c => c.trim().replace(/"/g, '').toUpperCase());
    }
    const od = def.match(/ON\s+DELETE\s+(CASCADE|SET\s+NULL|SET\s+DEFAULT|RESTRICT|NO\s+ACTION)/i);
    return {
      name: cname, type: 'foreign_key', columns: fromCols,
      references: {
        table:    toTable,
        columns:  toCols,
        onDelete: od ? od[1].toUpperCase().replace(/\s+/, '_') : null,
      },
    };
  }

  if (/^CHECK/i.test(def)) {
    return { name: cname, type: 'check', columns: [], checkExpr: extractParen(def) };
  }

  return null;
}

// ─────────────────────────────────────────────
// DDL STATEMENT HANDLERS
// ─────────────────────────────────────────────

/** Handle CREATE TABLE — builds table entry in the tables map */
export function handleCreateTable(stmt, version, tables) {
  const hm = stmt.match(/^CREATE\s+TABLE\s+"?(\w+(?:\.\w+)?)"?\s*\(/i);
  if (!hm) return;
  const qn   = parseName(hm[1]);
  const body = extractParen(stmt);
  if (!body) return;

  const columns = [], constraints = [];
  for (const d of splitComma(body)) {
    const dt = d.trim(); if (!dt) continue;
    if (/^(CONSTRAINT\s+\w+\s+)?(PRIMARY\s+KEY|FOREIGN\s+KEY|UNIQUE|CHECK)/i.test(dt)) {
      const c = parseConstraint(dt); if (c) constraints.push(c);
    } else {
      const col = parseColDef(dt);
      if (col) {
        if (col.primaryKey) {
          constraints.push({ name: `PK_${qn.name}`, type: 'primary_key', columns: [col.name] });
        }
        if (col.references) {
          constraints.push({
            name: null, type: 'foreign_key', columns: [col.name],
            references: { table: col.references.table, columns: [col.references.column], onDelete: null },
          });
        }
        columns.push(col);
      }
    }
  }

  tables.set(qn.full, {
    id:         qn.full,
    schema:     qn.schema,
    name:       qn.name,
    full:       qn.full,
    columns,
    constraints,
    indexes:    [],
    comments:   {},
    createdIn:  version,
    modifiedIn: [],
  });
}

/** Handle ALTER TABLE — supports ADD COLUMN and ADD CONSTRAINT */
export function handleAlterTable(stmt, version, tables) {
  const tm = stmt.match(/^ALTER\s+TABLE\s+"?(\w+(?:\.\w+)?)"?\s+/i);
  if (!tm) return;
  const key   = parseName(tm[1]).full;
  const table = tables.get(key);
  const rest  = stmt.slice(tm[0].length).trim();

  // ADD CONSTRAINT
  if (/^ADD\s+CONSTRAINT/i.test(rest)) {
    const c = parseConstraint(rest.replace(/^ADD\s+/i, '').trim());
    if (c && table) {
      table.constraints.push(c);
      if (!table.modifiedIn.includes(version)) table.modifiedIn.push(version);
    }
    return;
  }

  // ADD (col1, col2, ...)
  if (/^ADD\s*\(/i.test(rest)) {
    const body = extractParen(rest.slice(3));
    for (const d of splitComma(body)) {
      const col = parseColDef(d.trim());
      if (col && table) {
        table.columns.push(col);
        if (!table.modifiedIn.includes(version)) table.modifiedIn.push(version);
      }
    }
    return;
  }

  // ADD col (bare, no parens)
  if (/^ADD\s+\w/i.test(rest)) {
    const col = parseColDef(rest.slice(4).trim());
    if (col && table) {
      table.columns.push(col);
      if (!table.modifiedIn.includes(version)) table.modifiedIn.push(version);
    }
  }
}

/** Handle CREATE [UNIQUE] INDEX */
export function handleCreateIndex(stmt, version, tables) {
  const m = stmt.match(
    /^CREATE\s+(UNIQUE\s+)?INDEX\s+"?(\w+(?:\.\w+)?)"?\s+ON\s+"?(\w+(?:\.\w+)?)"?\s*\(([^)]+)\)/i
  );
  if (!m) return;
  const unique = !!m[1];
  const idxN  = parseName(m[2]);
  const tblN  = parseName(m[3]);
  const cols  = m[4].split(',').map(c =>
    c.trim().replace(/\s+(ASC|DESC)$/i, '').replace(/"/g, '').toUpperCase()
  );
  const t = tables.get(tblN.full);
  if (t) t.indexes.push({ name: idxN.name, columns: cols, unique, createdIn: version });
}

/** Handle CREATE SEQUENCE */
export function handleCreateSeq(stmt, version, seqs) {
  const m = stmt.match(/^CREATE\s+SEQUENCE\s+"?(\w+(?:\.\w+)?)"?/i);
  if (!m) return;
  const qn = parseName(m[1]);
  const sw = stmt.match(/START\s+WITH\s+(\d+)/i);
  const ib = stmt.match(/INCREMENT\s+BY\s+(\d+)/i);
  seqs.set(qn.full, {
    name:        qn.name,
    schema:      qn.schema,
    full:        qn.full,
    startWith:   sw ? parseInt(sw[1]) : 1,
    incrementBy: ib ? parseInt(ib[1]) : 1,
    createdIn:   version,
  });
}

/** Handle COMMENT ON TABLE / COLUMN */
export function handleComment(stmt, tables) {
  const tm = stmt.match(/COMMENT\s+ON\s+TABLE\s+"?(\w+(?:\.\w+)?)"?\s+IS\s+'([^']*)'/i);
  if (tm) {
    const t = tables.get(parseName(tm[1]).full);
    if (t) t.comments['__table__'] = tm[2];
    return;
  }
  const cm = stmt.match(/COMMENT\s+ON\s+COLUMN\s+"?(\w+(?:\.\w+)?)\.(\w+)"?\s+IS\s+'([^']*)'/i);
  if (cm) {
    const t = tables.get(parseName(cm[1]).full);
    if (t) t.comments[cm[2].toUpperCase()] = cm[3];
  }
}

// ─────────────────────────────────────────────
// FLYWAY ORCHESTRATOR
// ─────────────────────────────────────────────

/**
 * Parse a Flyway filename into { version, description, order }.
 * Supports V1, V1.2, V1.2.3 etc.
 */
export function parseFlywayVer(filename) {
  const m = filename.match(/^V([\d.]+)__(.+?)\.sql$/i);
  if (!m) return { version: '0', description: filename, order: 0 };
  const parts = m[1].split('.').map(Number);
  const order = parts.reduce((acc, n, i) => acc + n * Math.pow(1000, 3 - i), 0);
  return { version: m[1], description: m[2].replace(/_/g, ' '), order };
}

/**
 * Main orchestrator. Takes an array of { filename, sql } objects,
 * sorts them by Flyway version, applies each migration in order,
 * and returns the final accumulated schema graph.
 *
 * @param {Array<{ filename: string, sql: string }>} files
 * @returns {{ tables: Map, seqs: Map, edges: Array, migHist: Array }}
 */
export function applyMigrations(files) {
  const sorted = [...files]
    .map(f => ({ ...f, ...parseFlywayVer(f.filename) }))
    .sort((a, b) => a.order - b.order);

  const tables  = new Map();
  const seqs    = new Map();
  const migHist = [];

  for (const file of sorted) {
    migHist.push({ version: file.version, description: file.description });
    const clean = stripComments(file.sql);
    const stmts = splitStmts(clean);

    for (const stmt of stmts) {
      const u  = stmt.replace(/\s+/g, ' ').trim();
      if (!u) continue;
      const up = u.toUpperCase();

      if      (up.startsWith('CREATE TABLE'))                        handleCreateTable(stmt, file.version, tables);
      else if (up.startsWith('ALTER TABLE'))                         handleAlterTable(stmt, file.version, tables);
      else if (up.startsWith('CREATE INDEX') ||
               up.startsWith('CREATE UNIQUE INDEX'))                 handleCreateIndex(stmt, file.version, tables);
      else if (up.startsWith('CREATE SEQUENCE'))                     handleCreateSeq(stmt, file.version, seqs);
      else if (up.startsWith('COMMENT ON'))                          handleComment(stmt, tables);
    }
  }

  // Derive FK edges from accumulated constraints
  const edges = [];
  for (const [, t] of tables) {
    for (const c of t.constraints) {
      if (c.type === 'foreign_key' && c.references) {
        edges.push({
          id:             `${t.full}→${c.references.table}:${c.name}`,
          fromTable:      t.full,
          fromCols:       c.columns,
          toTable:        c.references.table,
          toCols:         c.references.columns,
          constraintName: c.name,
          onDelete:       c.references.onDelete,
        });
      }
    }
  }

  return { tables, seqs, edges, migHist };
}

// ─────────────────────────────────────────────
// LLM VECTOR CHUNK BUILDER
// ─────────────────────────────────────────────

/**
 * Build LLM-ready vector chunks from a schema graph.
 * Produces one chunk per table, plus a schema summary chunk
 * and a relationship graph chunk.
 *
 * Each chunk: { id, type, title, content, meta, hint }
 *
 * @param {{ tables: Map, seqs: Map, edges: Array, migHist: Array }} graph
 * @returns {Array<Object>}
 */
export function buildChunks(graph) {
  const { tables, seqs, edges, migHist } = graph;
  const chunks = [];

  // ── Per-table chunks ──
  for (const [, t] of tables) {
    const pk   = t.constraints.find(c => c.type === 'primary_key');
    const fks  = t.constraints.filter(c => c.type === 'foreign_key');
    const uqs  = t.constraints.filter(c => c.type === 'unique');
    const cks  = t.constraints.filter(c => c.type === 'check');
    const outE = edges.filter(e => e.fromTable === t.full);
    const inE  = edges.filter(e => e.toTable   === t.full);

    const L = [];
    L.push(`TABLE: ${t.full}`);
    if (t.comments['__table__']) L.push(`Description: ${t.comments['__table__']}`);
    L.push(`Schema: ${t.schema || 'default'} | Created: V${t.createdIn}${t.modifiedIn.length ? ` | Modified: V${t.modifiedIn.join(', V')}` : ''}`);
    L.push('');
    L.push('COLUMNS:');

    for (const col of t.columns) {
      const flags = [];
      if (pk?.columns.includes(col.name))               flags.push('PK');
      if (!col.nullable)                                 flags.push('NOT NULL');
      if (col.default)                                   flags.push(`DEFAULT ${col.default}`);
      if (uqs.some(u => u.columns.includes(col.name)))   flags.push('UNIQUE');
      if (outE.some(e => e.fromCols.includes(col.name))) flags.push('FK');
      const comment = t.comments[col.name];
      L.push(`  ${col.name}: ${typeStr(col)}${flags.length ? ` [${flags.join(', ')}]` : ''}${comment ? ` -- ${comment}` : ''}`);
    }

    if (outE.length) {
      L.push('');
      L.push('REFERENCES (outgoing FK):');
      for (const e of outE) {
        L.push(`  ${e.fromCols.join(',')}) → ${e.toTable}(${e.toCols.join(',')})${e.onDelete ? ` ON DELETE ${e.onDelete}` : ''}${e.constraintName ? ` [${e.constraintName}]` : ''}`);
      }
    }
    if (inE.length) {
      L.push('');
      L.push('REFERENCED BY:');
      for (const e of inE) L.push(`  ${e.fromTable}.${e.fromCols.join(',')} → ${e.toCols.join(',')}`);
    }
    if (t.indexes.length) {
      L.push('');
      L.push('INDEXES:');
      for (const idx of t.indexes) L.push(`  ${idx.name}: (${idx.columns.join(', ')})${idx.unique ? ' UNIQUE' : ''} [V${idx.createdIn}]`);
    }
    if (cks.length) {
      L.push('');
      L.push('CHECK CONSTRAINTS:');
      for (const ck of cks) L.push(`  ${ck.name || 'unnamed'}: CHECK (${ck.checkExpr})`);
    }

    chunks.push({
      id:      `table:${t.full}`,
      type:    'table',
      title:   `Table: ${t.name}`,
      content: L.join('\n'),
      meta: {
        tableName:   t.name,
        schema:      t.schema,
        columnCount: t.columns.length,
        hasPK:       !!pk,
        fkCount:     fks.length,
        referencedBy: inE.length,
        indexCount:  t.indexes.length,
        createdIn:   t.createdIn,
        pkCols:      pk?.columns || [],
      },
      hint: `Use for: queries about ${t.name} table — columns, types, constraints, FK relationships.`,
    });
  }

  // ── Schema summary chunk ──
  const tableNames = [...tables.keys()];
  const totalCols  = [...tables.values()].reduce((s, t) => s + t.columns.length, 0);
  const schemas    = [...new Set([...tables.values()].map(t => t.schema).filter(Boolean))];

  const sumL = [
    'SCHEMA SUMMARY',
    `DB Schemas: ${schemas.join(', ')}`,
    `Tables: ${tableNames.length} (${tableNames.join(', ')})`,
    `Sequences: ${seqs.size} (${[...seqs.keys()].join(', ')})`,
    `Total columns: ${totalCols}`,
    `FK relationships: ${edges.length}`,
    `Migration history: ${migHist.map(m => `V${m.version} (${m.description})`).join(' → ')}`,
    '',
    'RELATIONSHIP MAP:',
    ...edges.map(e => `  ${e.fromTable}.${e.fromCols.join(',')} → ${e.toTable}.${e.toCols.join(',')}`),
    '',
    'TABLE ROLES:',
    ...[...tables.values()].map(t => {
      const o = edges.filter(e => e.fromTable === t.full).length;
      const i = edges.filter(e => e.toTable   === t.full).length;
      let role = 'standalone';
      if      (i > 0 && o === 0) role = 'root/parent entity';
      else if (o > 0 && i > 0)   role = 'junction/child entity';
      else if (o > 0 && i === 0) role = 'leaf/detail entity';
      return `  ${t.full}: ${role} (referenced by ${i}, references ${o})`;
    }),
  ];

  chunks.unshift({
    id:      'schema:summary',
    type:    'schema_summary',
    title:   'Schema Summary',
    content: sumL.join('\n'),
    meta:    { tableCount: tables.size, seqCount: seqs.size, edgeCount: edges.length, columnCount: totalCols, schemas },
    hint:    'Use for: high-level schema questions, table count, migration history, overall topology.',
  });

  // ── Relationship graph chunk ──
  const relL = ['RELATIONSHIP GRAPH (adjacency list)', ''];
  for (const tname of tableNames) {
    const out = edges.filter(e => e.fromTable === tname);
    const inn = edges.filter(e => e.toTable   === tname);
    relL.push(`${tname}:`);
    for (const e of out) relL.push(`  ──FK──▶ ${e.toTable} via ${e.fromCols.join(',')}${e.onDelete ? ` [ON DELETE ${e.onDelete}]` : ''}`);
    for (const e of inn) relL.push(`  ◀──FK── ${e.fromTable} via ${e.fromCols.join(',')}`);
    if (!out.length && !inn.length) relL.push('  (no FK relationships)');
  }

  chunks.push({
    id:      'schema:relationships',
    type:    'relationship_map',
    title:   'Relationship Graph',
    content: relL.join('\n'),
    meta:    { edges: edges.map(e => ({ from: e.fromTable, to: e.toTable, via: e.fromCols, onDelete: e.onDelete })) },
    hint:    'Use for: JOIN path planning, cascade analysis, understanding table connectivity.',
  });

  return chunks;
}

// ─────────────────────────────────────────────
// ERD LAYOUT ENGINE
// ─────────────────────────────────────────────

/**
 * Compute (x, y) positions for each table node using FK-depth layering.
 * Parent tables (referenced but not referencing) sit at the top;
 * leaf tables (referencing but not referenced) at the bottom.
 *
 * @param {Map} tables
 * @param {Array} edges
 * @param {{ width?: number, height?: number }} options
 * @returns {Map<string, { x: number, y: number }>}
 */
export function computeLayout(tables, edges, { width = 580, height = 220 } = {}) {
  const levels = new Map();
  for (const k of tables.keys()) levels.set(k, 0);

  // Iteratively push parent tables upward
  for (let i = 0; i < 10; i++) {
    let changed = false;
    for (const e of edges) {
      const fl = levels.get(e.fromTable) || 0;
      const tl = levels.get(e.toTable)   || 0;
      if (fl <= tl) { levels.set(e.fromTable, tl + 1); changed = true; }
    }
    if (!changed) break;
  }

  const byLevel = new Map();
  for (const [t, l] of levels) {
    if (!byLevel.has(l)) byLevel.set(l, []);
    byLevel.get(l).push(t);
  }

  const pos  = new Map();
  const maxL = Math.max(0, ...[...levels.values()]);

  for (const [level, tbls] of byLevel) {
    const y = maxL === 0 ? height / 2 : (level / maxL) * (height - 80) + 40;
    tbls.forEach((t, i) => {
      const x = ((i + 1) / (tbls.length + 1)) * width;
      pos.set(t, { x, y });
    });
  }

  return pos;
}
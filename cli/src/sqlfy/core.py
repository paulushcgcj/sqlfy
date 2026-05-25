"""
sqlfy.core
==========
Pure logic module — Python port of cli/core.js.

No I/O, no CLI concerns. Safe to import in both the CLI runner
and future API/Tauri bridge layers.
"""

from __future__ import annotations

import re
import math
from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────
# DATA TYPES
# ─────────────────────────────────────────────

@dataclass
class Column:
    name: str
    type: str
    precision: Optional[int]
    scale: Optional[int]
    nullable: bool
    default: Optional[str]
    primary_key: bool
    unique: bool
    references: Optional[dict]   # { table, column }


@dataclass
class Constraint:
    name: Optional[str]
    type: str                    # primary_key | unique | foreign_key | check
    columns: list[str]
    references: Optional[dict] = None   # { table, columns, on_delete }
    check_expr: Optional[str]  = None


@dataclass
class Index:
    name: str
    columns: list[str]
    unique: bool
    created_in: str


@dataclass
class Table:
    id: str
    schema: Optional[str]
    name: str
    full: str
    columns: list[Column]        = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)
    indexes: list[Index]         = field(default_factory=list)
    comments: dict[str, str]     = field(default_factory=dict)
    created_in: str              = ''
    modified_in: list[str]       = field(default_factory=list)


@dataclass
class Sequence:
    name: str
    schema: Optional[str]
    full: str
    start_with: int
    increment_by: int
    created_in: str


@dataclass
class Edge:
    id: str
    from_table: str
    from_cols: list[str]
    to_table: str
    to_cols: list[str]
    constraint_name: Optional[str]
    on_delete: Optional[str]


@dataclass
class MigrationHistory:
    version: str
    description: str


@dataclass
class SchemaGraph:
    tables: dict[str, Table]
    seqs: dict[str, Sequence]
    edges: list[Edge]
    mig_hist: list[MigrationHistory]


@dataclass
class VectorChunk:
    id: str
    type: str
    title: str
    content: str
    meta: dict
    hint: str


# ─────────────────────────────────────────────
# SQL TOKENISER UTILITIES
# ─────────────────────────────────────────────

def strip_comments(sql: str) -> str:
    """Remove block (/* */) and line (--) comments."""
    sql = re.sub(r'/\*[\s\S]*?\*/', ' ', sql)
    sql = re.sub(r'--[^\n]*', ' ', sql)
    return sql


def split_stmts(sql: str) -> list[str]:
    """
    Split SQL into individual statements on ';',
    respecting string literals and nested parentheses.
    """
    result: list[str] = []
    depth = 0
    cur: list[str] = []
    in_str = False
    i = 0

    while i < len(sql):
        c = sql[i]
        if in_str:
            cur.append(c)
            if c == "'":
                if i + 1 < len(sql) and sql[i + 1] == "'":
                    cur.append(sql[i + 1])
                    i += 1
                else:
                    in_str = False
        elif c == "'":
            in_str = True
            cur.append(c)
        elif c == '(':
            depth += 1
            cur.append(c)
        elif c == ')':
            depth -= 1
            cur.append(c)
        elif c == ';' and depth == 0:
            s = ''.join(cur).strip()
            if s:
                result.append(s)
            cur = []
        else:
            cur.append(c)
        i += 1

    s = ''.join(cur).strip()
    if s:
        result.append(s)
    return result


def extract_paren(s: str) -> str:
    """Extract the content of the outermost parentheses."""
    start = s.find('(')
    if start < 0:
        return ''
    depth = 0
    for i in range(start, len(s)):
        if s[i] == '(':
            depth += 1
        elif s[i] == ')':
            depth -= 1
            if depth == 0:
                return s[start + 1:i]
    return ''


def split_comma(s: str) -> list[str]:
    """Comma-split respecting nested parens and string literals."""
    result: list[str] = []
    depth = 0
    cur: list[str] = []
    in_str = False

    for c in s:
        if in_str:
            cur.append(c)
            if c == "'":
                in_str = False
        elif c == "'":
            in_str = True
            cur.append(c)
        elif c == '(':
            depth += 1
            cur.append(c)
        elif c == ')':
            depth -= 1
            cur.append(c)
        elif c == ',' and depth == 0:
            p = ''.join(cur).strip()
            if p:
                result.append(p)
            cur = []
        else:
            cur.append(c)

    p = ''.join(cur).strip()
    if p:
        result.append(p)
    return result


# ─────────────────────────────────────────────
# NAME / TYPE PARSING
# ─────────────────────────────────────────────

def parse_name(s: str) -> dict:
    """
    Parse a potentially schema-qualified name.
    'APP.USERS' → { schema: 'APP', name: 'USERS', full: 'APP.USERS' }
    """
    s = s.strip().replace('"', '')
    parts = s.split('.')
    if len(parts) >= 2:
        schema = parts[0].upper()
        name   = parts[1].upper()
        return {'schema': schema, 'name': name, 'full': f'{schema}.{name}'}
    return {'schema': None, 'name': s.upper(), 'full': s.upper()}


def parse_data_type(s: str) -> dict:
    """
    Parse a data-type token.
    'NUMBER(10,2)' → { type: 'NUMBER', precision: 10, scale: 2 }
    """
    m = re.match(r'^([A-Z][A-Z0-9 ]*)(?:\(([^)]+)\))?$', s.strip(), re.I)
    if not m:
        return {'type': s.strip().upper(), 'precision': None, 'scale': None}
    type_ = m.group(1).strip().upper()
    if not m.group(2):
        return {'type': type_, 'precision': None, 'scale': None}
    parts = [p.strip() for p in m.group(2).split(',')]
    precision = int(parts[0]) if parts[0] else None
    scale     = int(parts[1]) if len(parts) > 1 and parts[1] else None
    return {'type': type_, 'precision': precision, 'scale': scale}


def type_str(col: Column) -> str:
    """Render column data type back to a display string."""
    if col.precision is not None and col.scale is not None:
        return f'{col.type}({col.precision},{col.scale})'
    if col.precision is not None:
        return f'{col.type}({col.precision})'
    return col.type


# ─────────────────────────────────────────────
# COLUMN + CONSTRAINT PARSERS
# ─────────────────────────────────────────────

def parse_col_def(definition: str) -> Optional[Column]:
    """
    Parse a single column definition from a CREATE TABLE body.
    Returns None if it looks like a constraint, not a column.
    """
    definition = re.sub(r'\s+', ' ', definition).strip()
    nm = re.match(r'^"?(\w+)"?\s+', definition)
    if not nm:
        return None

    name = nm.group(1).upper()
    rest = definition[nm.end():].strip()

    # Extract data type (may contain parens)
    type_s = []
    depth = 0
    i = 0
    while i < len(rest):
        c = rest[i]
        if c == '(':
            depth += 1; type_s.append(c)
        elif c == ')':
            depth -= 1; type_s.append(c)
        elif c == ' ' and depth == 0:
            break
        else:
            type_s.append(c)
        i += 1

    dt = parse_data_type(''.join(type_s))
    rest = rest[i:].strip()

    nullable    = True
    default_val = None
    primary_key = False
    unique      = False
    references  = None

    # DEFAULT value
    dm = re.search(
        r'DEFAULT\s+(.+?)(?=\s+(?:NOT\s+NULL|NULL|CONSTRAINT|PRIMARY|UNIQUE|REFERENCES|ENABLE|DISABLE)|$)',
        rest, re.I
    )
    if dm:
        default_val = dm.group(1).strip()
        rest = rest[:dm.start()] + rest[dm.end():]
        rest = rest.strip()

    if re.search(r'NOT\s+NULL', rest, re.I):
        nullable = False
    if re.search(r'\bPRIMARY\s+KEY\b', rest, re.I):
        primary_key = True
    if re.search(r'\bUNIQUE\b', rest, re.I):
        unique = True

    rm = re.search(r'REFERENCES\s+"?(\w+(?:\.\w+)?)"?\s*\("?(\w+)"?\)', rest, re.I)
    if rm:
        ref_tbl = parse_name(rm.group(1))
        references = {'table': ref_tbl['full'], 'column': rm.group(2).upper()}

    return Column(
        name=name,
        type=dt['type'],
        precision=dt['precision'],
        scale=dt['scale'],
        nullable=nullable,
        default=default_val,
        primary_key=primary_key,
        unique=unique,
        references=references,
    )


def parse_constraint(definition: str) -> Optional[Constraint]:
    """
    Parse a table constraint (PRIMARY KEY, UNIQUE, FOREIGN KEY, CHECK).
    Handles both bare and CONSTRAINT <name> ... forms.
    """
    definition = re.sub(r'\s+', ' ', definition).strip()
    cname = None

    cn = re.match(r'^CONSTRAINT\s+"?(\w+)"?\s+', definition, re.I)
    if cn:
        cname = cn.group(1).upper()
        definition = definition[cn.end():].strip()

    if re.match(r'^PRIMARY\s+KEY', definition, re.I):
        cols = [c.strip().replace('"', '').upper()
                for c in extract_paren(definition).split(',') if c.strip()]
        return Constraint(name=cname, type='primary_key', columns=cols)

    if re.match(r'^UNIQUE', definition, re.I):
        cols = [c.strip().replace('"', '').upper()
                for c in extract_paren(definition).split(',') if c.strip()]
        return Constraint(name=cname, type='unique', columns=cols)

    if re.match(r'^FOREIGN\s+KEY', definition, re.I):
        from_cols = [c.strip().replace('"', '').upper()
                     for c in extract_paren(definition).split(',') if c.strip()]
        rm = re.search(r'REFERENCES\s+"?(\w+(?:\.\w+)?)"?\s*\(([^)]+)\)', definition, re.I)
        to_table = ''
        to_cols: list[str] = []
        if rm:
            to_table = parse_name(rm.group(1))['full']
            to_cols  = [c.strip().replace('"', '').upper() for c in rm.group(2).split(',')]
        od = re.search(
            r'ON\s+DELETE\s+(CASCADE|SET\s+NULL|SET\s+DEFAULT|RESTRICT|NO\s+ACTION)',
            definition, re.I
        )
        on_delete = re.sub(r'\s+', '_', od.group(1).upper()) if od else None
        return Constraint(
            name=cname, type='foreign_key', columns=from_cols,
            references={'table': to_table, 'columns': to_cols, 'on_delete': on_delete},
        )

    if re.match(r'^CHECK', definition, re.I):
        return Constraint(name=cname, type='check', columns=[], check_expr=extract_paren(definition))

    return None


# ─────────────────────────────────────────────
# DDL STATEMENT HANDLERS
# ─────────────────────────────────────────────

def handle_create_table(stmt: str, version: str, tables: dict[str, Table]) -> None:
    hm = re.match(r'^CREATE\s+TABLE\s+"?(\w+(?:\.\w+)?)"?\s*\(', stmt, re.I)
    if not hm:
        return
    qn   = parse_name(hm.group(1))
    body = extract_paren(stmt)
    if not body:
        return

    columns: list[Column]         = []
    constraints: list[Constraint] = []

    for d in split_comma(body):
        dt = d.strip()
        if not dt:
            continue
        if re.match(r'^(CONSTRAINT\s+\w+\s+)?(PRIMARY\s+KEY|FOREIGN\s+KEY|UNIQUE|CHECK)', dt, re.I):
            c = parse_constraint(dt)
            if c:
                constraints.append(c)
        else:
            col = parse_col_def(dt)
            if col:
                if col.primary_key:
                    constraints.append(Constraint(
                        name=f'PK_{qn["name"]}', type='primary_key', columns=[col.name]
                    ))
                if col.references:
                    constraints.append(Constraint(
                        name=None, type='foreign_key', columns=[col.name],
                        references={
                            'table': col.references['table'],
                            'columns': [col.references['column']],
                            'on_delete': None,
                        },
                    ))
                columns.append(col)

    tables[qn['full']] = Table(
        id=qn['full'], schema=qn['schema'], name=qn['name'], full=qn['full'],
        columns=columns, constraints=constraints,
        created_in=version,
    )


def handle_alter_table(stmt: str, version: str, tables: dict[str, Table]) -> None:
    tm = re.match(r'^ALTER\s+TABLE\s+"?(\w+(?:\.\w+)?)"?\s+', stmt, re.I)
    if not tm:
        return
    key   = parse_name(tm.group(1))['full']
    table = tables.get(key)
    rest  = stmt[tm.end():].strip()

    # ADD CONSTRAINT
    if re.match(r'^ADD\s+CONSTRAINT', rest, re.I):
        c = parse_constraint(re.sub(r'^ADD\s+', '', rest, flags=re.I).strip())
        if c and table:
            table.constraints.append(c)
            if version not in table.modified_in:
                table.modified_in.append(version)
        return

    # ADD (col1, col2, ...)
    if re.match(r'^ADD\s*\(', rest, re.I):
        body = extract_paren(rest[3:])
        for d in split_comma(body):
            col = parse_col_def(d.strip())
            if col and table:
                table.columns.append(col)
                if version not in table.modified_in:
                    table.modified_in.append(version)
        return

    # ADD col (bare)
    if re.match(r'^ADD\s+\w', rest, re.I):
        col = parse_col_def(rest[4:].strip())
        if col and table:
            table.columns.append(col)
            if version not in table.modified_in:
                table.modified_in.append(version)


def handle_create_index(stmt: str, version: str, tables: dict[str, Table]) -> None:
    m = re.match(
        r'^CREATE\s+(UNIQUE\s+)?INDEX\s+"?(\w+(?:\.\w+)?)"?\s+ON\s+"?(\w+(?:\.\w+)?)"?\s*\(([^)]+)\)',
        stmt, re.I
    )
    if not m:
        return
    unique = bool(m.group(1))
    idx_n  = parse_name(m.group(2))
    tbl_n  = parse_name(m.group(3))
    cols   = [re.sub(r'\s+(ASC|DESC)$', '', c.strip(), flags=re.I).replace('"', '').upper()
              for c in m.group(4).split(',')]
    t = tables.get(tbl_n['full'])
    if t:
        t.indexes.append(Index(name=idx_n['name'], columns=cols, unique=unique, created_in=version))


def handle_create_seq(stmt: str, version: str, seqs: dict[str, Sequence]) -> None:
    m = re.match(r'^CREATE\s+SEQUENCE\s+"?(\w+(?:\.\w+)?)"?', stmt, re.I)
    if not m:
        return
    qn = parse_name(m.group(1))
    sw = re.search(r'START\s+WITH\s+(\d+)', stmt, re.I)
    ib = re.search(r'INCREMENT\s+BY\s+(\d+)', stmt, re.I)
    seqs[qn['full']] = Sequence(
        name=qn['name'], schema=qn['schema'], full=qn['full'],
        start_with=int(sw.group(1)) if sw else 1,
        increment_by=int(ib.group(1)) if ib else 1,
        created_in=version,
    )


def handle_comment(stmt: str, tables: dict[str, Table]) -> None:
    tm = re.search(r"COMMENT\s+ON\s+TABLE\s+\"?(\w+(?:\.\w+)?)\s*\"?\s+IS\s+'([^']*)'", stmt, re.I)
    if tm:
        t = tables.get(parse_name(tm.group(1))['full'])
        if t:
            t.comments['__table__'] = tm.group(2)
        return
    cm = re.search(r"COMMENT\s+ON\s+COLUMN\s+\"?(\w+(?:\.\w+)?)\.(\w+)\"?\s+IS\s+'([^']*)'", stmt, re.I)
    if cm:
        t = tables.get(parse_name(cm.group(1))['full'])
        if t:
            t.comments[cm.group(2).upper()] = cm.group(3)


# ─────────────────────────────────────────────
# FLYWAY ORCHESTRATOR
# ─────────────────────────────────────────────

def parse_flyway_ver(filename: str) -> dict:
    """
    Parse a Flyway filename into { version, description, order }.
    Supports V1, V1.2, V1.2.3, etc.
    """
    m = re.match(r'^V([\d.]+)__(.+?)\.sql$', filename, re.I)
    if not m:
        return {'version': '0', 'description': filename, 'order': 0}
    parts = [int(p) for p in m.group(1).split('.')]
    order = sum(n * (1000 ** (3 - i)) for i, n in enumerate(parts))
    return {
        'version':     m.group(1),
        'description': m.group(2).replace('_', ' '),
        'order':       order,
    }


def apply_migrations(files: list[dict]) -> SchemaGraph:
    """
    Main orchestrator.

    Args:
        files: list of { filename: str, sql: str }

    Returns:
        SchemaGraph with accumulated tables, sequences, FK edges, and migration history.
    """
    sorted_files = sorted(files, key=lambda f: parse_flyway_ver(f['filename'])['order'])

    tables:   dict[str, Table]    = {}
    seqs:     dict[str, Sequence] = {}
    mig_hist: list[MigrationHistory] = []

    for file in sorted_files:
        ver = parse_flyway_ver(file['filename'])
        mig_hist.append(MigrationHistory(version=ver['version'], description=ver['description']))

        clean = strip_comments(file['sql'])
        stmts = split_stmts(clean)

        for stmt in stmts:
            u  = re.sub(r'\s+', ' ', stmt).strip()
            if not u:
                continue
            up = u.upper()

            if up.startswith('CREATE TABLE'):
                handle_create_table(stmt, ver['version'], tables)
            elif up.startswith('ALTER TABLE'):
                handle_alter_table(stmt, ver['version'], tables)
            elif up.startswith('CREATE INDEX') or up.startswith('CREATE UNIQUE INDEX'):
                handle_create_index(stmt, ver['version'], tables)
            elif up.startswith('CREATE SEQUENCE'):
                handle_create_seq(stmt, ver['version'], seqs)
            elif up.startswith('COMMENT ON'):
                handle_comment(stmt, tables)

    # Derive FK edges from accumulated constraints
    edges: list[Edge] = []
    for t in tables.values():
        for c in t.constraints:
            if c.type == 'foreign_key' and c.references:
                edges.append(Edge(
                    id=f'{t.full}→{c.references["table"]}:{c.name}',
                    from_table=t.full,
                    from_cols=c.columns,
                    to_table=c.references['table'],
                    to_cols=c.references['columns'],
                    constraint_name=c.name,
                    on_delete=c.references.get('on_delete'),
                ))

    return SchemaGraph(tables=tables, seqs=seqs, edges=edges, mig_hist=mig_hist)


# ─────────────────────────────────────────────
# LLM VECTOR CHUNK BUILDER
# ─────────────────────────────────────────────

def build_chunks(graph: SchemaGraph) -> list[VectorChunk]:
    """
    Build LLM-ready vector chunks from a SchemaGraph.
    Produces one chunk per table, a schema summary chunk,
    and a relationship graph chunk.
    """
    tables   = graph.tables
    seqs     = graph.seqs
    edges    = graph.edges
    mig_hist = graph.mig_hist
    chunks:  list[VectorChunk] = []

    def out_edges(full: str) -> list[Edge]:
        return [e for e in edges if e.from_table == full]

    def in_edges(full: str) -> list[Edge]:
        return [e for e in edges if e.to_table == full]

    for t in tables.values():
        pk   = next((c for c in t.constraints if c.type == 'primary_key'), None)
        fks  = [c for c in t.constraints if c.type == 'foreign_key']
        uqs  = [c for c in t.constraints if c.type == 'unique']
        cks  = [c for c in t.constraints if c.type == 'check']
        out_e = out_edges(t.full)
        in_e  = in_edges(t.full)

        L: list[str] = []
        L.append(f'TABLE: {t.full}')
        if t.comments.get('__table__'):
            L.append(f'Description: {t.comments["__table__"]}')
        modified = f' | Modified: V{", V".join(t.modified_in)}' if t.modified_in else ''
        L.append(f'Schema: {t.schema or "default"} | Created: V{t.created_in}{modified}')
        L.append('')
        L.append('COLUMNS:')

        for col in t.columns:
            flags: list[str] = []
            if pk and col.name in pk.columns:
                flags.append('PK')
            if not col.nullable:
                flags.append('NOT NULL')
            if col.default:
                flags.append(f'DEFAULT {col.default}')
            if any(col.name in u.columns for u in uqs):
                flags.append('UNIQUE')
            if any(col.name in e.from_cols for e in out_e):
                flags.append('FK')
            comment = t.comments.get(col.name, '')
            flag_str = f' [{", ".join(flags)}]' if flags else ''
            cmt_str  = f' -- {comment}' if comment else ''
            L.append(f'  {col.name}: {type_str(col)}{flag_str}{cmt_str}')

        if out_e:
            L.append('')
            L.append('REFERENCES (outgoing FK):')
            for e in out_e:
                od  = f' ON DELETE {e.on_delete}' if e.on_delete else ''
                cn  = f' [{e.constraint_name}]' if e.constraint_name else ''
                L.append(f'  {",".join(e.from_cols)}) → {e.to_table}({",".join(e.to_cols)}){od}{cn}')

        if in_e:
            L.append('')
            L.append('REFERENCED BY:')
            for e in in_e:
                L.append(f'  {e.from_table}.{",".join(e.from_cols)} → {",".join(e.to_cols)}')

        if t.indexes:
            L.append('')
            L.append('INDEXES:')
            for idx in t.indexes:
                uq = ' UNIQUE' if idx.unique else ''
                L.append(f'  {idx.name}: ({", ".join(idx.columns)}){uq} [V{idx.created_in}]')

        if cks:
            L.append('')
            L.append('CHECK CONSTRAINTS:')
            for ck in cks:
                L.append(f'  {ck.name or "unnamed"}: CHECK ({ck.check_expr})')

        chunks.append(VectorChunk(
            id=f'table:{t.full}',
            type='table',
            title=f'Table: {t.name}',
            content='\n'.join(L),
            meta={
                'table_name':   t.name,
                'schema':       t.schema,
                'column_count': len(t.columns),
                'has_pk':       pk is not None,
                'fk_count':     len(fks),
                'referenced_by': len(in_e),
                'index_count':  len(t.indexes),
                'created_in':   t.created_in,
                'pk_cols':      pk.columns if pk else [],
            },
            hint=f'Use for: queries about {t.name} table — columns, types, constraints, FK relationships.',
        ))

    # ── Schema summary chunk ──
    table_names = list(tables.keys())
    total_cols  = sum(len(t.columns) for t in tables.values())
    schemas     = list({t.schema for t in tables.values() if t.schema})

    sum_l = [
        'SCHEMA SUMMARY',
        f'DB Schemas: {", ".join(schemas)}',
        f'Tables: {len(table_names)} ({", ".join(table_names)})',
        f'Sequences: {len(seqs)} ({", ".join(seqs.keys())})',
        f'Total columns: {total_cols}',
        f'FK relationships: {len(edges)}',
        f'Migration history: {" → ".join(f"V{m.version} ({m.description})" for m in mig_hist)}',
        '',
        'RELATIONSHIP MAP:',
    ]
    for e in edges:
        sum_l.append(f'  {e.from_table}.{",".join(e.from_cols)} → {e.to_table}.{",".join(e.to_cols)}')
    sum_l.append('')
    sum_l.append('TABLE ROLES:')
    for t in tables.values():
        o = len(out_edges(t.full))
        i = len(in_edges(t.full))
        if i > 0 and o == 0:
            role = 'root/parent entity'
        elif o > 0 and i > 0:
            role = 'junction/child entity'
        elif o > 0 and i == 0:
            role = 'leaf/detail entity'
        else:
            role = 'standalone'
        sum_l.append(f'  {t.full}: {role} (referenced by {i}, references {o})')

    chunks.insert(0, VectorChunk(
        id='schema:summary',
        type='schema_summary',
        title='Schema Summary',
        content='\n'.join(sum_l),
        meta={
            'table_count':  len(tables),
            'seq_count':    len(seqs),
            'edge_count':   len(edges),
            'column_count': total_cols,
            'schemas':      schemas,
        },
        hint='Use for: high-level schema questions, table count, migration history, overall topology.',
    ))

    # ── Relationship graph chunk ──
    rel_l = ['RELATIONSHIP GRAPH (adjacency list)', '']
    for tname in table_names:
        out = out_edges(tname)
        inn = in_edges(tname)
        rel_l.append(f'{tname}:')
        for e in out:
            od = f' [ON DELETE {e.on_delete}]' if e.on_delete else ''
            rel_l.append(f'  ──FK──▶ {e.to_table} via {",".join(e.from_cols)}{od}')
        for e in inn:
            rel_l.append(f'  ◀──FK── {e.from_table} via {",".join(e.from_cols)}')
        if not out and not inn:
            rel_l.append('  (no FK relationships)')

    chunks.append(VectorChunk(
        id='schema:relationships',
        type='relationship_map',
        title='Relationship Graph',
        content='\n'.join(rel_l),
        meta={'edges': [{'from': e.from_table, 'to': e.to_table, 'via': e.from_cols, 'on_delete': e.on_delete} for e in edges]},
        hint='Use for: JOIN path planning, cascade analysis, understanding table connectivity.',
    ))

    return chunks


# ─────────────────────────────────────────────
# ERD LAYOUT ENGINE
# ─────────────────────────────────────────────

def compute_layout(
    tables: dict[str, Table],
    edges:  list[Edge],
    width:  float = 580,
    height: float = 220,
) -> dict[str, dict]:
    """
    Compute (x, y) positions for each table node using FK-depth layering.
    Returns { full_table_name: { x, y } }
    """
    levels: dict[str, int] = {k: 0 for k in tables}

    for _ in range(10):
        changed = False
        for e in edges:
            fl = levels.get(e.from_table, 0)
            tl = levels.get(e.to_table,   0)
            if fl <= tl:
                levels[e.from_table] = tl + 1
                changed = True
        if not changed:
            break

    by_level: dict[int, list[str]] = {}
    for t, l in levels.items():
        by_level.setdefault(l, []).append(t)

    max_l = max(levels.values(), default=0)
    pos: dict[str, dict] = {}

    for level, tbls in by_level.items():
        y = height / 2 if max_l == 0 else (level / max_l) * (height - 80) + 40
        for i, t in enumerate(tbls):
            x = ((i + 1) / (len(tbls) + 1)) * width
            pos[t] = {'x': x, 'y': y}

    return pos
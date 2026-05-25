"""
sqlfy.core
==========
Schema graph engine — now powered by sqlglot for proper Oracle AST parsing.

Public API is unchanged from step 5/6/7. Only the internals changed:
  - Hand-rolled tokeniser replaced by sqlglot.parse(dialect="oracle")
  - Handles CREATE TABLE, ALTER TABLE ADD/DROP/MODIFY, CREATE INDEX,
    CREATE SEQUENCE, DROP TABLE, COMMENT ON
  - Column constraints extracted from AST nodes, not regex
  - Action tracking: each migration records what changed (CREATE/DROP/MODIFY)
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field
from typing import Optional

import sqlglot
import sqlglot.expressions as exp

# Suppress sqlglot "unsupported syntax" warnings for Command fallbacks
# — we handle them explicitly via regex on the raw SQL
import logging
logging.getLogger("sqlglot").setLevel(logging.CRITICAL)


# ─────────────────────────────────────────────
# DATA TYPES  (unchanged public shape)
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
class MigrationAction:
    """Records what a single migration statement did — used in history/diff."""
    action: str           # CREATE | DROP | ADD_COLUMN | DROP_COLUMN | MODIFY_COLUMN
                          # ADD_CONSTRAINT | DROP_CONSTRAINT | CREATE_INDEX | CREATE_SEQUENCE
    object_type: str      # TABLE | COLUMN | CONSTRAINT | INDEX | SEQUENCE
    object_name: str      # fully-qualified name of the affected object
    version: str


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
    actions: list[MigrationAction] = field(default_factory=list)


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
    actions: list[MigrationAction] = field(default_factory=list)  # all actions across all migrations


@dataclass
class VectorChunk:
    id: str
    type: str
    title: str
    content: str
    meta: dict
    hint: str



# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _table_full(node: exp.Table) -> str:
    """'app.users' from a sqlglot Table expression."""
    db   = node.args.get('db')
    name = node.name.upper()
    if db:
        return f'{db.name.upper()}.{name}'
    return name


def _table_schema_name(node: exp.Table) -> tuple[Optional[str], str]:
    db = node.args.get('db')
    return (db.name.upper() if db else None), node.name.upper()


def _col_datatype(kind: Optional[exp.DataType]) -> tuple[str, Optional[int], Optional[int]]:
    """Extract (type_str, precision, scale) from a sqlglot DataType node."""
    if kind is None:
        return 'UNKNOWN', None, None
    type_name = kind.this.name if kind.this else str(kind)
    exprs = kind.expressions
    precision = int(exprs[0].name) if len(exprs) > 0 and exprs[0].name.isdigit() else None
    scale     = int(exprs[1].name) if len(exprs) > 1 and exprs[1].name.isdigit() else None

    # Normalise sqlglot type names back to Oracle-style display names
    _aliases = {
        'DECIMAL': 'NUMBER',
        'FLOAT':   'FLOAT',
        'TEXT':    'CLOB',
        'TINYTEXT':'CLOB',
    }
    type_name = _aliases.get(type_name.upper(), type_name.upper())
    return type_name, precision, scale


def _on_delete_from_options(options: list) -> Optional[str]:
    """Extract ON DELETE action string from a list of option expressions."""
    joined = ' '.join(str(o) for o in options).upper()
    m = re.search(r'ON DELETE (CASCADE|SET NULL|SET DEFAULT|RESTRICT|NO ACTION)', joined)
    if m:
        return m.group(1).replace(' ', '_')
    return None


def type_str(col: Column) -> str:
    """Render column data type back to a display string."""
    if col.precision is not None and col.scale is not None:
        return f'{col.type}({col.precision},{col.scale})'
    if col.precision is not None:
        return f'{col.type}({col.precision})'
    return col.type


# ─────────────────────────────────────────────
# COLUMN PARSER  (from sqlglot ColumnDef AST node)
# ─────────────────────────────────────────────

def _parse_column_def(col_node: exp.ColumnDef) -> Column:
    name = col_node.name.upper()
    type_, precision, scale = _col_datatype(col_node.kind)

    nullable    = True
    default_val = None
    primary_key = False
    unique      = False
    references  = None

    for c in col_node.constraints:
        kind = c.kind
        if isinstance(kind, exp.NotNullColumnConstraint):
            nullable = False
        elif isinstance(kind, exp.DefaultColumnConstraint):
            default_val = kind.this.sql(dialect='oracle') if kind.this else None
            # Strip outer quotes from string literals for display
            if default_val and default_val.startswith("'") and default_val.endswith("'"):
                default_val = default_val  # keep as-is
        elif isinstance(kind, exp.PrimaryKeyColumnConstraint):
            primary_key = True
            nullable    = False
        elif isinstance(kind, exp.UniqueColumnConstraint):
            unique = True
        elif isinstance(kind, exp.Reference):
            ref_schema = kind.this  # Schema node
            ref_table  = ref_schema.this if ref_schema else None
            if ref_table:
                ref_full = _table_full(ref_table)
                ref_cols = [e.name.upper() for e in ref_schema.expressions]
                references = {
                    'table':  ref_full,
                    'column': ref_cols[0] if ref_cols else '',
                }

    return Column(
        name=name, type=type_, precision=precision, scale=scale,
        nullable=nullable, default=default_val,
        primary_key=primary_key, unique=unique, references=references,
    )


# ─────────────────────────────────────────────
# TABLE CONSTRAINT PARSER  (from sqlglot Constraint AST node)
# ─────────────────────────────────────────────

def _parse_table_constraint(node: exp.Constraint) -> Optional[Constraint]:
    cname = node.name.upper() if node.name else None

    for expr in node.expressions:
        if isinstance(expr, exp.PrimaryKey):
            cols = [e.name.upper() for e in expr.expressions]
            return Constraint(name=cname, type='primary_key', columns=cols)

        if isinstance(expr, exp.UniqueColumnConstraint):
            schema = expr.this  # Schema node
            cols = [e.name.upper() for e in (schema.expressions if schema else [])]
            return Constraint(name=cname, type='unique', columns=cols)

        if isinstance(expr, exp.ForeignKey):
            from_cols = [e.name.upper() for e in expr.expressions]
            ref       = expr.args.get('reference')
            to_table  = ''
            to_cols: list[str] = []
            on_delete = None
            if ref:
                ref_schema = ref.args.get('this')  # Schema wrapping Table
                if ref_schema:
                    ref_table = ref_schema.this
                    if ref_table:
                        to_table = _table_full(ref_table)
                    to_cols = [e.name.upper() for e in ref_schema.expressions]
                on_delete = _on_delete_from_options(ref.args.get('options', []))
            return Constraint(
                name=cname, type='foreign_key', columns=from_cols,
                references={'table': to_table, 'columns': to_cols, 'on_delete': on_delete},
            )

        if isinstance(expr, exp.CheckColumnConstraint):
            check_sql = expr.this.sql(dialect='oracle') if expr.this else ''
            return Constraint(name=cname, type='check', columns=[], check_expr=check_sql)

    return None


# ─────────────────────────────────────────────
# DDL HANDLERS
# ─────────────────────────────────────────────

def _handle_create_table(
    stmt: exp.Create,
    version: str,
    tables: dict[str, Table],
    all_actions: list[MigrationAction],
) -> None:
    schema_node = stmt.this          # exp.Schema
    table_node  = schema_node.this   # exp.Table
    schema_str, name_str = _table_schema_name(table_node)
    full = f'{schema_str}.{name_str}' if schema_str else name_str

    columns: list[Column]         = []
    constraints: list[Constraint] = []

    for node in schema_node.expressions:
        if isinstance(node, exp.ColumnDef):
            col = _parse_column_def(node)
            if col.primary_key:
                constraints.append(Constraint(
                    name=f'PK_{name_str}', type='primary_key', columns=[col.name]
                ))
            if col.references:
                constraints.append(Constraint(
                    name=None, type='foreign_key', columns=[col.name],
                    references={
                        'table':    col.references['table'],
                        'columns':  [col.references['column']],
                        'on_delete': None,
                    },
                ))
            columns.append(col)

        elif isinstance(node, exp.Constraint):
            c = _parse_table_constraint(node)
            if c:
                constraints.append(c)

    action = MigrationAction(
        action='CREATE', object_type='TABLE', object_name=full, version=version
    )
    all_actions.append(action)

    tables[full] = Table(
        id=full, schema=schema_str, name=name_str, full=full,
        columns=columns, constraints=constraints,
        created_in=version, actions=[action],
    )


def _handle_drop_table(
    stmt: exp.Drop,
    version: str,
    tables: dict[str, Table],
    all_actions: list[MigrationAction],
) -> None:
    table_node = stmt.this
    if not isinstance(table_node, exp.Table):
        return
    full = _table_full(table_node)
    action = MigrationAction(
        action='DROP', object_type='TABLE', object_name=full, version=version
    )
    all_actions.append(action)
    tables.pop(full, None)


def _handle_alter_table(
    stmt: exp.Alter,
    version: str,
    tables: dict[str, Table],
    all_actions: list[MigrationAction],
) -> None:
    table_node = stmt.this
    if not isinstance(table_node, exp.Table):
        return
    full  = _table_full(table_node)
    table = tables.get(full)

    def mark_modified() -> None:
        if table and version not in table.modified_in:
            table.modified_in.append(version)

    for action_node in stmt.args.get('actions', []):

        # ── ADD COLUMN(S) or ADD CONSTRAINT ──────────────────────────────
        if isinstance(action_node, exp.Schema):
            # Schema node = ADD (col1 TYPE, col2 TYPE, ...)
            for node in action_node.expressions:
                if isinstance(node, exp.ColumnDef) and table:
                    col = _parse_column_def(node)
                    table.columns.append(col)
                    mark_modified()
                    act = MigrationAction(
                        action='ADD_COLUMN', object_type='COLUMN',
                        object_name=f'{full}.{col.name}', version=version,
                    )
                    all_actions.append(act)
                    table.actions.append(act)

        elif isinstance(action_node, exp.AddConstraint):
            for con_node in action_node.expressions:
                if isinstance(con_node, exp.Constraint) and table:
                    c = _parse_table_constraint(con_node)
                    if c:
                        table.constraints.append(c)
                        mark_modified()
                        act = MigrationAction(
                            action='ADD_CONSTRAINT', object_type='CONSTRAINT',
                            object_name=f'{full}.{c.name or "unnamed"}', version=version,
                        )
                        all_actions.append(act)
                        table.actions.append(act)

        # ── DROP COLUMN ───────────────────────────────────────────────────
        elif isinstance(action_node, exp.Drop):
            if action_node.args.get('kind') == 'COLUMN' and table:
                col_name = action_node.this.name.upper() if action_node.this else ''
                table.columns = [c for c in table.columns if c.name != col_name]
                mark_modified()
                act = MigrationAction(
                    action='DROP_COLUMN', object_type='COLUMN',
                    object_name=f'{full}.{col_name}', version=version,
                )
                all_actions.append(act)
                table.actions.append(act)

            elif action_node.args.get('kind') == 'CONSTRAINT' and table:
                con_name = action_node.this.name.upper() if action_node.this else ''
                table.constraints = [c for c in table.constraints if (c.name or '') != con_name]
                mark_modified()
                act = MigrationAction(
                    action='DROP_CONSTRAINT', object_type='CONSTRAINT',
                    object_name=f'{full}.{con_name}', version=version,
                )
                all_actions.append(act)
                table.actions.append(act)


def _handle_alter_table_command(
    raw_sql: str,
    version: str,
    tables: dict[str, Table],
    all_actions: list[MigrationAction],
) -> None:
    """
    Fallback for ALTER TABLE MODIFY — sqlglot parses this as a Command.
    We extract it via regex on the raw SQL text.
    """
    m = re.match(
        r'^(?:ALTER\s+TABLE)\s+"?(\w+(?:\.\w+)?)"?\s+MODIFY\s*\((.+)\)\s*$',
        raw_sql.strip(), re.I | re.S
    )
    if not m:
        # bare MODIFY without parens
        m = re.match(
            r'^(?:ALTER\s+TABLE)\s+"?(\w+(?:\.\w+)?)"?\s+MODIFY\s+(.+?)\s*$',
            raw_sql.strip(), re.I | re.S
        )
    if not m:
        return

    full  = m.group(1).upper().replace('"', '')
    table = tables.get(full)
    if not table:
        return

    # Split comma-separated column modifications (respecting parens)
    body = m.group(2)
    depth, cur, defs = 0, [], []
    for ch in body:
        if ch == '(':   depth += 1
        elif ch == ')': depth -= 1
        if ch == ',' and depth == 0:
            defs.append(''.join(cur).strip()); cur = []
        else:
            cur.append(ch)
    if cur: defs.append(''.join(cur).strip())

    for defn in defs:
        cm = re.match(r'"?(\w+)"?\s+(\S+(?:\([^)]+\))?)(.*)', defn, re.I | re.S)
        if not cm:
            continue
        col_name = cm.group(1).upper()
        type_raw = cm.group(2).upper()
        rest     = cm.group(3).strip()

        # Find the column and update it
        for col in table.columns:
            if col.name == col_name:
                # Parse new type
                tm = re.match(r'(\w[\w ]*?)(?:\((\d+)(?:,(\d+))?\))?$', type_raw)
                if tm:
                    col.type      = tm.group(1).strip()
                    col.precision = int(tm.group(2)) if tm.group(2) else col.precision
                    col.scale     = int(tm.group(3)) if tm.group(3) else col.scale
                if re.search(r'NOT\s+NULL', rest, re.I):
                    col.nullable = False
                elif re.search(r'\bNULL\b', rest, re.I):
                    col.nullable = True
                dm = re.search(r'DEFAULT\s+(.+?)(?=\s+(?:NOT\s+NULL|NULL)|$)', rest, re.I)
                if dm:
                    col.default = dm.group(1).strip()
                break

        if version not in table.modified_in:
            table.modified_in.append(version)
        act = MigrationAction(
            action='MODIFY_COLUMN', object_type='COLUMN',
            object_name=f'{full}.{col_name}', version=version,
        )
        all_actions.append(act)
        table.actions.append(act)


def _handle_create_index_command(
    raw_sql: str,
    version: str,
    tables: dict[str, Table],
    all_actions: list[MigrationAction],
) -> None:
    """
    sqlglot falls back to Command for CREATE INDEX — handle via regex.
    """
    m = re.match(
        r'^(?:CREATE\s+)?(UNIQUE\s+)?INDEX\s+"?(\w+(?:\.\w+)?)"?\s+ON\s+"?(\w+(?:\.\w+)?)"?\s*\(([^)]+)\)',
        raw_sql.strip(), re.I
    )
    if not m:
        return
    unique   = bool(m.group(1))
    idx_raw  = m.group(2).replace('"', '').upper()
    tbl_raw  = m.group(3).replace('"', '').upper()
    cols_raw = m.group(4)

    idx_name = idx_raw.split('.')[-1]
    cols     = [re.sub(r'\s+(ASC|DESC)$', '', c.strip(), flags=re.I).replace('"', '').upper()
                for c in cols_raw.split(',')]

    table = tables.get(tbl_raw)
    if table:
        table.indexes.append(Index(name=idx_name, columns=cols, unique=unique, created_in=version))
        act = MigrationAction(
            action='CREATE_INDEX', object_type='INDEX',
            object_name=f'{tbl_raw}.{idx_name}', version=version,
        )
        all_actions.append(act)
        table.actions.append(act)


def _handle_create_sequence(
    stmt: exp.Create,
    version: str,
    seqs: dict[str, Sequence],
    all_actions: list[MigrationAction],
) -> None:
    table_node = stmt.this
    schema_str, name_str = _table_schema_name(table_node)
    full = f'{schema_str}.{name_str}' if schema_str else name_str

    start_with   = 1
    increment_by = 1

    props = stmt.args.get('properties')
    if props:
        for p in props.expressions:
            if isinstance(p, exp.SequenceProperties):
                if p.args.get('start'):
                    start_with = int(p.args['start'].name)
                if p.args.get('increment'):
                    increment_by = int(p.args['increment'].name)

    seqs[full] = Sequence(
        name=name_str, schema=schema_str, full=full,
        start_with=start_with, increment_by=increment_by, created_in=version,
    )
    all_actions.append(MigrationAction(
        action='CREATE_SEQUENCE', object_type='SEQUENCE', object_name=full, version=version,
    ))


def _handle_comment(
    stmt: exp.Comment,
    tables: dict[str, Table],
) -> None:
    kind = stmt.args.get('kind', '').upper()
    if kind == 'TABLE':
        table_node = stmt.this
        if isinstance(table_node, exp.Table):
            full = _table_full(table_node)
            t = tables.get(full)
            if t:
                t.comments['__table__'] = stmt.expression.name if stmt.expression else ''
    elif kind == 'COLUMN':
        # COMMENT ON COLUMN schema.table.column IS '...'
        # sqlglot represents this as a Column node with a table reference
        col_node = stmt.this
        if isinstance(col_node, exp.Column):
            col_name   = col_node.name.upper()
            table_node = col_node.args.get('table')
            db_node    = col_node.args.get('db')
            if table_node:
                tname = table_node.name.upper()
                full  = f'{db_node.name.upper()}.{tname}' if db_node else tname
                t = tables.get(full)
                if t:
                    t.comments[col_name] = stmt.expression.name if stmt.expression else ''


# ─────────────────────────────────────────────
# FLYWAY ORCHESTRATOR
# ─────────────────────────────────────────────

def parse_flyway_ver(filename: str) -> dict:
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


def apply_migrations(files: list[dict], dialect: str = 'oracle') -> SchemaGraph:
    """
    Reconstruct the final schema state from a list of { filename, sql } dicts.
    Delegates to Reconstructor — kept for backward compatibility.

    Args:
        files:   list of { filename: str, sql: str }
        dialect: SQL dialect to use (default: 'oracle')

    Returns:
        SchemaGraph with accumulated tables, sequences, FK edges,
        migration history, and full action log.
    """
    # Import here to avoid circular dependency (reconstructor imports from core)
    from .reconstructor import reconstruct
    return reconstruct(files, dialect=dialect)


# ─────────────────────────────────────────────
# LLM VECTOR CHUNK BUILDER  (unchanged)
# ─────────────────────────────────────────────

def build_chunks(graph: SchemaGraph) -> list[VectorChunk]:
    tables   = graph.tables
    seqs     = graph.seqs
    edges    = graph.edges
    mig_hist = graph.mig_hist

    chunks: list[VectorChunk] = []

    def out_e(full): return [e for e in edges if e.from_table == full]
    def in_e(full):  return [e for e in edges if e.to_table   == full]

    for t in tables.values():
        pk    = next((c for c in t.constraints if c.type == 'primary_key'), None)
        fks   = [c for c in t.constraints if c.type == 'foreign_key']
        uqs   = [c for c in t.constraints if c.type == 'unique']
        cks   = [c for c in t.constraints if c.type == 'check']
        out   = out_e(t.full)
        inn   = in_e(t.full)

        L: list[str] = []
        L.append(f'TABLE: {t.full}')
        if t.comments.get('__table__'):
            L.append(f'Description: {t.comments["__table__"]}')
        modified = f' | Modified: V{", V".join(t.modified_in)}' if t.modified_in else ''
        L.append(f'Schema: {t.schema or "default"} | Created: V{t.created_in}{modified}')
        L.append(''); L.append('COLUMNS:')

        for col in t.columns:
            flags: list[str] = []
            if pk and col.name in pk.columns:      flags.append('PK')
            if not col.nullable:                   flags.append('NOT NULL')
            if col.default:                        flags.append(f'DEFAULT {col.default}')
            if any(col.name in u.columns for u in uqs): flags.append('UNIQUE')
            if any(col.name in e.from_cols for e in out): flags.append('FK')
            comment  = t.comments.get(col.name, '')
            flag_str = f' [{", ".join(flags)}]' if flags else ''
            cmt_str  = f' -- {comment}' if comment else ''
            L.append(f'  {col.name}: {type_str(col)}{flag_str}{cmt_str}')

        if out:
            L.append(''); L.append('REFERENCES (outgoing FK):')
            for e in out:
                od = f' ON DELETE {e.on_delete}' if e.on_delete else ''
                cn = f' [{e.constraint_name}]' if e.constraint_name else ''
                L.append(f'  {",".join(e.from_cols)}) → {e.to_table}({",".join(e.to_cols)}){od}{cn}')
        if inn:
            L.append(''); L.append('REFERENCED BY:')
            for e in inn: L.append(f'  {e.from_table}.{",".join(e.from_cols)} → {",".join(e.to_cols)}')
        if t.indexes:
            L.append(''); L.append('INDEXES:')
            for idx in t.indexes:
                L.append(f'  {idx.name}: ({", ".join(idx.columns)}){"  UNIQUE" if idx.unique else ""} [V{idx.created_in}]')
        if cks:
            L.append(''); L.append('CHECK CONSTRAINTS:')
            for ck in cks: L.append(f'  {ck.name or "unnamed"}: CHECK ({ck.check_expr})')

        # Action history for this table
        if t.actions:
            L.append(''); L.append('MIGRATION ACTIONS:')
            for a in t.actions:
                L.append(f'  V{a.version}: {a.action} {a.object_type} {a.object_name}')

        chunks.append(VectorChunk(
            id=f'table:{t.full}', type='table', title=f'Table: {t.name}',
            content='\n'.join(L),
            meta={
                'table_name': t.name, 'schema': t.schema,
                'column_count': len(t.columns), 'has_pk': pk is not None,
                'fk_count': len(fks), 'referenced_by': len(inn),
                'index_count': len(t.indexes), 'created_in': t.created_in,
                'pk_cols': pk.columns if pk else [],
                'actions': [{'action': a.action, 'version': a.version} for a in t.actions],
            },
            hint=f'Use for: queries about {t.name} table — columns, types, constraints, FK relationships.',
        ))

    # Schema summary
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
        '', 'RELATIONSHIP MAP:',
        *[f'  {e.from_table}.{",".join(e.from_cols)} → {e.to_table}.{",".join(e.to_cols)}' for e in edges],
        '', 'TABLE ROLES:',
        *[f'  {t.full}: {"root/parent entity" if len(in_e(t.full))>0 and len(out_e(t.full))==0 else "junction/child entity" if len(out_e(t.full))>0 and len(in_e(t.full))>0 else "leaf/detail entity" if len(out_e(t.full))>0 else "standalone"} (referenced by {len(in_e(t.full))}, references {len(out_e(t.full))})'
         for t in tables.values()],
    ]
    chunks.insert(0, VectorChunk(
        id='schema:summary', type='schema_summary', title='Schema Summary',
        content='\n'.join(sum_l),
        meta={'table_count': len(tables), 'seq_count': len(seqs),
              'edge_count': len(edges), 'column_count': total_cols, 'schemas': schemas},
        hint='Use for: high-level schema questions, table count, migration history, overall topology.',
    ))

    # Relationship graph chunk
    rel_l = ['RELATIONSHIP GRAPH (adjacency list)', '']
    for tname in table_names:
        out = out_e(tname); inn = in_e(tname)
        rel_l.append(f'{tname}:')
        for e in out: rel_l.append(f'  ──FK──▶ {e.to_table} via {",".join(e.from_cols)}{"  [ON DELETE "+e.on_delete+"]" if e.on_delete else ""}')
        for e in inn: rel_l.append(f'  ◀──FK── {e.from_table} via {",".join(e.from_cols)}')
        if not out and not inn: rel_l.append('  (no FK relationships)')
    chunks.append(VectorChunk(
        id='schema:relationships', type='relationship_map', title='Relationship Graph',
        content='\n'.join(rel_l),
        meta={'edges': [{'from': e.from_table, 'to': e.to_table, 'via': e.from_cols, 'on_delete': e.on_delete} for e in edges]},
        hint='Use for: JOIN path planning, cascade analysis, understanding table connectivity.',
    ))

    return chunks


# ─────────────────────────────────────────────
# ERD LAYOUT ENGINE  (unchanged)
# ─────────────────────────────────────────────

def compute_layout(
    tables: dict[str, Table],
    edges:  list[Edge],
    width:  float = 580,
    height: float = 220,
) -> dict[str, dict]:
    levels: dict[str, int] = {k: 0 for k in tables}
    for _ in range(10):
        changed = False
        for e in edges:
            fl = levels.get(e.from_table, 0)
            tl = levels.get(e.to_table,   0)
            if fl <= tl:
                levels[e.from_table] = tl + 1; changed = True
        if not changed: break
    by_level: dict[int, list[str]] = {}
    for t, l in levels.items(): by_level.setdefault(l, []).append(t)
    max_l = max(levels.values(), default=0)
    pos: dict[str, dict] = {}
    for level, tbls in by_level.items():
        y = height / 2 if max_l == 0 else (level / max_l) * (height - 80) + 40
        for i, t in enumerate(tbls):
            pos[t] = {'x': ((i + 1) / (len(tbls) + 1)) * width, 'y': y}
    return pos
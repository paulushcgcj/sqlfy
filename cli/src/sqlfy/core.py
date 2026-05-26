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
from typing import Optional

import networkx as nx
import sqlglot
import sqlglot.expressions as exp

from .domain.models import (
    Column,
    Constraint,
    Index,
    MigrationAction,
    Table,
    Sequence,
    Edge,
    MigrationHistory,
    SchemaGraph,
    VectorChunk,
    GraphNode,
    GraphEdge,
    EdgeRelation,
    Confidence,
)
from .domain.utils import type_str
from .domain.sqlglot_compat import SQLGLOT_HAS_MODIFY, parse_modify_native
from .output.chunker import build_chunks
from .output.layout import compute_layout

# Suppress sqlglot "unsupported syntax" warnings for Command fallbacks
# — we handle them explicitly via regex on the raw SQL
import logging
logging.getLogger("sqlglot").setLevel(logging.CRITICAL)


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
    
    This function is legacy code from before the reconstructor refactoring.
    The preferred path is through reconstructor.py which has the same logic
    with feature detection for native sqlglot MODIFY support.
    
    Kept for backward compatibility in case external code imports this.
    """
    # Use native sqlglot parsing if available
    if SQLGLOT_HAS_MODIFY:
        try:
            table_name, modifications = parse_modify_native(raw_sql, dialect='oracle')
            table = tables.get(table_name)
            if not table:
                return
            
            for mod_info in modifications:
                col_name = mod_info.column_name
                
                for col in table.columns:
                    if col.name != col_name:
                        continue
                    
                    if mod_info.data_type is not None:
                        col.type = mod_info.data_type
                    if mod_info.precision is not None:
                        col.precision = mod_info.precision
                    if mod_info.scale is not None:
                        col.scale = mod_info.scale
                    if mod_info.nullable is not None:
                        col.nullable = mod_info.nullable
                    if mod_info.default is not None:
                        col.default = mod_info.default
                    break
                
                if version not in table.modified_in:
                    table.modified_in.append(version)
                
                act = MigrationAction(
                    action='MODIFY_COLUMN',
                    object_type='COLUMN',
                    object_name=f'{table_name}.{col_name}',
                    version=version,
                )
                all_actions.append(act)
                table.actions.append(act)
            
            return
        except (ValueError, AttributeError):
            # Fall through to regex fallback
            pass
    
    # Regex fallback for older sqlglot versions
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
        # Match: "colname type(precision, scale) rest"
        # Use a greedy pattern that captures the entire type including parens and spaces
        cm = re.match(r'"?(\w+)"?\s+(\w+(?:\s*\([^)]+\))?)(.*)', defn, re.I | re.S)
        if not cm:
            continue
        col_name = cm.group(1).upper()
        type_raw = cm.group(2).upper().strip()  # Strip whitespace from type
        rest     = cm.group(3).strip()

        # Find the column and update it
        for col in table.columns:
            if col.name == col_name:
                # Parse new type - handles spaces in precision/scale: NUMBER(10, 2)
                tm = re.match(r'(\w[\w ]*?)(?:\(\s*(\d+)\s*(?:,\s*(\d+)\s*)?\))?$', type_raw)
                if tm:
                    col.type = tm.group(1).strip()
                    # Update precision and scale based on what's explicitly provided
                    # If precision is present, always update it (don't keep old value)
                    # If scale is present, use it; otherwise reset to None
                    if tm.group(2):  # precision present
                        col.precision = int(tm.group(2))
                        col.scale = int(tm.group(3)) if tm.group(3) else None
                    else:
                        # No precision specified, keep existing (rare case)
                        pass
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
# NETWORKX GRAPH CONSTRUCTION (Feature #1)
# ─────────────────────────────────────────────

def build_networkx_graph(schema_graph: SchemaGraph, directed: bool = False) -> nx.Graph | nx.DiGraph:
    """Convert SchemaGraph to NetworkX format.
    
    Args:
        schema_graph: The schema graph from apply_migrations()
        directed: If True, create a directed graph (default: undirected)
    
    Returns:
        NetworkX graph with nodes for tables/columns/sequences and edges for relationships
    """
    G = nx.DiGraph() if directed else nx.Graph()
    
    # Add table nodes
    for table_id, table in schema_graph.tables.items():
        G.add_node(
            table_id,
            label=table.name,
            type="table",
            created_in=table.created_in,
            modified_in=table.modified_in,
            column_count=len(table.columns),
            schema=table.schema,
        )
        
        # Add column nodes
        for col in table.columns:
            col_id = f"{table_id}.{col.name}"
            G.add_node(
                col_id,
                label=col.name,
                type="column",
                data_type=col.type,
                nullable=col.nullable,
                primary_key=col.primary_key,
                unique=col.unique,
            )
            # Add containment edge: table contains column
            G.add_edge(
                table_id,
                col_id,
                relation="contains",
                confidence="EXTRACTED",
            )
    
    # Add sequence nodes
    for seq_id, seq in schema_graph.seqs.items():
        G.add_node(
            seq_id,
            label=seq.name,
            type="sequence",
            created_in=seq.created_in,
            start_with=seq.start_with,
            increment_by=seq.increment_by,
            schema=seq.schema,
        )
    
    # Add FK edges
    for edge in schema_graph.edges:
        G.add_edge(
            edge.from_table,
            edge.to_table,
            relation="foreign_key",
            confidence="EXTRACTED",
            from_cols=edge.from_cols,
            to_cols=edge.to_cols,
            on_delete=edge.on_delete,
            constraint_name=edge.constraint_name,
        )
    
    # Add migration history nodes
    for mig in schema_graph.mig_hist:
        mig_id = f"migration:{mig.version}"
        G.add_node(
            mig_id,
            label=mig.version,
            type="migration",
            description=mig.description,
        )
    
    # Add migration action edges
    for action in schema_graph.actions:
        mig_id = f"migration:{action.version}"
        
        # Determine relation type from action
        relation: EdgeRelation = "modifies"
        if action.action == "CREATE":
            relation = "creates"
        elif action.action == "DROP":
            relation = "drops"
        
        # Add edge from migration to affected object
        if mig_id in G.nodes and action.object_name in G.nodes:
            G.add_edge(
                mig_id,
                action.object_name,
                relation=relation,
                confidence="EXTRACTED",
                action_type=action.action,
                object_type=action.object_type,
            )
    
    return G
"""
sqlfy.reconstructor
===================
State Reconstructor engine.

Processes Flyway migration files in version order and maintains an
explicit state machine representing the current database schema.

Key capabilities vs. the simple apply_migrations() function:
  - Incremental: apply one file at a time with apply_file()
  - Point-in-time: reconstruct state at any version with apply_up_to()
  - Snapshot: export the current state as a SchemaGraph
  - Full DROP support: DROP TABLE, DROP COLUMN, DROP CONSTRAINT, DROP INDEX
  - MODIFY support: ALTER COLUMN type, nullability, default changes
  - RENAME support: RENAME COLUMN, RENAME TABLE (regex fallback)
  - Per-statement error recovery: one bad statement doesn't kill the run
  - Dialect-aware: defaults to Oracle, swappable for Postgres etc.
"""

from __future__ import annotations

import re
import logging
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Optional

import sqlglot
import sqlglot.expressions as exp

from .domain.models import (
    Column, Constraint, Index, Table, Sequence,
    Edge, MigrationHistory, MigrationAction, SchemaGraph, VectorChunk,
)
from .domain.utils import type_str
from .parsing.ast_helpers import (
    _table_full, _table_schema_name, _col_datatype, _on_delete_from_options,
)
from .parsing.column_parser import _parse_column_def
from .parsing.constraint_parser import _parse_table_constraint
from .migrations.parser import parse_flyway_ver
from .domain.sqlglot_compat import (
    SQLGLOT_HAS_MODIFY,
    SQLGLOT_HAS_RENAME_COLUMN,
    parse_modify_native,
    log_sqlglot_capabilities,
)
from .parsing.extractors import get_extractor
from .semantic.operations import AnyOperation, OperationProvenance

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# RESULT TYPE  — what apply_file() returns
# ─────────────────────────────────────────────

@dataclass
class MigrationResult:
    """Result of applying one migration file."""
    version:  str
    filename: str
    actions:  list[MigrationAction] = field(default_factory=list)
    errors:   list[str]             = field(default_factory=list)
    skipped:  bool                  = False   # True if already applied


# ─────────────────────────────────────────────
# RECONSTRUCTOR
# ─────────────────────────────────────────────

class Reconstructor:
    """
    Stateful migration processor.

    Usage — full batch:
        r = Reconstructor()
        graph = r.apply_all(files)

    Usage — incremental:
        r = Reconstructor()
        for file in sorted_files:
            result = r.apply_file(file['filename'], file['sql'])
            print(result.actions)
        graph = r.snapshot()

    Usage — point-in-time:
        graph_at_v2 = Reconstructor().apply_up_to(files, version='2')
    """

    def __init__(self, dialect: str = 'oracle') -> None:
        self.dialect  = dialect
        self.tables:   dict[str, Table]    = {}
        self.seqs:     dict[str, Sequence] = {}
        self.mig_hist: list[MigrationHistory] = []
        self.actions:  list[MigrationAction]  = []
        self._applied: set[str] = set()   # versions already applied
        self.semantic_ops: list[AnyOperation] = []  # semantic operations (Phase 9)
        
        # Log sqlglot capabilities on first instantiation
        if not hasattr(Reconstructor, '_logged_capabilities'):
            log_sqlglot_capabilities()
            Reconstructor._logged_capabilities = True

    # ── Public API ─────────────────────────────────────────────────────────

    def apply_all(self, files: list[dict]) -> SchemaGraph:
        """Apply all migration files (sorted by Flyway version) and return the final SchemaGraph."""
        sorted_files = sorted(files, key=lambda f: parse_flyway_ver(f['filename'])['order'])
        for f in sorted_files:
            self.apply_file(f['filename'], f['sql'])
        return self.snapshot()

    def apply_up_to(self, files: list[dict], version: str) -> SchemaGraph:
        """Apply migrations up to and including *version*, return that SchemaGraph."""
        sorted_files = sorted(files, key=lambda f: parse_flyway_ver(f['filename'])['order'])
        target_order = parse_flyway_ver(f'V{version}__x.sql')['order']
        for f in sorted_files:
            if parse_flyway_ver(f['filename'])['order'] <= target_order:
                self.apply_file(f['filename'], f['sql'])
        return self.snapshot()

    def apply_file(self, filename: str, sql: str) -> MigrationResult:
        """
        Apply a single migration file.
        Safe to call multiple times — already-applied versions are skipped.
        """
        ver  = parse_flyway_ver(filename)
        vsn  = ver['version']

        if vsn in self._applied:
            return MigrationResult(version=vsn, filename=filename, skipped=True)

        result = MigrationResult(version=vsn, filename=filename)
        self.mig_hist.append(MigrationHistory(version=vsn, description=ver['description']))

        stmts = sqlglot.parse(sql, dialect=self.dialect, error_level=sqlglot.ErrorLevel.WARN)

        for stmt in stmts:
            if stmt is None:
                continue
            if not isinstance(stmt, exp.Expression):
                continue
            try:
                acts = self._dispatch(stmt, vsn)
                result.actions.extend(acts)
                self.actions.extend(acts)
            except Exception as exc:
                msg = f'V{vsn}: error processing statement — {exc}'
                log.warning(msg)
                result.errors.append(msg)

        self._applied.add(vsn)
        return result

    def snapshot(self) -> SchemaGraph:
        """Return an immutable snapshot of the current schema state."""
        edges = self._derive_edges()
        return SchemaGraph(
            tables=deepcopy(self.tables),
            seqs=deepcopy(self.seqs),
            edges=edges,
            mig_hist=list(self.mig_hist),
            actions=list(self.actions),
        )

    def reset(self) -> None:
        """Reset to empty state."""
        self.tables.clear()
        self.seqs.clear()
        self.mig_hist.clear()
        self.actions.clear()
        self.semantic_ops.clear()
        self._applied.clear()

    # ── Statement dispatcher ────────────────────────────────────────────────

    def _dispatch(self, stmt: exp.Expression, version: str) -> list[MigrationAction]:
        """Route a parsed statement to the appropriate handler."""
        acts: list[MigrationAction] = []

        # ── Semantic operation extraction (additive, non-breaking) ──────────
        extractor = get_extractor(stmt)
        if extractor:
            prov = OperationProvenance.of(
                source_file=version, version=version, statement_index=0,
                raw_sql=stmt.sql(dialect=self.dialect),
            )
            try:
                self.semantic_ops.extend(extractor.extract(stmt, prov))
            except Exception as _exc:
                log.debug("Extractor failed for %s: %s", type(stmt).__name__, _exc)
        # ────────────────────────────────────────────────────────────────────

        if isinstance(stmt, exp.Create):
            kind = stmt.args.get('kind', '')
            if kind == 'TABLE':
                acts += self._create_table(stmt, version)
            elif kind == 'SEQUENCE':
                acts += self._create_sequence(stmt, version)
            elif kind == 'INDEX':
                acts += self._create_index_ast(stmt, version)

        elif isinstance(stmt, exp.Drop):
            kind = stmt.args.get('kind', '')
            if kind == 'TABLE':
                acts += self._drop_table(stmt, version)
            elif kind == 'INDEX':
                acts += self._drop_index(stmt, version)
            elif kind == 'SEQUENCE':
                acts += self._drop_sequence(stmt, version)

        elif isinstance(stmt, exp.Alter):
            if stmt.args.get('kind') == 'TABLE':
                acts += self._alter_table(stmt, version)

        elif isinstance(stmt, exp.Comment):
            self._apply_comment(stmt)

        elif isinstance(stmt, exp.Command):
            acts += self._command_fallback(stmt, version)

        return acts

    # ── CREATE TABLE ────────────────────────────────────────────────────────

    def _create_table(self, stmt: exp.Create, version: str) -> list[MigrationAction]:
        schema_node = stmt.this
        table_node  = schema_node.this
        schema_str, name_str = _table_schema_name(table_node)
        full = f'{schema_str}.{name_str}' if schema_str else name_str

        # Honour OR REPLACE / IF NOT EXISTS
        if stmt.args.get('exists') and full in self.tables:
            return []

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

        act = MigrationAction(action='CREATE', object_type='TABLE', object_name=full, version=version)
        self.tables[full] = Table(
            id=full, schema=schema_str, name=name_str, full=full,
            columns=columns, constraints=constraints,
            created_in=version, actions=[act],
        )
        return [act]

    # ── DROP TABLE ──────────────────────────────────────────────────────────

    def _drop_table(self, stmt: exp.Drop, version: str) -> list[MigrationAction]:
        if not isinstance(stmt.this, exp.Table):
            return []
        full = _table_full(stmt.this)

        # IF EXISTS — no error if missing
        if stmt.args.get('exists') and full not in self.tables:
            return []

        act = MigrationAction(action='DROP', object_type='TABLE', object_name=full, version=version)
        self.tables.pop(full, None)
        return [act]

    # ── CREATE SEQUENCE ─────────────────────────────────────────────────────

    def _create_sequence(self, stmt: exp.Create, version: str) -> list[MigrationAction]:
        table_node = stmt.this
        schema_str, name_str = _table_schema_name(table_node)
        full = f'{schema_str}.{name_str}' if schema_str else name_str

        start_with = increment_by = 1
        props = stmt.args.get('properties')
        if props:
            for p in props.expressions:
                if isinstance(p, exp.SequenceProperties):
                    if p.args.get('start'):
                        start_with   = int(p.args['start'].name)
                    if p.args.get('increment'):
                        increment_by = int(p.args['increment'].name)

        self.seqs[full] = Sequence(
            name=name_str, schema=schema_str, full=full,
            start_with=start_with, increment_by=increment_by, created_in=version,
        )
        return [MigrationAction(action='CREATE_SEQUENCE', object_type='SEQUENCE', object_name=full, version=version)]

    # ── DROP SEQUENCE ───────────────────────────────────────────────────────

    def _drop_sequence(self, stmt: exp.Drop, version: str) -> list[MigrationAction]:
        name_node = stmt.this
        full = _table_full(name_node) if isinstance(name_node, exp.Table) else str(name_node).upper()
        self.seqs.pop(full, None)
        return [MigrationAction(action='DROP_SEQUENCE', object_type='SEQUENCE', object_name=full, version=version)]

    # ── CREATE INDEX (AST path) ─────────────────────────────────────────────

    def _create_index_ast(self, stmt: exp.Create, version: str) -> list[MigrationAction]:
        """Handles the (rare) case where sqlglot successfully parses CREATE INDEX."""
        idx_node = stmt.this
        if not isinstance(idx_node, (exp.Index,)):
            return []
        tbl_node = idx_node.args.get('table')
        if not tbl_node:
            return []
        full     = _table_full(tbl_node)
        idx_name = idx_node.name.upper() if idx_node.name else 'UNNAMED_IDX'
        cols     = [e.name.upper() for e in (idx_node.args.get('expressions') or [])]
        unique   = bool(stmt.args.get('unique'))
        table    = self.tables.get(full)
        if table:
            table.indexes.append(Index(name=idx_name, columns=cols, unique=unique, created_in=version))
        act = MigrationAction(action='CREATE_INDEX', object_type='INDEX', object_name=f'{full}.{idx_name}', version=version)
        return [act]

    # ── DROP INDEX ──────────────────────────────────────────────────────────

    def _drop_index(self, stmt: exp.Drop, version: str) -> list[MigrationAction]:
        idx_name = stmt.this.name.upper() if stmt.this else ''
        # Remove the index from whichever table owns it
        for t in self.tables.values():
            t.indexes = [i for i in t.indexes if i.name != idx_name]
        return [MigrationAction(action='DROP_INDEX', object_type='INDEX', object_name=idx_name, version=version)]

    # ── ALTER TABLE ─────────────────────────────────────────────────────────

    def _alter_table(self, stmt: exp.Alter, version: str) -> list[MigrationAction]:
        table_node = stmt.this
        if not isinstance(table_node, exp.Table):
            return []
        full  = _table_full(table_node)
        table = self.tables.get(full)
        acts: list[MigrationAction] = []

        def mark() -> None:
            if table and version not in table.modified_in:
                table.modified_in.append(version)

        for action_node in stmt.args.get('actions', []):

            # ADD COLUMN(S) - handle both Schema-wrapped and direct ColumnDef
            if isinstance(action_node, exp.ColumnDef) and table:
                # Direct ColumnDef (common in ALTER TABLE ADD COLUMN)
                col = _parse_column_def(action_node)
                if not any(c.name == col.name for c in table.columns):
                    table.columns.append(col)
                mark()
                act = MigrationAction(action='ADD_COLUMN', object_type='COLUMN',
                                      object_name=f'{full}.{col.name}', version=version)
                acts.append(act); table.actions.append(act)
            
            elif isinstance(action_node, exp.Schema):
                # Schema-wrapped ColumnDef(s)
                for node in action_node.expressions:
                    if isinstance(node, exp.ColumnDef) and table:
                        col = _parse_column_def(node)
                        # Only add if not already present
                        if not any(c.name == col.name for c in table.columns):
                            table.columns.append(col)
                        mark()
                        act = MigrationAction(action='ADD_COLUMN', object_type='COLUMN',
                                              object_name=f'{full}.{col.name}', version=version)
                        acts.append(act); table.actions.append(act)

            # ADD CONSTRAINT
            elif isinstance(action_node, exp.AddConstraint):
                for con_node in action_node.expressions:
                    if isinstance(con_node, exp.Constraint) and table:
                        c = _parse_table_constraint(con_node)
                        if c:
                            table.constraints.append(c)
                            mark()
                            act = MigrationAction(action='ADD_CONSTRAINT', object_type='CONSTRAINT',
                                                  object_name=f'{full}.{c.name or "unnamed"}', version=version)
                            acts.append(act); table.actions.append(act)

            # DROP COLUMN / CONSTRAINT / INDEX
            elif isinstance(action_node, exp.Drop):
                drop_kind = action_node.args.get('kind', '')
                obj_name  = action_node.this.name.upper() if action_node.this else ''

                if drop_kind == 'COLUMN' and table:
                    table.columns = [c for c in table.columns if c.name != obj_name]
                    mark()
                    act = MigrationAction(action='DROP_COLUMN', object_type='COLUMN',
                                          object_name=f'{full}.{obj_name}', version=version)
                    acts.append(act); table.actions.append(act)

                elif drop_kind == 'CONSTRAINT' and table:
                    table.constraints = [c for c in table.constraints if (c.name or '') != obj_name]
                    mark()
                    act = MigrationAction(action='DROP_CONSTRAINT', object_type='CONSTRAINT',
                                          object_name=f'{full}.{obj_name}', version=version)
                    acts.append(act); table.actions.append(act)

                elif drop_kind == 'INDEX' and table:
                    table.indexes = [i for i in table.indexes if i.name != obj_name]
                    act = MigrationAction(action='DROP_INDEX', object_type='INDEX',
                                          object_name=f'{full}.{obj_name}', version=version)
                    acts.append(act)

            # RENAME COLUMN
            elif isinstance(action_node, exp.RenameColumn):
                old_col = action_node.this
                new_col = action_node.args.get('to')
                if old_col and new_col and table:
                    old_name = old_col.name.upper()
                    new_name = new_col.name.upper()
                    for col in table.columns:
                        if col.name == old_name:
                            col.name = new_name
                            break
                    for con in table.constraints:
                        con.columns = [new_name if c == old_name else c for c in con.columns]
                    mark()
                    act = MigrationAction(action='RENAME_COLUMN', object_type='COLUMN',
                                          object_name=f'{full}.{old_name} → {new_name}', version=version)
                    acts.append(act)
                    if table: table.actions.append(act)

            # RENAME TABLE (fallback for dialects that parse it this way)
            elif hasattr(exp, 'RenameTable') and isinstance(action_node, getattr(exp, 'RenameTable')):
                new_node = action_node.this
                if isinstance(new_node, exp.Table) and table:
                    new_schema, new_name = _table_schema_name(new_node)
                    new_full = f'{new_schema}.{new_name}' if new_schema else new_name
                    table.name  = new_name
                    table.full  = new_full
                    table.id    = new_full
                    self.tables[new_full] = self.tables.pop(full)
                    act = MigrationAction(action='RENAME_TABLE', object_type='TABLE',
                                          object_name=f'{full} → {new_full}', version=version)
                    acts.append(act)

        return acts

    # ── COMMENT ON ──────────────────────────────────────────────────────────

    def _apply_comment(self, stmt: exp.Comment) -> None:
        kind = stmt.args.get('kind', '').upper()
        text = stmt.expression.name if stmt.expression else ''

        if kind == 'TABLE':
            node = stmt.this
            if isinstance(node, exp.Table):
                t = self.tables.get(_table_full(node))
                if t:
                    t.comments['__table__'] = text

        elif kind == 'COLUMN':
            node = stmt.this
            if isinstance(node, exp.Column):
                col_name   = node.name.upper()
                table_node = node.args.get('table')
                db_node    = node.args.get('db')
                if table_node:
                    tname = table_node.name.upper()
                    full  = f'{db_node.name.upper()}.{tname}' if db_node else tname
                    t = self.tables.get(full)
                    if t:
                        t.comments[col_name] = text

    # ── COMMAND FALLBACK ────────────────────────────────────────────────────

    def _command_fallback(self, stmt: exp.Command, version: str) -> list[MigrationAction]:
        """
        Handle statements sqlglot cannot fully parse — CREATE INDEX, ALTER MODIFY,
        RENAME COLUMN etc. — via targeted regex on the raw SQL text.

        sqlglot Command gives us:
          stmt.this       = verb  e.g. 'ALTER' | 'CREATE'
          stmt.expression = rest  e.g. ' TABLE app.t MODIFY (col VARCHAR2(100))'
        """
        cmd_name = (stmt.this or '').strip().upper()
        raw_expr = (stmt.expression or '').strip()
        expr_up  = raw_expr.upper()
        acts: list[MigrationAction] = []

        # CREATE [UNIQUE] INDEX
        if cmd_name == 'CREATE' and re.match(r'^(?:UNIQUE\s+)?INDEX\b', expr_up):
            acts += self._create_index_regex(f'CREATE {raw_expr}', version)

        # ALTER TABLE ... MODIFY (col TYPE ...)
        elif cmd_name == 'ALTER' and expr_up.startswith('TABLE') and 'MODIFY' in expr_up:
            if SQLGLOT_HAS_MODIFY:
                acts += self._alter_modify_native(f'ALTER {raw_expr}', version)
            else:
                acts += self._alter_modify_regex(f'ALTER {raw_expr}', version)

        # ALTER TABLE ... RENAME COLUMN old TO new
        elif cmd_name == 'ALTER' and expr_up.startswith('TABLE') and 'RENAME' in expr_up and 'COLUMN' in expr_up:
            acts += self._alter_rename_column_regex(f'ALTER {raw_expr}', version)

        return acts

    # ── Regex fallback helpers ──────────────────────────────────────────────

    def _create_index_regex(self, raw_sql: str, version: str) -> list[MigrationAction]:
        m = re.match(
            r'^CREATE\s+(UNIQUE\s+)?INDEX\s+"?(\w+(?:\.\w+)?)"?\s+ON\s+"?(\w+(?:\.\w+)?)"?\s*\(([^)]+)\)',
            raw_sql.strip(), re.I
        )
        if not m:
            return []
        unique   = bool(m.group(1))
        idx_name = m.group(2).replace('"', '').upper().split('.')[-1]
        tbl_full = m.group(3).replace('"', '').upper()
        cols     = [re.sub(r'\s+(ASC|DESC)$', '', c.strip(), flags=re.I).replace('"', '').upper()
                    for c in m.group(4).split(',')]
        table = self.tables.get(tbl_full)
        if table:
            if not any(i.name == idx_name for i in table.indexes):
                table.indexes.append(Index(name=idx_name, columns=cols, unique=unique, created_in=version))
            if version not in table.modified_in:
                table.modified_in.append(version)
        return [MigrationAction(action='CREATE_INDEX', object_type='INDEX',
                                object_name=f'{tbl_full}.{idx_name}', version=version)]

    def _alter_modify_regex(self, raw_sql: str, version: str) -> list[MigrationAction]:
        m = re.match(
            r'^ALTER\s+TABLE\s+"?(\w+(?:\.\w+)?)"?\s+MODIFY\s*(?:\((.+)\)|(.+))\s*$',
            raw_sql.strip(), re.I | re.S
        )
        if not m:
            return []
        full  = m.group(1).replace('"', '').upper()
        body  = (m.group(2) or m.group(3) or '').strip()
        table = self.tables.get(full)
        if not table:
            return []

        acts: list[MigrationAction] = []
        # Split on comma (respecting parens)
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

            for col in table.columns:
                if col.name != col_name:
                    continue
                # Match type with optional precision and scale (handles spaces: NUMBER(10, 2))
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
            act = MigrationAction(action='MODIFY_COLUMN', object_type='COLUMN',
                                  object_name=f'{full}.{col_name}', version=version)
            acts.append(act)
            table.actions.append(act)

        return acts
    # ── Native sqlglot MODIFY parser ────────────────────────────────────────

    def _alter_modify_native(self, raw_sql: str, version: str) -> list[MigrationAction]:
        """
        Parse ALTER TABLE MODIFY using native sqlglot AST (when supported).
        
        This is faster and more robust than regex parsing, but only works
        with sqlglot versions that fully support Oracle MODIFY syntax.
        As of sqlglot 30.8.0, MODIFY is still parsed as Command, so this
        path is not yet active.
        """
        try:
            table_name, modifications = parse_modify_native(raw_sql, dialect=self.dialect)
        except (ValueError, AttributeError) as e:
            log.warning(f"Native MODIFY parse failed: {e} — falling back to regex")
            return self._alter_modify_regex(raw_sql, version)
        
        table = self.tables.get(table_name)
        if not table:
            log.warning(f"Table {table_name} not found for MODIFY statement")
            return []
        
        acts: list[MigrationAction] = []
        
        for mod_info in modifications:
            col_name = mod_info.column_name
            
            # Find the column in the table
            for col in table.columns:
                if col.name != col_name:
                    continue
                
                # Update column properties
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
            
            # Track modification
            if version not in table.modified_in:
                table.modified_in.append(version)
            
            act = MigrationAction(
                action='MODIFY_COLUMN',
                object_type='COLUMN',
                object_name=f'{table_name}.{col_name}',
                version=version
            )
            acts.append(act)
            table.actions.append(act)
        
        return acts

    # ── Regex fallback MODIFY parser ────────────────────────────────────────
    def _alter_rename_column_regex(self, raw_sql: str, version: str) -> list[MigrationAction]:
        m = re.match(
            r'^ALTER\s+TABLE\s+"?(\w+(?:\.\w+)?)"?\s+RENAME\s+COLUMN\s+"?(\w+)"?\s+TO\s+"?(\w+)"?',
            raw_sql.strip(), re.I
        )
        if not m:
            return []
        full     = m.group(1).replace('"', '').upper()
        old_name = m.group(2).upper()
        new_name = m.group(3).upper()
        table    = self.tables.get(full)
        if not table:
            return []
        for col in table.columns:
            if col.name == old_name:
                col.name = new_name
                break
        # Also update any constraint column references
        for con in table.constraints:
            con.columns = [new_name if c == old_name else c for c in con.columns]
        if version not in table.modified_in:
            table.modified_in.append(version)
        act = MigrationAction(action='RENAME_COLUMN', object_type='COLUMN',
                              object_name=f'{full}.{old_name} → {new_name}', version=version)
        table.actions.append(act)
        return [act]

    # ── Edge derivation ─────────────────────────────────────────────────────

    def _derive_edges(self) -> list[Edge]:
        edges: list[Edge] = []
        seen: set[str] = set()
        for t in self.tables.values():
            for c in t.constraints:
                if c.type == 'foreign_key' and c.references:
                    eid = f'{t.full}→{c.references["table"]}:{c.name}'
                    if eid not in seen:
                        seen.add(eid)
                        edges.append(Edge(
                            id=eid,
                            from_table=t.full,
                            from_cols=c.columns,
                            to_table=c.references['table'],
                            to_cols=c.references['columns'],
                            constraint_name=c.name,
                            on_delete=c.references.get('on_delete'),
                        ))
        return edges


# ─────────────────────────────────────────────
# CONVENIENCE FUNCTIONS  (backward-compat wrappers)
# ─────────────────────────────────────────────

def reconstruct(files: list[dict], dialect: str = 'oracle') -> SchemaGraph:
    """
    Reconstruct the final schema state from a list of { filename, sql } dicts.
    Thin wrapper around Reconstructor — preserves the apply_migrations() contract.
    """
    return Reconstructor(dialect=dialect).apply_all(files)


def reconstruct_at(files: list[dict], version: str, dialect: str = 'oracle') -> SchemaGraph:
    """
    Reconstruct the schema state as it was at a specific Flyway version.

    Example:
        graph_v2 = reconstruct_at(files, version='2')
    """
    return Reconstructor(dialect=dialect).apply_up_to(files, version)
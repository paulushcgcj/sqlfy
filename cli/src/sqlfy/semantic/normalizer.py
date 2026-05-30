"""
sqlfy.semantic.normalizer
=========================
Converts raw sqlglot AST statements into typed ``AnyOperation`` instances.

The normalizer is the bridge between the low-level AST parsing layer
(``parsing/``) and the semantic operation models (``semantic/operations.py``).

Usage::

    from sqlfy.semantic.normalizer import Normalizer

    n = Normalizer(dialect="oracle")
    ops = n.normalize_file(sql_text, source_file="V1__init.sql", version="1")
    for op in ops:
        print(op.operation, op.provenance.source_file)
"""

from __future__ import annotations

import re
import logging
from typing import Iterator

import sqlglot
import sqlglot.expressions as exp

from ..parsing.ast_helpers import _table_full, _table_schema_name, _col_datatype, _on_delete_from_options
from ..parsing.column_parser import _parse_column_def
from ..parsing.constraint_parser import _parse_table_constraint
from .operations import (
    AnyOperation,
    OperationProvenance,
    ColumnDefinition,
    ConstraintDefinition,
    CreateTableOperation,
    DropTableOperation,
    AddColumnOperation,
    DropColumnOperation,
    ModifyColumnOperation,
    RenameColumnOperation,
    AddConstraintOperation,
    DropConstraintOperation,
    CreateIndexOperation,
    DropIndexOperation,
    CreateSequenceOperation,
    ColumnChanges,
    CommentOperation,
    UnknownOperation,
)
from ..domain.sqlglot_compat import SQLGLOT_HAS_MODIFY, SQLGLOT_HAS_RENAME_COLUMN, parse_modify_native

log = logging.getLogger(__name__)


def _to_col_def(col: object) -> ColumnDefinition:
    """Convert internal Column dataclass → ColumnDefinition."""
    parsed = _parse_column_def(col) if not hasattr(col, "name") else col  # type: ignore[arg-type]
    return ColumnDefinition(
        name=getattr(parsed, "name", ""),
        type=getattr(parsed, "type", ""),
        nullable=getattr(parsed, "nullable", True),
        default=getattr(parsed, "default", None),
        primary_key=getattr(parsed, "primary_key", False),
        unique=getattr(parsed, "unique", False),
        references=None,
    )


def _to_constraint_def(c: "object") -> ConstraintDefinition:
    """Convert internal Constraint dataclass → ConstraintDefinition."""
    return ConstraintDefinition(
        name=getattr(c, "name", None),
        type=getattr(c, "type", ""),
        columns=getattr(c, "columns", []),
        ref_table=getattr(c, "ref_table", None),
        ref_columns=getattr(c, "ref_columns", []) or [],
        on_delete=getattr(c, "on_delete", None),
        check_expr=getattr(c, "check_expr", None),
    )


class Normalizer:
    """Converts SQL text → list of typed semantic operations."""

    def __init__(self, dialect: str = "oracle") -> None:
        self.dialect = dialect

    def normalize_file(
        self,
        sql: str,
        source_file: str,
        version: str,
    ) -> list[AnyOperation]:
        """Parse all statements in *sql* and return semantic operations."""
        try:
            statements = sqlglot.parse(sql, dialect=self.dialect, error_level=sqlglot.ErrorLevel.WARN)
        except Exception as e:
            log.debug("sqlglot parse error in %s: %s", source_file, e)
            statements = []
        results: list[AnyOperation] = []
        for idx, stmt in enumerate(statements or []):
            if stmt is None:
                continue
            prov = OperationProvenance.of(
                source_file=source_file,
                version=version,
                statement_index=idx,
                raw_sql=stmt.sql(dialect=self.dialect) if stmt else None,
            )
            results.extend(self._extract(stmt, prov))  # type: ignore[arg-type]
        return results

    def _extract(self, stmt: exp.Expression, prov: OperationProvenance) -> list[AnyOperation]:
        if isinstance(stmt, exp.Create):
            return self._handle_create(stmt, prov)
        if isinstance(stmt, exp.Drop):
            return self._handle_drop(stmt, prov)
        if isinstance(stmt, exp.Alter):
            return self._handle_alter(stmt, prov)
        if isinstance(stmt, exp.Command):
            return self._handle_command(stmt, prov)
        return []

    # ── CREATE ──────────────────────────────────────────────

    def _handle_create(self, stmt: exp.Create, prov: OperationProvenance) -> list[AnyOperation]:
        kind = stmt.args.get("kind", "").upper()
        if kind == "TABLE" and isinstance(stmt.this, exp.Schema):
            return [self._create_table(stmt, prov)]
        if kind in ("INDEX", "UNIQUE INDEX"):
            return [self._create_index(stmt, prov)]
        if kind == "SEQUENCE":
            return [self._create_sequence(stmt, prov)]
        return []

    def _create_table(self, stmt: exp.Create, prov: OperationProvenance) -> CreateTableOperation:
        table_node = stmt.this.this
        table_name = _table_full(table_node)
        schema, _ = _table_schema_name(table_node)
        columns: list[ColumnDefinition] = []
        constraints: list[ConstraintDefinition] = []
        for item in stmt.this.expressions:
            if isinstance(item, exp.ColumnDef):
                col = _parse_column_def(item)
                columns.append(ColumnDefinition(
                    name=col.name, type=col.type, nullable=col.nullable,
                    default=col.default, primary_key=col.primary_key, unique=col.unique,
                    references=None,
                ))
            elif isinstance(item, exp.Constraint):
                c = _parse_table_constraint(item)
                if c:
                    constraints.append(_to_constraint_def(c))
        return CreateTableOperation(provenance=prov, table=table_name, schema_=schema,
                                     columns=columns, constraints=constraints)

    def _create_index(self, stmt: exp.Create, prov: OperationProvenance) -> CreateIndexOperation:
        this = stmt.this
        index_name = this.name if hasattr(this, "name") else str(this)
        table_name = ""
        cols: list[str] = []
        if hasattr(stmt, "args"):
            table_arg = stmt.args.get("this")
            if table_arg is not None and hasattr(table_arg, "args") and "table" in table_arg.args:
                table_name = _table_full(table_arg.args["table"])
            for col_node in (stmt.find_all(exp.Column)):
                cols.append(col_node.name)
        return CreateIndexOperation(provenance=prov, table=table_name,
                                     index_name=index_name, columns=cols,
                                     unique="UNIQUE" in str(stmt).upper()[:20])

    def _create_sequence(self, stmt: exp.Create, prov: OperationProvenance) -> CreateSequenceOperation:
        this = stmt.this
        seq_name = _table_full(this) if hasattr(this, "name") else str(this)
        schema, _ = _table_schema_name(this) if hasattr(this, "args") else (None, seq_name)
        return CreateSequenceOperation(provenance=prov, sequence=seq_name, schema_=schema,
                                       start_with=1, increment_by=1)

    # ── DROP ────────────────────────────────────────────────

    def _handle_drop(self, stmt: exp.Drop, prov: OperationProvenance) -> list[AnyOperation]:
        kind = stmt.args.get("kind", "").upper()
        this = stmt.this
        if kind == "TABLE":
            return [DropTableOperation(provenance=prov, table=_table_full(this),
                                        if_exists=bool(stmt.args.get("exists")))]
        if kind == "INDEX":
            name = this.name if hasattr(this, "name") else str(this)
            return [DropIndexOperation(provenance=prov, index_name=name)]
        if kind == "SEQUENCE":
            return []  # No DropSequenceOperation for now
        return []

    # ── ALTER ───────────────────────────────────────────────

    def _handle_alter(self, stmt: exp.Alter, prov: OperationProvenance) -> list[AnyOperation]:
        table_name = _table_full(stmt.this)
        ops: list[AnyOperation] = []
        for action in stmt.args.get("actions", []):
            op = self._handle_alter_action(table_name, action, prov)
            if op:
                ops.append(op)
        return ops

    def _handle_alter_action(
        self, table: str, action: exp.Expression, prov: OperationProvenance
    ) -> AnyOperation | None:
        if isinstance(action, exp.Add):
            for item in action.expressions if hasattr(action, "expressions") else [action.this]:
                if isinstance(item, exp.ColumnDef):
                    col = _parse_column_def(item)
                    return AddColumnOperation(provenance=prov, table=table,
                                               column=ColumnDefinition(
                                                   name=col.name, type=col.type,
                                                   nullable=col.nullable, default=col.default,
                                                   primary_key=col.primary_key, unique=col.unique,
                                                   references=None,
                                               ))
                if isinstance(item, exp.Constraint):
                    c = _parse_table_constraint(item)
                    if c:
                        return AddConstraintOperation(provenance=prov, table=table,
                                                       constraint=_to_constraint_def(c))
        if isinstance(action, exp.Drop):
            kind = action.args.get("kind", "").upper()
            this = action.this
            if kind == "COLUMN":
                col_name = this.name if hasattr(this, "name") else str(this)
                return DropColumnOperation(provenance=prov, table=table, column=col_name)
            if kind in ("CONSTRAINT", "PRIMARY KEY", "UNIQUE"):
                cname = this.name if hasattr(this, "name") else str(this)
                return DropConstraintOperation(provenance=prov, table=table,
                                                constraint_name=cname, constraint_type=kind)
        if SQLGLOT_HAS_RENAME_COLUMN and isinstance(action, exp.RenameColumn):
            return RenameColumnOperation(
                provenance=prov, table=table,
                from_name=action.this.name,
                to_name=action.args["to"].name,
            )
        # MODIFY column (dialect-specific)
        if SQLGLOT_HAS_MODIFY:
            try:
                _table_name, modifications = parse_modify_native(str(action))
                if modifications:
                    mod = modifications[0]
                    return ModifyColumnOperation(
                        provenance=prov, table=table,
                        column=mod.column_name,
                        changes=ColumnChanges(type=mod.data_type, nullable=mod.nullable, default=mod.default),
                    )
            except Exception:
                pass
        return None

    # ── COMMAND (regex fallback) ─────────────────────────────

    def _handle_command(self, stmt: exp.Command, prov: OperationProvenance) -> list[AnyOperation]:
        sql = str(stmt)
        # COMMENT ON TABLE / COLUMN
        m = re.match(
            r"COMMENT\s+ON\s+(TABLE|COLUMN)\s+(\S+)\s+IS\s+'(.*)'",
            sql, re.I | re.S,
        )
        if m:
            return [CommentOperation(provenance=prov, target=m.group(2), comment=m.group(3))]
        # CREATE INDEX fallback
        m = re.match(
            r"CREATE\s+(UNIQUE\s+)?INDEX\s+(\S+)\s+ON\s+(\S+)\s*\(([^)]+)\)",
            sql, re.I,
        )
        if m:
            return [CreateIndexOperation(
                provenance=prov, table=m.group(3),
                index_name=m.group(2),
                columns=[c.strip() for c in m.group(4).split(",")],
                unique=bool(m.group(1)),
            )]
        return []

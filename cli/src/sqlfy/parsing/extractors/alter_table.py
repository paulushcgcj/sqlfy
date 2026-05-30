"""
sqlfy.parsing.extractors.alter_table
======================================
Extractor for ALTER TABLE statements.
"""
from __future__ import annotations
import sqlglot.expressions as exp
from ...semantic.operations import (
    AnyOperation, OperationProvenance, ColumnDefinition, ConstraintDefinition,
    ColumnChanges,
    AddColumnOperation, DropColumnOperation, ModifyColumnOperation,
    RenameColumnOperation, AddConstraintOperation, DropConstraintOperation,
)
from ...parsing.ast_helpers import _table_full
from ...parsing.column_parser import _parse_column_def
from ...parsing.constraint_parser import _parse_table_constraint
from ...domain.sqlglot_compat import SQLGLOT_HAS_MODIFY, SQLGLOT_HAS_RENAME_COLUMN, parse_modify_native
from .base import BaseExtractor


class AlterTableExtractor(BaseExtractor):
    """Handles ``ALTER TABLE`` statements."""

    def can_handle(self, stmt: exp.Expression) -> bool:
        return isinstance(stmt, exp.Alter) and str(stmt.args.get("kind", "")).upper() == "TABLE"

    def extract(self, stmt: exp.Expression, provenance: OperationProvenance) -> list[AnyOperation]:
        assert isinstance(stmt, exp.Alter)
        table_name = _table_full(stmt.this)
        ops: list[AnyOperation] = []
        for action in stmt.args.get("actions", []):
            op = self._handle_action(table_name, action, provenance)
            if op:
                ops.append(op)
        return ops

    def _handle_action(
        self, table: str, action: exp.Expression, prov: OperationProvenance
    ) -> AnyOperation | None:
        if isinstance(action, exp.Add):
            items = action.expressions if hasattr(action, "expressions") else [action.this]
            for item in items:
                if isinstance(item, exp.ColumnDef):
                    col = _parse_column_def(item)
                    return AddColumnOperation(
                        provenance=prov, table=table,
                        column=ColumnDefinition(
                            name=col.name, type=col.type,
                            nullable=col.nullable, default=col.default,
                            primary_key=col.primary_key,
                            unique=col.unique,
                            references=None,
                        ),
                    )
                if isinstance(item, exp.Constraint):
                    c = _parse_table_constraint(item)
                    if c:
                        return AddConstraintOperation(
                            provenance=prov, table=table,
                            constraint=ConstraintDefinition(
                                name=getattr(c, "name", None),
                                type=getattr(c, "type", ""),
                                columns=getattr(c, "columns", []),
                                ref_table=getattr(c, "ref_table", None),
                                ref_columns=getattr(c, "ref_columns", []) or [],
                                on_delete=getattr(c, "on_delete", None),
                                check_expr=getattr(c, "check_expr", None),
                            ),
                        )
        if isinstance(action, exp.Drop):
            kind = str(action.args.get("kind", "")).upper()
            this = action.this
            if kind == "COLUMN":
                return DropColumnOperation(
                    provenance=prov, table=table,
                    column=this.name if hasattr(this, "name") else str(this),
                )
            if kind in ("CONSTRAINT", "PRIMARY KEY", "UNIQUE"):
                return DropConstraintOperation(
                    provenance=prov, table=table,
                    constraint_name=this.name if hasattr(this, "name") else str(this),
                    constraint_type=kind,
                )
        if SQLGLOT_HAS_RENAME_COLUMN and isinstance(action, exp.RenameColumn):
            return RenameColumnOperation(
                provenance=prov, table=table,
                from_name=action.this.name,
                to_name=action.args["to"].name,
            )
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

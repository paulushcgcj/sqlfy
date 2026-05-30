"""
sqlfy.parsing.extractors.create_table
=======================================
Extractor for CREATE TABLE statements.
"""
from __future__ import annotations
import sqlglot.expressions as exp
from ...semantic.operations import (
    AnyOperation, OperationProvenance, ColumnDefinition, ConstraintDefinition,
    CreateTableOperation,
)
from ...parsing.ast_helpers import _table_full, _table_schema_name
from ...parsing.column_parser import _parse_column_def
from ...parsing.constraint_parser import _parse_table_constraint
from .base import BaseExtractor


class CreateTableExtractor(BaseExtractor):
    """Handles ``CREATE TABLE`` statements."""

    def can_handle(self, stmt: exp.Expression) -> bool:
        return (
            isinstance(stmt, exp.Create)
            and str(stmt.args.get("kind", "")).upper() == "TABLE"
            and isinstance(stmt.this, exp.Schema)
        )

    def extract(self, stmt: exp.Expression, provenance: OperationProvenance) -> list[AnyOperation]:
        assert isinstance(stmt, exp.Create)
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
                ))
            elif isinstance(item, exp.Constraint):
                c = _parse_table_constraint(item)
                if c:
                    constraints.append(ConstraintDefinition(
                        name=getattr(c, "name", None),
                        type=getattr(c, "type", ""),
                        columns=getattr(c, "columns", []),
                        ref_table=getattr(c, "ref_table", None),
                        ref_columns=getattr(c, "ref_columns", []) or [],
                        on_delete=getattr(c, "on_delete", None),
                    ))
        return [CreateTableOperation(
            provenance=provenance, table=table_name, schema_=schema,
            columns=columns, constraints=constraints,
        )]

"""
sqlfy.parsing.column_parser
============================
Convert a sqlglot ColumnDef AST node into a domain Column dataclass.
"""

from __future__ import annotations

from typing import Optional

import sqlglot.expressions as exp

from ..domain.models import Column
from .ast_helpers import _table_full, _col_datatype


def _parse_column_def(col_node: exp.ColumnDef) -> Column:
    """Parse a sqlglot ColumnDef node into a domain Column.

    Args:
        col_node: A sqlglot ColumnDef expression node.

    Returns:
        A Column dataclass with all attributes populated from the AST.
    """
    name = col_node.name.upper()
    type_, precision, scale = _col_datatype(col_node.kind)

    nullable: bool = True
    default_val: Optional[str] = None
    primary_key: bool = False
    unique: bool = False
    references: Optional[dict] = None

    for c in col_node.constraints:
        kind = c.kind
        if isinstance(kind, exp.NotNullColumnConstraint):
            nullable = False
        elif isinstance(kind, exp.DefaultColumnConstraint):
            default_val = kind.this.sql(dialect="oracle") if kind.this else None
        elif isinstance(kind, exp.PrimaryKeyColumnConstraint):
            primary_key = True
            nullable = False
        elif isinstance(kind, exp.UniqueColumnConstraint):
            unique = True
        elif isinstance(kind, exp.Reference):
            ref_schema = kind.this  # Schema node
            ref_table = ref_schema.this if ref_schema else None
            if ref_table:
                ref_full = _table_full(ref_table)
                ref_cols = [e.name.upper() for e in ref_schema.expressions]
                references = {
                    "table": ref_full,
                    "column": ref_cols[0] if ref_cols else "",
                }

    return Column(
        name=name,
        type=type_,
        precision=precision,
        scale=scale,
        nullable=nullable,
        default=default_val,
        primary_key=primary_key,
        unique=unique,
        references=references,
    )


__all__ = ["_parse_column_def"]

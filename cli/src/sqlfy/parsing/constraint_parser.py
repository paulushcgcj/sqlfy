"""
sqlfy.parsing.constraint_parser
================================
Convert a sqlglot Constraint AST node into a domain Constraint dataclass.
"""

from __future__ import annotations

from typing import Optional

import sqlglot.expressions as exp

from ..domain.models import Constraint
from .ast_helpers import _table_full, _on_delete_from_options


def _parse_table_constraint(node: exp.Constraint) -> Optional[Constraint]:
    """Parse a sqlglot table-level Constraint node into a domain Constraint.

    Handles: PRIMARY KEY, UNIQUE, FOREIGN KEY, CHECK constraints.

    Args:
        node: A sqlglot Constraint expression node.

    Returns:
        A Constraint dataclass, or None if the node type is not recognised.
    """
    cname = node.name.upper() if node.name else None

    for expr in node.expressions:
        if isinstance(expr, exp.PrimaryKey):
            cols = [e.name.upper() for e in expr.expressions]
            return Constraint(name=cname, type="primary_key", columns=cols)

        if isinstance(expr, exp.UniqueColumnConstraint):
            schema = expr.this  # Schema node
            cols = [e.name.upper() for e in (schema.expressions if schema else [])]
            return Constraint(name=cname, type="unique", columns=cols)

        if isinstance(expr, exp.ForeignKey):
            from_cols = [e.name.upper() for e in expr.expressions]
            ref = expr.args.get("reference")
            to_table: str = ""
            to_cols: list[str] = []
            on_delete: Optional[str] = None
            if ref:
                ref_schema = ref.args.get("this")  # Schema wrapping Table
                if ref_schema:
                    ref_table = ref_schema.this
                    if ref_table:
                        to_table = _table_full(ref_table)
                    to_cols = [e.name.upper() for e in ref_schema.expressions]
                on_delete = _on_delete_from_options(ref.args.get("options", []))
            return Constraint(
                name=cname,
                type="foreign_key",
                columns=from_cols,
                references={"table": to_table, "columns": to_cols, "on_delete": on_delete},
            )

        if isinstance(expr, exp.CheckColumnConstraint):
            check_sql = expr.this.sql(dialect="oracle") if expr.this else ""
            return Constraint(name=cname, type="check", columns=[], check_expr=check_sql)

    return None


__all__ = ["_parse_table_constraint"]

"""
sqlfy.parsing.ast_helpers
=========================
Low-level sqlglot AST utility functions.

These functions translate raw sqlglot expression nodes into
simple Python values (strings, tuples). They form the lowest layer
of the parsing domain and carry no domain model imports.
"""

from __future__ import annotations

import re
from typing import Optional

import sqlglot.expressions as exp


def _table_full(node: exp.Table) -> str:
    """Return the fully qualified table name from a sqlglot Table node.

    Examples:
        Table('USERS') → 'USERS'
        Table('APP.USERS') → 'APP.USERS'
    """
    db = node.args.get("db")
    name = node.name.upper()
    if db:
        return f"{db.name.upper()}.{name}"
    return name


def _table_schema_name(node: exp.Table) -> tuple[Optional[str], str]:
    """Return (schema, name) from a sqlglot Table node, both uppercased."""
    db = node.args.get("db")
    return (db.name.upper() if db else None), node.name.upper()


def _col_datatype(
    kind: Optional[exp.DataType],
) -> tuple[str, Optional[int], Optional[int]]:
    """Extract (type_name, precision, scale) from a sqlglot DataType node.

    Returns:
        Tuple of (canonical_type_name, precision_or_None, scale_or_None).
    """
    if kind is None:
        return "UNKNOWN", None, None

    type_name = kind.this.name if kind.this else str(kind)
    exprs = kind.expressions
    precision = int(exprs[0].name) if len(exprs) > 0 and exprs[0].name.isdigit() else None
    scale = int(exprs[1].name) if len(exprs) > 1 and exprs[1].name.isdigit() else None

    # Normalise sqlglot type names back to Oracle-style display names
    _aliases: dict[str, str] = {
        "DECIMAL": "NUMBER",
        "FLOAT": "FLOAT",
        "TEXT": "CLOB",
        "TINYTEXT": "CLOB",
    }
    type_name = _aliases.get(type_name.upper(), type_name.upper())
    return type_name, precision, scale


def _on_delete_from_options(options: list) -> Optional[str]:
    """Extract ON DELETE action string from a list of option expressions."""
    joined = " ".join(str(o) for o in options).upper()
    m = re.search(
        r"ON DELETE (CASCADE|SET NULL|SET DEFAULT|RESTRICT|NO ACTION)", joined
    )
    if m:
        return m.group(1).replace(" ", "_")
    return None


__all__ = [
    "_table_full",
    "_table_schema_name",
    "_col_datatype",
    "_on_delete_from_options",
]

"""
sqlfy.parsing
=============
AST extraction domain.

Converts raw SQL text into structured, domain-typed data using sqlglot.
Nothing in this package exposes raw sqlglot AST nodes to callers.

Submodules
----------
ast_helpers         Low-level sqlglot AST utilities
column_parser       ColumnDef AST node → Column dataclass
constraint_parser   Constraint AST node → Constraint dataclass
ddl_handlers        Statement-level DDL dispatch (CREATE/ALTER/DROP/COMMENT)
dialects            Dialect adapter classes
"""

from .ast_helpers import _table_full, _table_schema_name, _col_datatype, _on_delete_from_options
from .column_parser import _parse_column_def
from .constraint_parser import _parse_table_constraint
from .ddl_handlers import (
    _handle_create_table,
    _handle_drop_table,
    _handle_alter_table,
    _handle_alter_table_command,
    _handle_create_index_command,
    _handle_create_sequence,
    _handle_comment,
)

__all__ = [
    "_table_full",
    "_table_schema_name",
    "_col_datatype",
    "_on_delete_from_options",
    "_parse_column_def",
    "_parse_table_constraint",
    "_handle_create_table",
    "_handle_drop_table",
    "_handle_alter_table",
    "_handle_alter_table_command",
    "_handle_create_index_command",
    "_handle_create_sequence",
    "_handle_comment",
]

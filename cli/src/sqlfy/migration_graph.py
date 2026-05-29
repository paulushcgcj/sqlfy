"""
sqlfy.migration_graph
=====================
Backward-compatibility shim. Implementation moved to sqlfy.graph.migration_graph.

New code should import from sqlfy.graph.migration_graph directly.
"""

from .graph.migration_graph import (
    MigrationNode,
    MigrationGraph,
    parse_migration_filename,
    extract_table_operations,
    build_migration_graph,
    format_dot,
    format_html,
    format_timeline,
    format_json,
)

__all__ = [
    "MigrationNode",
    "MigrationGraph",
    "parse_migration_filename",
    "extract_table_operations",
    "build_migration_graph",
    "format_dot",
    "format_html",
    "format_timeline",
    "format_json",
]

"""
sqlfy.migration_graph
=====================
Backward-compatibility shim. Implementation moved to sqlfy.graph.migration_graph.

New code should import from sqlfy.graph.migration_graph directly.
"""
from __future__ import annotations

from .graph.migration_graph import (
    MigrationGraph,
    MigrationNode,
    build_migration_graph,
    extract_table_operations,
    format_dot,
    format_html,
    format_json,
    format_timeline,
    parse_migration_filename,
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

"""
sqlfy.core
==========
Backward-compatibility shim.

The implementation has been decomposed into domain packages:
  - sqlfy.parsing           AST helpers, column/constraint parsers, DDL handlers
  - sqlfy.graph.builder     NetworkX graph construction
  - sqlfy.migrations.parser Flyway version string parsing

All names exported here continue to work for existing callers and tests.
New code should import directly from the domain packages.
"""

from __future__ import annotations

import logging

# Domain model re-exports
from .domain.models import (
    Column,
    Edge,
    MigrationAction,
    MigrationHistory,
    SchemaGraph,
    Sequence,
    Table,
)

# Graph layer re-exports
from .graph.builder import build_networkx_graph

# Migrations layer re-exports
from .migrations.parser import parse_flyway_ver

# Output layer re-exports
# Parsing layer re-exports

logging.getLogger("sqlglot").setLevel(logging.CRITICAL)

__all__ = [
    "Column", "Edge", "MigrationAction", "MigrationHistory",
    "SchemaGraph", "Sequence", "Table", "build_networkx_graph",
    "parse_flyway_ver", "apply_migrations",
]


def apply_migrations(files: list[dict], dialect: str = "oracle") -> SchemaGraph:
    """Reconstruct schema from migration files. Delegates to Reconstructor.

    Kept for backward compatibility. New code should use
    sqlfy.reconstructor.reconstruct() directly.
    """
    from .reconstructor import reconstruct
    return reconstruct(files, dialect=dialect)

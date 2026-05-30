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

# ── Domain model re-exports ───────────────────────────────────────────────────
from .domain.models import (
    Column,
    Constraint,
    Index,
    MigrationAction,
    Table,
    Sequence,
    Edge,
    MigrationHistory,
    SchemaGraph,
    VectorChunk,
    GraphNode,
    GraphEdge,
    EdgeRelation,
    Confidence,
)
from .domain.utils import type_str
from .domain.sqlglot_compat import SQLGLOT_HAS_MODIFY, parse_modify_native

# ── Parsing layer re-exports ──────────────────────────────────────────────────
from .parsing.ast_helpers import (
    _table_full,
    _table_schema_name,
    _col_datatype,
    _on_delete_from_options,
)
from .parsing.column_parser import _parse_column_def
from .parsing.constraint_parser import _parse_table_constraint
from .parsing.ddl_handlers import (
    _handle_create_table,
    _handle_drop_table,
    _handle_alter_table,
    _handle_alter_table_command,
    _handle_create_index_command,
    _handle_create_sequence,
    _handle_comment,
)

# ── Graph layer re-exports ────────────────────────────────────────────────────
from .graph.builder import build_networkx_graph

# ── Migrations layer re-exports ───────────────────────────────────────────────
from .migrations.parser import parse_flyway_ver

# ── Output layer re-exports ───────────────────────────────────────────────────
from .output.chunker import build_chunks
from .output.layout import compute_layout

logging.getLogger("sqlglot").setLevel(logging.CRITICAL)


# ─────────────────────────────────────────────
# APPLY MIGRATIONS (backward-compat wrapper)
# ─────────────────────────────────────────────

def apply_migrations(files: list[dict], dialect: str = "oracle") -> SchemaGraph:
    """Reconstruct schema from migration files. Delegates to Reconstructor.

    Kept for backward compatibility. New code should use
    ``sqlfy.reconstructor.reconstruct()`` directly.
    """
    from .reconstructor import reconstruct
    return reconstruct(files, dialect=dialect)




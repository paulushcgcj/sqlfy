"""
sqlfy.domain
============
Core domain models: data models, schema state utilities.
"""
from __future__ import annotations

from .models import (
    Column,
    Confidence,
    Constraint,
    Edge,
    EdgeRelation,
    GraphEdge,
    GraphNode,
    Index,
    MigrationAction,
    MigrationHistory,
    SchemaGraph,
    Sequence,
    Table,
    VectorChunk,
)
from .schema_state import SchemaState
from .utils import type_str

__all__ = [
    # Data models
    'Column', 'Constraint', 'Index', 'MigrationAction',
    'Table', 'Sequence', 'Edge', 'MigrationHistory',
    'SchemaGraph', 'VectorChunk', 'GraphNode', 'GraphEdge',
    'EdgeRelation', 'Confidence',
    # Utilities
    'type_str',
    # State management
    'SchemaState',
]

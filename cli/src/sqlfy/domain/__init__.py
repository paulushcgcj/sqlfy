"""
sqlfy.domain
============
Core domain models: data models, schema state utilities.
"""

from .models import (
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
from .utils import type_str
from .schema_state import SchemaState

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

"""
sqlfy.models
============
Data models for SQL schema representation.

All dataclasses used throughout the sqlfy package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Literal


# ─────────────────────────────────────────────
# SCHEMA DATA TYPES
# ─────────────────────────────────────────────

@dataclass
class Column:
    name: str
    type: str
    precision: Optional[int]
    scale: Optional[int]
    nullable: bool
    default: Optional[str]
    primary_key: bool
    unique: bool
    references: Optional[dict]   # { table, column }


@dataclass
class Constraint:
    name: Optional[str]
    type: str                    # primary_key | unique | foreign_key | check
    columns: list[str]
    references: Optional[dict] = None   # { table, columns, on_delete }
    check_expr: Optional[str]  = None


@dataclass
class Index:
    name: str
    columns: list[str]
    unique: bool
    created_in: str


@dataclass
class MigrationAction:
    """Records what a single migration statement did — used in history/diff."""
    action: str           # CREATE | DROP | ADD_COLUMN | DROP_COLUMN | MODIFY_COLUMN
                          # ADD_CONSTRAINT | DROP_CONSTRAINT | CREATE_INDEX | CREATE_SEQUENCE
    object_type: str      # TABLE | COLUMN | CONSTRAINT | INDEX | SEQUENCE
    object_name: str      # fully-qualified name of the affected object
    version: str


@dataclass
class Table:
    id: str
    schema: Optional[str]
    name: str
    full: str
    columns: list[Column]        = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)
    indexes: list[Index]         = field(default_factory=list)
    comments: dict[str, str]     = field(default_factory=dict)
    created_in: str              = ''
    modified_in: list[str]       = field(default_factory=list)
    actions: list[MigrationAction] = field(default_factory=list)


@dataclass
class Sequence:
    name: str
    schema: Optional[str]
    full: str
    start_with: int
    increment_by: int
    created_in: str


@dataclass
class Edge:
    id: str
    from_table: str
    from_cols: list[str]
    to_table: str
    to_cols: list[str]
    constraint_name: Optional[str]
    on_delete: Optional[str]


@dataclass
class MigrationHistory:
    version: str
    description: str


@dataclass
class SchemaGraph:
    tables: dict[str, Table]
    seqs: dict[str, Sequence]
    edges: list[Edge]
    mig_hist: list[MigrationHistory]
    actions: list[MigrationAction] = field(default_factory=list)  # all actions across all migrations


@dataclass
class VectorChunk:
    id: str
    type: str
    title: str
    content: str
    meta: dict
    hint: str


# ─────────────────────────────────────────────
# GRAPH DATA TYPES (for NetworkX)
# ─────────────────────────────────────────────

EdgeRelation = Literal[
    "foreign_key",      # FK relationship
    "references",       # Column references another table
    "contains",         # Table contains column
    "modifies",         # Migration modifies object
    "creates",          # Migration creates object
    "drops",            # Migration drops object
]

Confidence = Literal["EXTRACTED", "INFERRED", "AMBIGUOUS"]


@dataclass
class GraphNode:
    """NetworkX-compatible node representation."""
    id: str
    label: str
    type: str  # table | column | view | sequence | constraint | migration
    source_file: Optional[str] = None
    source_location: Optional[str] = None
    created_in: Optional[str] = None
    modified_in: list[str] = field(default_factory=list)


@dataclass
class GraphEdge:
    """NetworkX-compatible edge representation."""
    source: str
    target: str
    relation: EdgeRelation
    confidence: Confidence = "EXTRACTED"
    metadata: dict = field(default_factory=dict)

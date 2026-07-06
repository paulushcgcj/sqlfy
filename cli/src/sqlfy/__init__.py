# sqlfy cli package
from __future__ import annotations

from .analysis.differ import DiffResult, SchemaDiffer, diff_files
from .analysis.insights import Finding, InsightsEngine, InsightsReport
from .core import apply_migrations
from .domain.models import (
    Column,
    Edge,
    MigrationAction,
    SchemaGraph,
    Sequence,
    Table,
    VectorChunk,
)
from .domain.schema_state import (
    ColumnState,
    ConstraintState,
    IndexState,
    MigrationStep,
    RelationshipState,
    SchemaState,
    SchemaStateBuilder,
    SequenceState,
    TableState,
)
from .domain.utils import type_str
from .output.chunker import build_chunks
from .output.exporter import Exporter
from .output.grapher import Grapher
from .output.layout import compute_layout
from .reconstructor import MigrationResult, Reconstructor, reconstruct, reconstruct_at

__all__ = [
    'apply_migrations', 'build_chunks', 'compute_layout', 'type_str',
    'SchemaGraph', 'VectorChunk', 'Table', 'Column', 'Edge', 'Sequence', 'MigrationAction',
    'Reconstructor', 'reconstruct', 'reconstruct_at', 'MigrationResult',
    'SchemaState', 'SchemaStateBuilder',
    'TableState', 'ColumnState', 'ConstraintState', 'IndexState',
    'SequenceState', 'RelationshipState', 'MigrationStep',
    'SchemaDiffer', 'DiffResult', 'diff_files',
    'Grapher', 'Exporter',
    'InsightsEngine', 'InsightsReport', 'Finding',
]

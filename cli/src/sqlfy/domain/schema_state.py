"""
sqlfy.schema_state
==================
Schema State Dictionary — a clean, versioned, serialisable representation
of the reconstructed database state.

Separates *what the DB looks like* from the internal reconstruction machinery.
Can be serialised to JSON or YAML, compared across versions, and fed directly
into LLM pipelines or documentation generators.

Key concepts
------------
SchemaState
    The top-level snapshot. Contains all tables, sequences, relationships,
    and the migration history that produced this state.

TableState
    A single table's complete current state — columns, constraints, indexes,
    comments, and the migration version that last touched it.

RelationshipState
    A denormalised view of a single FK edge, including cardinality hints.

Usage
-----
    from cli.schema_state import SchemaStateBuilder

    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)

    # Serialise
    print(state.to_json())
    print(state.to_yaml())

    # Access
    for table in state.tables.values():
        print(table.full_name, [c.name for c in table.columns])
"""

from __future__ import annotations

import json
import hashlib
import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional

from .models import SchemaGraph
from .utils import type_str


# ─────────────────────────────────────────────
# VALUE OBJECTS
# ─────────────────────────────────────────────

@dataclass
class ColumnState:
    name:        str
    data_type:   str           # rendered type string e.g. "NUMBER(10,2)"
    raw_type:    str           # base type name e.g. "NUMBER"
    precision:   Optional[int]
    scale:       Optional[int]
    nullable:    bool
    default:     Optional[str]
    is_pk:       bool
    is_fk:       bool
    is_unique:   bool
    comment:     Optional[str]


@dataclass
class ConstraintState:
    name:        Optional[str]
    type:        str           # primary_key | unique | foreign_key | check
    columns:     list[str]
    ref_table:   Optional[str] = None
    ref_columns: Optional[list[str]] = None
    on_delete:   Optional[str] = None
    check_expr:  Optional[str] = None


@dataclass
class IndexState:
    name:       str
    columns:    list[str]
    unique:     bool
    created_in: str


@dataclass
class TableState:
    schema:       Optional[str]
    name:         str
    full_name:    str
    columns:      list[ColumnState]
    constraints:  list[ConstraintState]
    indexes:      list[IndexState]
    comment:      Optional[str]
    created_in:   str
    modified_in:  list[str]
    column_count: int
    has_pk:       bool
    pk_columns:   list[str]

    @property
    def fk_columns(self) -> list[str]:
        fk_cols: list[str] = []
        for c in self.constraints:
            if c.type == 'foreign_key':
                fk_cols.extend(c.columns)
        return fk_cols


@dataclass
class RelationshipState:
    id:              str
    from_table:      str
    from_columns:    list[str]
    to_table:        str
    to_columns:      list[str]
    constraint_name: Optional[str]
    on_delete:       Optional[str]
    # Derived cardinality hints (heuristic, not parsed from DDL)
    cardinality:     str   # "many_to_one" | "one_to_one" | "unknown"


@dataclass
class SequenceState:
    schema:       Optional[str]
    name:         str
    full_name:    str
    start_with:   int
    increment_by: int
    created_in:   str


@dataclass
class MigrationStep:
    version:     str
    description: str


@dataclass
class SchemaState:
    """
    Complete, serialisable snapshot of the database schema at a point in time.

    Fields
    ------
    version
        The latest migration version included in this snapshot.
    generated_at
        ISO-8601 timestamp of when this snapshot was generated.
    fingerprint
        SHA-256 of the canonical JSON — use to detect changes.
    dialect
        The SQL dialect used for parsing (e.g. 'oracle').
    tables
        All tables keyed by fully-qualified name (e.g. 'APP.USERS').
    sequences
        All sequences keyed by fully-qualified name.
    relationships
        All FK relationships (denormalised for easy consumption).
    migration_history
        Ordered list of migrations applied to produce this state.
    stats
        Quick summary counts.
    source_files
        Optional list of source migration files for anti-pattern detection.
    """
    version:           str
    generated_at:      str
    fingerprint:       str
    dialect:           str
    tables:            dict[str, TableState]
    sequences:         dict[str, SequenceState]
    relationships:     list[RelationshipState]
    migration_history: list[MigrationStep]
    stats:             dict[str, int]
    source_files:      list[dict] = field(default_factory=list)

    # ── Serialisation ─────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Convert to a plain dict (JSON-safe)."""
        return _deep_asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serialise to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)

    def to_yaml(self) -> str:
        """
        Serialise to YAML string.
        Requires PyYAML (pip install pyyaml) — raises ImportError if missing.
        """
        try:
            import yaml
        except ImportError:
            raise ImportError(
                'PyYAML is required for YAML output. Install with: pip install pyyaml'
            )
        return yaml.dump(self.to_dict(), allow_unicode=True, sort_keys=False, default_flow_style=False)

    # ── Convenience accessors ──────────────────────────────────────────────

    def get_table(self, name: str) -> Optional[TableState]:
        """Case-insensitive table lookup by name or full name."""
        name_up = name.upper()
        return (
            self.tables.get(name_up)
            or next((t for t in self.tables.values() if t.name == name_up), None)
        )

    def tables_in_schema(self, schema: str) -> list[TableState]:
        return [t for t in self.tables.values() if (t.schema or '').upper() == schema.upper()]

    def orphan_tables(self) -> list[TableState]:
        """Tables with no FK relationships in or out."""
        rel_tables = {r.from_table for r in self.relationships} | {r.to_table for r in self.relationships}
        return [t for t in self.tables.values() if t.full_name not in rel_tables]

    def tables_without_pk(self) -> list[TableState]:
        return [t for t in self.tables.values() if not t.has_pk]

    def tables_referencing(self, full_name: str) -> list[TableState]:
        """Tables that have an FK pointing TO full_name."""
        names = {r.from_table for r in self.relationships if r.to_table == full_name.upper()}
        return [self.tables[n] for n in names if n in self.tables]

    def tables_referenced_by(self, full_name: str) -> list[TableState]:
        """Tables that full_name points TO via FK."""
        names = {r.to_table for r in self.relationships if r.from_table == full_name.upper()}
        return [self.tables[n] for n in names if n in self.tables]


# ─────────────────────────────────────────────
# BUILDER
# ─────────────────────────────────────────────

class SchemaStateBuilder:
    """Converts a SchemaGraph into a SchemaState."""

    @staticmethod
    def from_graph(
        graph: SchemaGraph,
        dialect: str = 'oracle',
        source_files: Optional[list[dict]] = None,
    ) -> SchemaState:
        tables        = SchemaStateBuilder._build_tables(graph)
        sequences     = SchemaStateBuilder._build_sequences(graph)
        relationships = SchemaStateBuilder._build_relationships(graph)
        mig_history   = [MigrationStep(version=m.version, description=m.description)
                         for m in graph.mig_hist]

        latest_version = mig_history[-1].version if mig_history else '0'

        stats = {
            'table_count':        len(tables),
            'column_count':       sum(t.column_count for t in tables.values()),
            'sequence_count':     len(sequences),
            'relationship_count': len(relationships),
            'index_count':        sum(len(t.indexes) for t in tables.values()),
            'tables_without_pk':  sum(1 for t in tables.values() if not t.has_pk),
            'migration_count':    len(mig_history),
        }

        generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')

        # Fingerprint — stable hash of the canonical table/column structure
        fingerprint_src = json.dumps(
            {k: {'cols': [c.name for c in t.columns], 'cons': [c.type for c in t.constraints]}
             for k, t in sorted(tables.items())},
            sort_keys=True
        )
        fingerprint = hashlib.sha256(fingerprint_src.encode()).hexdigest()[:16]

        return SchemaState(
            version=latest_version,
            generated_at=generated_at,
            fingerprint=fingerprint,
            dialect=dialect,
            tables=tables,
            sequences=sequences,
            relationships=relationships,
            migration_history=mig_history,
            stats=stats,
            source_files=source_files or [],
        )

    # ── Table builder ──────────────────────────────────────────────────────

    @staticmethod
    def _build_tables(graph: SchemaGraph) -> dict[str, TableState]:
        result: dict[str, TableState] = {}

        # Pre-index FK columns for badge decoration
        fk_col_map: dict[str, set[str]] = {}   # full_table → set of col names
        for e in graph.edges:
            fk_col_map.setdefault(e.from_table, set()).update(e.from_cols)

        for full, t in graph.tables.items():
            pk = next((c for c in t.constraints if c.type == 'primary_key'), None)
            pk_cols = set(pk.columns) if pk else set()
            uq_cols: set[str] = set()
            for c in t.constraints:
                if c.type == 'unique':
                    uq_cols.update(c.columns)
            fk_cols = fk_col_map.get(full, set())

            columns = [
                ColumnState(
                    name=col.name,
                    data_type=type_str(col),
                    raw_type=col.type,
                    precision=col.precision,
                    scale=col.scale,
                    nullable=col.nullable,
                    default=col.default,
                    is_pk=col.name in pk_cols,
                    is_fk=col.name in fk_cols,
                    is_unique=col.name in uq_cols,
                    comment=t.comments.get(col.name),
                )
                for col in t.columns
            ]

            constraints = []
            for c in t.constraints:
                cs = ConstraintState(
                    name=c.name,
                    type=c.type,
                    columns=list(c.columns),
                )
                if c.references:
                    cs.ref_table   = c.references.get('table')
                    cs.ref_columns = c.references.get('columns')
                    cs.on_delete   = c.references.get('on_delete')
                if c.check_expr:
                    cs.check_expr = c.check_expr
                constraints.append(cs)

            indexes = [
                IndexState(name=i.name, columns=list(i.columns),
                           unique=i.unique, created_in=i.created_in)
                for i in t.indexes
            ]

            result[full] = TableState(
                schema=t.schema,
                name=t.name,
                full_name=full,
                columns=columns,
                constraints=constraints,
                indexes=indexes,
                comment=t.comments.get('__table__'),
                created_in=t.created_in,
                modified_in=list(t.modified_in),
                column_count=len(columns),
                has_pk=bool(pk),
                pk_columns=list(pk_cols),
            )

        return result

    # ── Sequence builder ───────────────────────────────────────────────────

    @staticmethod
    def _build_sequences(graph: SchemaGraph) -> dict[str, SequenceState]:
        return {
            full: SequenceState(
                schema=s.schema, name=s.name, full_name=full,
                start_with=s.start_with, increment_by=s.increment_by,
                created_in=s.created_in,
            )
            for full, s in graph.seqs.items()
        }

    # ── Relationship builder ───────────────────────────────────────────────

    @staticmethod
    def _build_relationships(graph: SchemaGraph) -> list[RelationshipState]:
        rels: list[RelationshipState] = []
        for e in graph.edges:
            # Heuristic cardinality: if from_cols is the PK of from_table → one_to_one
            from_table = graph.tables.get(e.from_table)
            pk = next((c for c in (from_table.constraints if from_table else [])
                       if c.type == 'primary_key'), None)
            if pk and set(e.from_cols) == set(pk.columns):
                cardinality = 'one_to_one'
            else:
                cardinality = 'many_to_one'

            rels.append(RelationshipState(
                id=e.id,
                from_table=e.from_table,
                from_columns=list(e.from_cols),
                to_table=e.to_table,
                to_columns=list(e.to_cols),
                constraint_name=e.constraint_name,
                on_delete=e.on_delete,
                cardinality=cardinality,
            ))
        return rels


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _deep_asdict(obj) -> object:
    """Recursively convert dataclasses to plain dicts, preserve other types."""
    if hasattr(obj, '__dataclass_fields__'):
        return {k: _deep_asdict(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _deep_asdict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_asdict(i) for i in obj]
    return obj
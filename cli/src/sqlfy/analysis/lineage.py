"""
sqlfy.analysis.lineage
======================
Column-level lineage and data flow analysis.

Integrates sqllineage to trace column dependencies across tables, views,
and stored procedures. Extends Feature #3 (Impact Analysis) from table-level
to column-level granularity.

Usage
-----
    from sqlfy.core import load_files
    from sqlfy.reconstructor import Reconstructor
    from sqlfy.analysis.lineage import extract_column_lineage, find_downstream
    
    files = load_files('migrations/')
    reconstructor = Reconstructor()
    schema_graph = reconstructor.apply_migrations(files)
    lineage = extract_column_lineage(schema_graph, files)
    
    downstream = find_downstream('users.email', lineage)
    print(f"Downstream columns: {len(downstream)}")
"""

from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

try:
    from sqllineage.runner import LineageRunner
    SQLLINEAGE_AVAILABLE = True
except ImportError:
    LineageRunner = None  # type: ignore[assignment,misc]
    SQLLINEAGE_AVAILABLE = False

import sqlglot
import sqlglot.expressions as exp

from ..domain.models import SchemaGraph, Table


@dataclass
class ColumnRef:
    """Reference to a specific column in a table/view."""
    
    table: str
    """Table or view name (fully qualified, e.g., APP.USERS)."""
    
    column: str
    """Column name (e.g., EMAIL)."""
    
    @property
    def full_name(self) -> str:
        """Fully qualified column name: table.column."""
        return f"{self.table}.{self.column}"
    
    @property
    def id(self) -> str:
        """Alias for full_name (for consistency with graph nodes)."""
        return self.full_name
    
    def __hash__(self) -> int:
        return hash(self.full_name)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ColumnRef):
            return False
        return self.full_name == other.full_name


@dataclass
class LineageEdge:
    """Directed edge representing column dependency."""
    
    source: ColumnRef
    """Source column (upstream)."""
    
    target: ColumnRef
    """Target column (downstream)."""
    
    via: str
    """How the dependency was established: JOIN, SELECT, CTE, CASE, etc."""
    
    statement: str
    """SQL snippet showing the dependency."""
    
    migration_version: str
    """Migration where this dependency was created."""
    
    lineage_type: str = "direct"
    """Type of lineage: direct, transformed, extraction, aggregation."""


@dataclass
class ColumnLineage:
    """Complete lineage information for a single column."""
    
    column: ColumnRef
    """The column being analyzed."""
    
    upstream: list[ColumnRef] = field(default_factory=list)
    """Columns this depends on (sources)."""
    
    downstream: list[ColumnRef] = field(default_factory=list)
    """Columns that depend on this (targets)."""
    
    edges: list[LineageEdge] = field(default_factory=list)
    """All edges involving this column."""
    
    created_in: str = ""
    """Migration version where column was created."""
    
    last_modified: str = ""
    """Migration version where column was last modified."""
    
    reference_count: int = 0
    """How many times this column is referenced in SELECT statements."""
    
    is_pk: bool = False
    """Whether this column is a primary key."""
    
    is_fk: bool = False
    """Whether this column is a foreign key."""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'column': self.column.full_name,
            'upstream': [c.full_name for c in self.upstream],
            'downstream': [c.full_name for c in self.downstream],
            'edges': [
                {
                    'source': e.source.full_name,
                    'target': e.target.full_name,
                    'via': e.via,
                    'type': e.lineage_type,
                    'migration': e.migration_version,
                }
                for e in self.edges
            ],
            'created_in': self.created_in,
            'last_modified': self.last_modified,
            'reference_count': self.reference_count,
            'is_pk': self.is_pk,
            'is_fk': self.is_fk,
        }


def extract_column_lineage(
    schema_graph: SchemaGraph,
    files: list[tuple[str, str]],
) -> dict[str, ColumnLineage]:
    """
    Extract column-level lineage from schema graph.
    
    Analyzes views, stored procedures, and CREATE TABLE AS SELECT statements
    to build a complete column dependency graph.
    
    Args:
        schema_graph: Schema graph from reconstructor
        files: List of (version, sql) migration files
    
    Returns:
        Dict mapping column_id (table.column) to ColumnLineage
    """
    lineage_map: dict[str, ColumnLineage] = {}
    edges: list[LineageEdge] = []
    
    # Step 1: Initialize lineage for all table columns
    for table_id, table in schema_graph.tables.items():
        for col in table.columns:
            col_ref = ColumnRef(table.full, col.name)
            lineage_map[col_ref.id] = ColumnLineage(
                column=col_ref,
                created_in=table.created_in,
                last_modified=table.modified_in[-1] if table.modified_in else table.created_in,
                is_pk=col.primary_key,
                is_fk=col.references is not None,
            )
    
    # Step 2: Extract lineage from views using sqllineage
    if SQLLINEAGE_AVAILABLE:
        for version, sql in files:
            edges.extend(_extract_from_migration(version, sql, schema_graph))
    
    # Step 3: Build upstream/downstream relationships
    for edge in edges:
        source_id = edge.source.id
        target_id = edge.target.id
        
        # Ensure both columns exist in lineage map
        if source_id not in lineage_map:
            lineage_map[source_id] = ColumnLineage(column=edge.source)
        if target_id not in lineage_map:
            lineage_map[target_id] = ColumnLineage(column=edge.target)
        
        # Add edge to both source and target
        lineage_map[source_id].downstream.append(edge.target)
        lineage_map[source_id].edges.append(edge)
        lineage_map[target_id].upstream.append(edge.source)
        lineage_map[target_id].edges.append(edge)
        
        # Increment reference count for source
        lineage_map[source_id].reference_count += 1
    
    # Deduplicate upstream/downstream lists
    for col_lineage in lineage_map.values():
        col_lineage.upstream = list(set(col_lineage.upstream))
        col_lineage.downstream = list(set(col_lineage.downstream))
    
    return lineage_map


def _extract_from_migration(
    version: str,
    sql: str,
    schema_graph: SchemaGraph,
) -> list[LineageEdge]:
    """
    Extract lineage edges from a single migration file.
    
    Parses CREATE VIEW, CREATE TABLE AS SELECT, and stored procedures.
    """
    edges: list[LineageEdge] = []
    
    try:
        statements = sqlglot.parse(sql, dialect='oracle')
    except Exception:
        return edges
    
    for stmt in statements:
        if stmt is None:
            continue
        
        # Handle CREATE VIEW
        if isinstance(stmt, exp.Create) and stmt.kind == 'VIEW':
            view_name = _get_view_name(stmt)
            view_sql = stmt.expression.sql(dialect='oracle') if stmt.expression else ""
            
            if view_name and view_sql:
                edges.extend(_extract_from_select(
                    view_name, view_sql, version, schema_graph
                ))
        
        # Handle CREATE TABLE AS SELECT
        elif isinstance(stmt, exp.Create) and stmt.kind == 'TABLE':
            if stmt.expression and isinstance(stmt.expression, exp.Select):
                table_node = stmt.this
                if isinstance(table_node, exp.Schema):
                    table_node = table_node.this
                if isinstance(table_node, exp.Table):
                    table_name = _table_full(table_node)
                    select_sql = stmt.expression.sql(dialect='oracle')
                    edges.extend(_extract_from_select(
                        table_name, select_sql, version, schema_graph
                    ))
    
    return edges


def _extract_from_select(
    target_name: str,
    select_sql: str,
    version: str,
    schema_graph: SchemaGraph,
) -> list[LineageEdge]:
    """
    Extract column lineage from a SELECT statement using sqllineage.
    
    Falls back to simple regex parsing if sqllineage is unavailable.
    """
    edges: list[LineageEdge] = []
    
    if not SQLLINEAGE_AVAILABLE:
        # Fallback: simple regex-based extraction
        return _extract_simple_lineage(target_name, select_sql, version)
    
    assert LineageRunner is not None
    try:
        runner = LineageRunner(select_sql, dialect='oracle')
        
        # Get column-level lineage
        for col_lineage in runner.get_column_lineage():
            # col_lineage is a tuple: (source_col, target_col)
            # source_col and target_col are sqllineage Column objects
            source_col = col_lineage[0]
            target_col = col_lineage[1] if len(col_lineage) > 1 else None
            
            if source_col and target_col:
                source_table = str(source_col.parent) if hasattr(source_col, 'parent') else ""
                source_name = str(source_col.raw_name)
                target_table = str(target_col.parent) if hasattr(target_col, 'parent') else target_name
                target_name_col = str(target_col.raw_name)
                
                # Normalize table names to match schema graph format
                source_table = _normalize_table_name(source_table, schema_graph)
                target_table = _normalize_table_name(target_table, schema_graph)
                
                if source_table and source_name and target_table and target_name_col:
                    edges.append(LineageEdge(
                        source=ColumnRef(source_table, source_name.upper()),
                        target=ColumnRef(target_table, target_name_col.upper()),
                        via="SELECT",
                        statement=select_sql[:200],  # Truncate for display
                        migration_version=version,
                        lineage_type="direct",
                    ))
    
    except Exception:
        # Fallback to simple parsing if sqllineage fails
        return _extract_simple_lineage(target_name, select_sql, version)
    
    return edges


def _extract_simple_lineage(
    target_name: str,
    select_sql: str,
    version: str,
) -> list[LineageEdge]:
    """
    Simple regex-based lineage extraction (fallback when sqllineage unavailable).
    
    Detects basic patterns like:
    - SELECT table.column
    - SELECT table.*
    - JOIN table ON ...
    """
    edges: list[LineageEdge] = []
    
    # Pattern: table.column or table_alias.column
    col_pattern = r'\b(\w+)\.(\w+)\b'
    
    for match in re.finditer(col_pattern, select_sql, re.IGNORECASE):
        table_or_alias = match.group(1).upper()
        column = match.group(2).upper()
        
        # Skip common SQL keywords
        if table_or_alias in {'SELECT', 'FROM', 'WHERE', 'JOIN', 'ON', 'AND', 'OR'}:
            continue
        
        # Create a basic lineage edge
        # Note: This is simplified - doesn't resolve aliases or handle complex queries
        edges.append(LineageEdge(
            source=ColumnRef(table_or_alias, column),
            target=ColumnRef(target_name, column),
            via="SELECT",
            statement=select_sql[:200],
            migration_version=version,
            lineage_type="inferred",
        ))
    
    return edges


def _normalize_table_name(table_name: str, schema_graph: SchemaGraph) -> str:
    """
    Normalize table name to match schema graph format (SCHEMA.TABLE).
    
    Handles aliases and unqualified names by matching against known tables.
    """
    if not table_name:
        return ""
    
    table_upper = table_name.upper()
    
    # Check if already fully qualified and exists
    if table_upper in schema_graph.tables:
        return table_upper
    
    # Try to find unqualified name in schema graph
    for full_name in schema_graph.tables.keys():
        if full_name.endswith('.' + table_upper):
            return full_name
        if full_name == table_upper:
            return full_name
    
    # Return as-is if not found (might be an alias or external table)
    return table_upper


def _get_view_name(stmt: exp.Create) -> str:
    """Extract view name from CREATE VIEW statement."""
    view_node = stmt.this
    if isinstance(view_node, exp.Schema):
        view_node = view_node.this
    if isinstance(view_node, exp.Table):
        return _table_full(view_node)
    return ""


def _table_full(node: exp.Table) -> str:
    """Get fully qualified table name from sqlglot Table node."""
    db = node.args.get('db')
    name = node.name.upper()
    if db:
        return f'{db.name.upper()}.{name}'
    return name


def find_downstream(
    column: str,
    lineage: dict[str, ColumnLineage],
    depth: int = -1,
) -> list[ColumnRef]:
    """
    Find all downstream columns that depend on the given column.
    
    Uses BFS traversal to find all columns transitively affected by changes
    to the specified column.
    
    Args:
        column: Column identifier (table.column format)
        lineage: Column lineage map from extract_column_lineage()
        depth: Maximum traversal depth (-1 for unlimited)
    
    Returns:
        List of downstream column references
    """
    if column not in lineage:
        return []
    
    visited: set[str] = {column}
    result: list[ColumnRef] = []
    queue: deque[tuple[str, int]] = deque([(column, 0)])
    
    while queue:
        current, current_depth = queue.popleft()
        
        if depth >= 0 and current_depth >= depth:
            continue
        
        if current not in lineage:
            continue
        
        for downstream_col in lineage[current].downstream:
            if downstream_col.id not in visited:
                visited.add(downstream_col.id)
                result.append(downstream_col)
                queue.append((downstream_col.id, current_depth + 1))
    
    return result


def find_upstream(
    column: str,
    lineage: dict[str, ColumnLineage],
    depth: int = -1,
) -> list[ColumnRef]:
    """
    Find all upstream columns that the given column depends on.
    
    Uses BFS traversal to find all source columns.
    
    Args:
        column: Column identifier (table.column format)
        lineage: Column lineage map from extract_column_lineage()
        depth: Maximum traversal depth (-1 for unlimited)
    
    Returns:
        List of upstream column references
    """
    if column not in lineage:
        return []
    
    visited: set[str] = {column}
    result: list[ColumnRef] = []
    queue: deque[tuple[str, int]] = deque([(column, 0)])
    
    while queue:
        current, current_depth = queue.popleft()
        
        if depth >= 0 and current_depth >= depth:
            continue
        
        if current not in lineage:
            continue
        
        for upstream_col in lineage[current].upstream:
            if upstream_col.id not in visited:
                visited.add(upstream_col.id)
                result.append(upstream_col)
                queue.append((upstream_col.id, current_depth + 1))
    
    return result


def find_unused_columns(
    schema_graph: SchemaGraph,
    lineage: dict[str, ColumnLineage],
) -> list[tuple[ColumnRef, str]]:
    """
    Find columns that are defined but never referenced in views or queries.
    
    Args:
        schema_graph: Schema graph from reconstructor
        lineage: Column lineage map
    
    Returns:
        List of (column_ref, created_in_version) tuples for unused columns
    """
    unused: list[tuple[ColumnRef, str]] = []
    
    for table in schema_graph.tables.values():
        for col in table.columns:
            col_ref = ColumnRef(table.full, col.name)
            
            if col_ref.id in lineage:
                col_lineage = lineage[col_ref.id]
                
                # Column is unused if it has no downstream references and isn't used
                # Exception: PKs and FKs are considered "used" by definition
                if (col_lineage.reference_count == 0 and 
                    len(col_lineage.downstream) == 0 and
                    not col_lineage.is_pk and
                    not col_lineage.is_fk):
                    unused.append((col_ref, col_lineage.created_in))
    
    return unused


def find_god_columns(
    lineage: dict[str, ColumnLineage],
    min_refs: int = 20,
) -> list[tuple[ColumnRef, int]]:
    """
    Find "god columns" that are heavily referenced across the schema.
    
    God columns are candidates for performance optimization (indexing),
    caching, or architectural review.
    
    Args:
        lineage: Column lineage map
        min_refs: Minimum reference count to be considered a god column
    
    Returns:
        List of (column_ref, reference_count) tuples, sorted by reference count
    """
    god_columns: list[tuple[ColumnRef, int]] = []
    
    for col_id, col_lineage in lineage.items():
        total_refs = col_lineage.reference_count + len(col_lineage.downstream)
        
        if total_refs >= min_refs:
            god_columns.append((col_lineage.column, total_refs))
    
    # Sort by reference count (descending)
    god_columns.sort(key=lambda x: x[1], reverse=True)
    
    return god_columns


def format_lineage_text(
    column: str,
    lineage: dict[str, ColumnLineage],
    direction: str = 'downstream',
    max_display: int = 50,
) -> str:
    """
    Format column lineage as human-readable text.
    
    Args:
        column: Column identifier (table.column)
        lineage: Column lineage map
        direction: 'downstream' or 'upstream'
        max_display: Maximum number of dependencies to display
    
    Returns:
        Formatted text output
    """
    if column not in lineage:
        return f"Column not found: {column}"
    
    col_lineage = lineage[column]
    lines = [
        f"Column Lineage: {column}",
        "=" * (16 + len(column)),
        "",
        f"Created in: {col_lineage.created_in or 'unknown'}",
        f"Last modified: {col_lineage.last_modified or 'unknown'}",
        f"Reference count: {col_lineage.reference_count}",
        f"Primary key: {'Yes' if col_lineage.is_pk else 'No'}",
        f"Foreign key: {'Yes' if col_lineage.is_fk else 'No'}",
        "",
    ]
    
    # Show downstream or upstream dependencies
    if direction == 'downstream':
        deps = col_lineage.downstream
        lines.append(f"Downstream dependencies ({len(deps)}):")
    else:
        deps = col_lineage.upstream
        lines.append(f"Upstream dependencies ({len(deps)}):")
    
    if not deps:
        lines.append("  (none)")
    else:
        # Show up to max_display dependencies
        for i, dep in enumerate(deps[:max_display]):
            lines.append(f"  → {dep.full_name}")
            
            # Find the edge for this dependency
            for edge in col_lineage.edges:
                if direction == 'downstream' and edge.target == dep:
                    lines.append(f"      via: {edge.via} in {edge.migration_version}")
                    break
                elif direction == 'upstream' and edge.source == dep:
                    lines.append(f"      via: {edge.via} in {edge.migration_version}")
                    break
        
        if len(deps) > max_display:
            lines.append(f"  ... and {len(deps) - max_display} more")
    
    return "\n".join(lines)


def format_lineage_json(lineage: dict[str, ColumnLineage]) -> dict[str, Any]:
    """
    Format column lineage as JSON.
    
    Args:
        lineage: Column lineage map
    
    Returns:
        JSON-serializable dictionary
    """
    return {
        'columns': {
            col_id: col_lineage.to_dict()
            for col_id, col_lineage in lineage.items()
        },
        'total_columns': len(lineage),
    }


def format_lineage_mermaid(
    column: str,
    lineage: dict[str, ColumnLineage],
    direction: str = 'downstream',
    max_depth: int = 3,
) -> str:
    """
    Format column lineage as Mermaid graph diagram.
    
    Args:
        column: Column identifier (table.column)
        lineage: Column lineage map
        direction: 'downstream' or 'upstream'
        max_depth: Maximum depth to traverse
    
    Returns:
        Mermaid diagram source code
    """
    if column not in lineage:
        return f"graph LR\n    {column}[Column not found: {column}]"
    
    lines = ["graph LR"]
    
    # BFS traversal to build graph
    visited: set[str] = {column}
    queue: deque[tuple[str, int]] = deque([(column, 0)])
    
    while queue:
        current, depth = queue.popleft()
        
        if depth >= max_depth:
            continue
        
        if current not in lineage:
            continue
        
        col_lineage = lineage[current]
        deps = col_lineage.downstream if direction == 'downstream' else col_lineage.upstream
        
        for dep in deps:
            if dep.id not in visited:
                visited.add(dep.id)
                queue.append((dep.id, depth + 1))
            
            # Add edge to diagram
            if direction == 'downstream':
                lines.append(f"    {_mermaid_id(current)} --> {_mermaid_id(dep.id)}")
            else:
                lines.append(f"    {_mermaid_id(dep.id)} --> {_mermaid_id(current)}")
    
    return "\n".join(lines)


def _mermaid_id(column_id: str) -> str:
    """Convert column ID to Mermaid-safe node ID."""
    return column_id.replace('.', '_').replace('-', '_')

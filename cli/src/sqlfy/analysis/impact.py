"""
sqlfy.analysis.impact
=====================
Impact analysis for schema changes using graph traversal.

Determines what objects are affected (directly or transitively) by changes
to a given schema object. Uses NetworkX graph traversal to find all
downstream dependencies.

Usage
-----
    from cli.core import build_networkx_graph
    from cli.analysis.impact import analyze_impact, ImpactResult
    
    graph = build_networkx_graph(schema_graph)
    result = analyze_impact(graph, 'APP.USERS')
    
    print(f"Direct: {result.direct}")
    print(f"Transitive: {result.transitive}")
    print(f"Total affected: {result.total_count}")
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

import networkx as nx


@dataclass
class ImpactResult:
    """Result of impact analysis for a schema object."""
    
    object_id: str
    """The object being analyzed."""
    
    direct: list[str] = field(default_factory=list)
    """Objects directly affected (depth 1)."""
    
    transitive: list[str] = field(default_factory=list)
    """Objects transitively affected (depth > 1)."""
    
    depth_map: dict[str, int] = field(default_factory=dict)
    """Map of affected object → depth from source."""
    
    by_type: dict[str, list[str]] = field(default_factory=dict)
    """Affected objects grouped by type (table, view, column, etc.)."""
    
    critical_paths: list[list[str]] = field(default_factory=list)
    """Critical paths from source to leaf nodes."""
    
    max_depth: int = 0
    """Maximum depth reached in traversal."""

    changed_tables: list[str] = field(default_factory=list)
    """Tables identified as changed by ``--from-diff``."""

    migration_files: list[str] = field(default_factory=list)
    """Migration ``.sql`` files changed in the diff."""

    @property
    def total_count(self) -> int:
        """Total number of affected objects (excluding source)."""
        return len(self.direct) + len(self.transitive)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'object_id': self.object_id,
            'direct': self.direct,
            'transitive': self.transitive,
            'depth_map': self.depth_map,
            'by_type': self.by_type,
            'critical_paths': self.critical_paths,
            'max_depth': self.max_depth,
            'total_count': self.total_count,
            'changed_tables': self.changed_tables,
            'migration_files': self.migration_files,
        }


def merge_impact_results(
    results: list[ImpactResult],
    changed_tables: list[str] | None = None,
    migration_files: list[str] | None = None,
) -> ImpactResult:
    """Merge multiple ``ImpactResult`` instances into a consolidated report.

    Parameters
    ----------
    results:
        Individual impact results, one per source table.
    changed_tables:
        Tables identified as changed (e.g. from ``--from-diff``).
    migration_files:
        Migration files that triggered the analysis.

    Returns
    -------
    A single ``ImpactResult`` with unioned fields.
    """
    direct: set[str] = set()
    transitive: set[str] = set()
    depth_map: dict[str, int] = {}
    by_type: dict[str, set[str]] = {}
    critical_paths: list[list[str]] = []
    max_depth = 0

    for r in results:
        direct.update(r.direct)
        transitive.update(r.transitive)
        depth_map.update(r.depth_map)
        for t, nodes in r.by_type.items():
            by_type.setdefault(t, set()).update(nodes)
        critical_paths.extend(r.critical_paths)
        if r.max_depth > max_depth:
            max_depth = r.max_depth

    return ImpactResult(
        object_id="__from_diff__",
        direct=sorted(direct),
        transitive=sorted(transitive),
        depth_map=depth_map,
        by_type={t: sorted(n) for t, n in by_type.items()},
        critical_paths=critical_paths,
        max_depth=max_depth,
        changed_tables=sorted(changed_tables) if changed_tables else [],
        migration_files=sorted(migration_files) if migration_files else [],
    )


def analyze_impact(
    graph: nx.Graph[Any] | nx.DiGraph[Any],
    object_id: str,
    max_depth: int = 5,
    follow_direction: str = 'out'
) -> ImpactResult:
    """
    Find all objects affected by changes to object_id.
    
    Uses BFS to traverse the dependency graph and identify all affected
    objects. Handles circular dependencies gracefully by tracking visited nodes.
    
    Args:
        graph: NetworkX graph with schema objects as nodes
        object_id: Node ID to analyze (e.g., 'APP.USERS', 'APP.USERS.EMAIL')
        max_depth: Maximum traversal depth (default: 5)
        follow_direction: 'out' (successors, default) or 'in' (predecessors)
    
    Returns:
        ImpactResult with affected objects grouped by depth and type
    
    Examples:
        >>> result = analyze_impact(graph, 'APP.USERS')
        >>> print(f"Direct: {result.direct}")
        >>> print(f"Transitive: {result.transitive}")
        >>> print(f"By type: {result.by_type}")
    """
    # Validate input
    if object_id not in graph.nodes:
        return ImpactResult(
            object_id=object_id,
            direct=[],
            transitive=[],
            depth_map={},
            by_type={},
            critical_paths=[],
            max_depth=0,
        )
    
    # BFS traversal
    visited: set[str] = {object_id}
    depth_map: dict[str, int] = {}
    parent_map: dict[str, str | None] = {object_id: None}
    queue: deque[tuple[str, int]] = deque([(object_id, 0)])
    
    # Choose neighbor function based on direction
    if isinstance(graph, nx.DiGraph):
        get_neighbors = graph.successors if follow_direction == 'out' else graph.predecessors
    else:
        get_neighbors = graph.neighbors
    
    while queue:
        current, depth = queue.popleft()
        
        if depth >= max_depth:
            continue
        
        for neighbor in get_neighbors(current):
            if neighbor not in visited:
                visited.add(neighbor)
                new_depth = depth + 1
                depth_map[neighbor] = new_depth
                parent_map[neighbor] = current
                queue.append((neighbor, new_depth))
    
    # Separate direct vs transitive
    direct = [n for n, d in depth_map.items() if d == 1]
    transitive = [n for n, d in depth_map.items() if d > 1]
    
    # Group by object type
    by_type: dict[str, list[str]] = {}
    for node in list(depth_map.keys()):
        node_type = graph.nodes[node].get('type', 'unknown')
        if node_type not in by_type:
            by_type[node_type] = []
        by_type[node_type].append(node)
    
    # Find critical paths (paths to leaf nodes)
    critical_paths = _find_critical_paths(graph, object_id, depth_map, parent_map, get_neighbors)
    
    # Compute max depth
    max_depth_reached = max(depth_map.values()) if depth_map else 0
    
    return ImpactResult(
        object_id=object_id,
        direct=direct,
        transitive=transitive,
        depth_map=depth_map,
        by_type=by_type,
        critical_paths=critical_paths,
        max_depth=max_depth_reached,
    )


def _find_critical_paths(
    graph: nx.Graph[Any] | nx.DiGraph[Any],
    source: str,
    depth_map: dict[str, int],
    parent_map: dict[str, str | None],
    get_neighbors: Any
) -> list[list[str]]:
    """
    Find critical paths from source to leaf nodes.
    
    A critical path is a path from the source to a node with no affected
    descendants (a leaf in the affected subgraph).
    
    Args:
        graph: NetworkX graph
        source: Source node ID
        depth_map: Map of node → depth from source
        parent_map: Map of node → parent node
        get_neighbors: Function to get neighbors (successors or predecessors)
    
    Returns:
        List of paths, where each path is a list of node IDs from source to leaf
    """
    # Find leaf nodes (nodes in depth_map with no affected descendants)
    affected_nodes = set(depth_map.keys())
    leaf_nodes = []
    
    for node in affected_nodes:
        has_affected_child = False
        for neighbor in get_neighbors(node):
            if neighbor in affected_nodes:
                has_affected_child = True
                break
        if not has_affected_child:
            leaf_nodes.append(node)
    
    # For each leaf, trace path back to source
    paths = []
    for leaf in leaf_nodes:
        path = []
        current: str | None = leaf
        
        while current is not None and current != source:
            path.append(current)
            current = parent_map.get(current)
        
        if current == source:
            path.append(source)
            path.reverse()
            paths.append(path)
    
    return paths


def format_impact_text(result: ImpactResult, graph: nx.Graph[Any] | nx.DiGraph[Any]) -> str:
    """
    Format impact analysis result as human-readable text.
    
    Args:
        result: Impact analysis result
        graph: NetworkX graph (for node attributes)
    
    Returns:
        Formatted text output
    """
    lines = [
        f"Impact Analysis: {result.object_id}",
        "=" * (17 + len(result.object_id)),
        "",
    ]
    
    if result.total_count == 0:
        lines.append("No affected objects found.")
        return "\n".join(lines)
    
    lines.append(f"Total affected: {result.total_count} objects")
    lines.append(f"Max depth: {result.max_depth}")
    lines.append("")
    
    # Direct dependencies
    if result.direct:
        lines.append(f"Direct dependencies ({len(result.direct)}):")
        for node in sorted(result.direct):
            node_type = graph.nodes[node].get('type', 'unknown')
            lines.append(f"  - {node} ({node_type})")
        lines.append("")
    
    # Transitive dependencies
    if result.transitive:
        lines.append(f"Transitive dependencies ({len(result.transitive)}):")
        # Group by depth
        by_depth: dict[int, list[str]] = {}
        for node, depth in result.depth_map.items():
            if depth > 1:
                if depth not in by_depth:
                    by_depth[depth] = []
                by_depth[depth].append(node)
        
        for depth in sorted(by_depth.keys()):
            nodes = sorted(by_depth[depth])
            lines.append(f"  Depth {depth}:")
            for node in nodes:
                node_type = graph.nodes[node].get('type', 'unknown')
                lines.append(f"    - {node} ({node_type})")
        lines.append("")
    
    # By type summary
    if result.by_type:
        lines.append("By object type:")
        for obj_type, nodes in sorted(result.by_type.items()):
            lines.append(f"  {obj_type}: {len(nodes)}")
        lines.append("")
    
    # Critical paths
    if result.critical_paths:
        lines.append(f"Critical paths ({len(result.critical_paths)}):")
        for i, path in enumerate(result.critical_paths[:5], 1):  # Show first 5
            path_str = " → ".join(path)
            lines.append(f"  {i}. {path_str}")
        if len(result.critical_paths) > 5:
            lines.append(f"  ... and {len(result.critical_paths) - 5} more")
        lines.append("")
    
    return "\n".join(lines)


def format_impact_json(result: ImpactResult) -> str:
    """
    Format impact analysis result as JSON.
    
    Args:
        result: Impact analysis result
    
    Returns:
        JSON string
    """
    from ..models import ImpactResult as _ImpactResult
    model = _ImpactResult(
        object_id=result.object_id,
        direct=result.direct,
        transitive=result.transitive,
        depth_map=result.depth_map,
        by_type=result.by_type,
        critical_paths=result.critical_paths,
        max_depth=result.max_depth,
        total_count=result.total_count,
    )
    return model.model_dump_json(by_alias=True, indent=2)


def format_impact_from_diff_text(
    result: ImpactResult,
    graph: nx.Graph[Any] | nx.DiGraph[Any],
    ref_display: str = "diff",
) -> str:
    """Human-readable text output for ``--from-diff`` mode."""
    lines: list[str] = []

    lines.append(f"Changed by diff ({ref_display}):")
    for f in result.migration_files:
        lines.append(f"  {f}")
    lines.append("")

    if result.changed_tables:
        lines.append("Downstream impact:")
        for tbl in sorted(result.changed_tables):
            lines.append(f"  {tbl} (changed)")
            direct_for_tbl = [
                n for n in result.depth_map
                if result.depth_map.get(n) == 1
                and n != tbl
            ]
            for affected in sorted(direct_for_tbl):
                if graph.has_edge(tbl, affected):
                    edge_data = graph.get_edge_data(tbl, affected)
                    label = ""
                    if edge_data:
                        for _key, data in edge_data.items() if isinstance(edge_data, dict) else [(None, edge_data)]:
                            rel = data.get("relationship", "") if isinstance(data, dict) else getattr(data, "relationship", "")
                            if rel == "foreign_key":
                                fk_cols = data.get("columns", "") if isinstance(data, dict) else getattr(data, "columns", "")
                                if fk_cols:
                                    label = f" (FK: {fk_cols})"
                                else:
                                    label = " (FK)"
                            break
                    lines.append(f"    └─ {affected}{label}")
        lines.append("")

    downstream_total = result.total_count
    lines.append(
        f"Summary: {len(result.changed_tables)} changed table(s), "
        f"{downstream_total} downstream table(s) affected."
    )

    return "\n".join(lines)


def format_impact_from_diff_json(
    result: ImpactResult,
    ref_display: str = "diff",
) -> str:
    """JSON output for ``--from-diff`` mode using the ``ImpactV1`` contract."""
    from ..contracts.impact.v1 import ImpactV1

    model = ImpactV1(
        object_id=result.object_id,
        direct=result.direct,
        transitive=result.transitive,
        depth_map=result.depth_map,
        by_type=result.by_type,
        critical_paths=result.critical_paths,
        max_depth=result.max_depth,
        total_count=result.total_count,
        changed_tables=result.changed_tables,
        migration_files=result.migration_files,
    )
    return model.model_dump_json(by_alias=True, indent=2)

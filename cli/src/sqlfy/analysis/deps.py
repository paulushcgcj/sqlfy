"""
sqlfy.analysis.deps
===================
Migration dependency analysis and validation.

Analyzes migration dependencies to detect:
- Circular dependencies (impossible migration order)
- Unreferenced objects (migrations reference tables not yet created)
- Parallel-safe migrations (can run concurrently)
- Critical path (longest dependency chain)
- Dependency validation errors

This builds on migration_graph.build_migration_graph() to provide
advanced NetworkX-based analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import json
import sys

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False


# ─────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────

@dataclass
class DependencyIssue:
    """Represents a dependency validation issue."""
    severity: str  # 'error' | 'warning' | 'info'
    code: str
    message: str
    migrations: list[str] = field(default_factory=list)


@dataclass
class DependencyAnalysis:
    """Complete migration dependency analysis."""
    migrations: list[str]  # All migration versions
    total_dependencies: int  # Total dependency edges
    dependency_map: dict[str, list[str]]  # version → list of versions it depends on
    reverse_dependency_map: dict[str, list[str]]  # version → list of versions that depend on it
    circular_dependencies: list[list[str]]  # Circular dependency chains
    parallel_safe_sets: list[list[str]]  # Migrations that can run in parallel
    critical_path: list[str]  # Longest dependency chain
    issues: list[DependencyIssue]  # Validation issues
    unreferenced_objects: list[tuple[str, str]]  # (migration, object) pairs for objects never created


# ─────────────────────────────────────────────
# CORE ANALYSIS
# ─────────────────────────────────────────────

def analyze_dependencies(migrations_dir: Path) -> DependencyAnalysis:
    """
    Analyze migration dependencies.
    
    Args:
        migrations_dir: Path to migrations directory
    
    Returns:
        DependencyAnalysis with validation results
    """
    if not HAS_NETWORKX:
        raise ImportError(
            "NetworkX is required for dependency analysis. "
            "Install with: pip install networkx"
        )
    
    # Import here to avoid circular dependency
    from ..migration_graph import build_migration_graph
    
    # Load migration files directly
    files_data = []
    for file_path in sorted(migrations_dir.glob('*.sql')):
        with open(file_path, 'r', encoding='utf-8') as f:
            files_data.append({
                'filename': file_path.name,
                'sql': f.read()
            })
    
    if not files_data:
        return DependencyAnalysis(
            migrations=[],
            total_dependencies=0,
            dependency_map={},
            reverse_dependency_map={},
            circular_dependencies=[],
            parallel_safe_sets=[],
            critical_path=[],
            issues=[],
            unreferenced_objects=[]
        )
    
    # Build migration graph
    graph = build_migration_graph(files_data)
    
    # Build NetworkX directed graph for analysis
    G = nx.DiGraph()
    
    # Add all migration nodes
    for version in graph.nodes.keys():
        G.add_node(version)
    
    # Add dependency edges (from_version depends on to_version, so edge goes from to → from)
    for from_version, to_version in graph.edges:
        G.add_edge(from_version, to_version)
    
    # Build dependency maps
    dependency_map = {version: sorted(node.dependencies) for version, node in graph.nodes.items()}
    reverse_dependency_map = {version: [] for version in graph.nodes.keys()}
    for version, deps in dependency_map.items():
        for dep_version in deps:
            reverse_dependency_map[dep_version].append(version)
    for version in reverse_dependency_map:
        reverse_dependency_map[version] = sorted(reverse_dependency_map[version])
    
    # Detect circular dependencies
    circular_dependencies = []
    try:
        cycles = list(nx.simple_cycles(G))
        circular_dependencies = cycles
    except Exception:
        pass
    
    # Find parallel-safe sets (topological layers)
    parallel_safe_sets = []
    if not circular_dependencies:
        try:
            for generation in nx.topological_generations(G):
                parallel_safe_sets.append(sorted(generation))
        except nx.NetworkXError:
            # Graph has cycles, cannot do topological sort
            pass
    
    # Find critical path (longest path in DAG)
    critical_path = []
    if not circular_dependencies:
        try:
            critical_path = nx.dag_longest_path(G)
        except Exception:
            pass
    
    # Validate dependencies and collect issues
    issues = []
    unreferenced_objects = []
    
    # Check for circular dependencies
    if circular_dependencies:
        for cycle in circular_dependencies:
            cycle_str = ' → '.join(cycle + [cycle[0]])
            issues.append(DependencyIssue(
                severity='error',
                code='CIRCULAR_DEPENDENCY',
                message=f'Circular dependency detected: {cycle_str}',
                migrations=cycle
            ))
    
    # Check for unreferenced objects (migrations reference objects never created)
    all_created_objects = set()
    for node in graph.nodes.values():
        for table in node.creates:
            all_created_objects.add(table)
    
    for version, node in graph.nodes.items():
        for table in node.references:
            if table not in all_created_objects:
                unreferenced_objects.append((version, table))
                issues.append(DependencyIssue(
                    severity='error',
                    code='UNREFERENCED_OBJECT',
                    message=f'Migration {version} references table {table} that is never created',
                    migrations=[version]
                ))
        
        for table in node.alters:
            if table not in all_created_objects:
                unreferenced_objects.append((version, table))
                issues.append(DependencyIssue(
                    severity='error',
                    code='UNREFERENCED_OBJECT',
                    message=f'Migration {version} alters table {table} that is never created',
                    migrations=[version]
                ))
    
    # Check for migrations with no dependencies (isolated migrations)
    for version, node in graph.nodes.items():
        if not node.dependencies and not node.creates:
            issues.append(DependencyIssue(
                severity='warning',
                code='ISOLATED_MIGRATION',
                message=f'Migration {version} has no dependencies and creates no objects',
                migrations=[version]
            ))
    
    return DependencyAnalysis(
        migrations=sorted(graph.nodes.keys()),
        total_dependencies=len(graph.edges),
        dependency_map=dependency_map,
        reverse_dependency_map=reverse_dependency_map,
        circular_dependencies=circular_dependencies,
        parallel_safe_sets=parallel_safe_sets,
        critical_path=critical_path,
        issues=issues,
        unreferenced_objects=unreferenced_objects
    )


# ─────────────────────────────────────────────
# FORMATTERS
# ─────────────────────────────────────────────

def format_text(analysis: DependencyAnalysis, show_details: bool = True) -> str:
    """
    Format dependency analysis as human-readable text.
    
    Args:
        analysis: DependencyAnalysis results
        show_details: Whether to show detailed dependency information
    
    Returns:
        Formatted text output
    """
    lines = []
    lines.append("Migration Dependency Analysis")
    lines.append("=" * 50)
    lines.append("")
    
    # Summary statistics
    lines.append(f"Total Migrations: {len(analysis.migrations)}")
    lines.append(f"Total Dependencies: {analysis.total_dependencies}")
    lines.append(f"Circular Dependencies: {len(analysis.circular_dependencies)}")
    lines.append(f"Parallel-Safe Sets: {len(analysis.parallel_safe_sets)}")
    lines.append(f"Critical Path Length: {len(analysis.critical_path)}")
    lines.append("")
    
    # Issues summary
    error_count = sum(1 for issue in analysis.issues if issue.severity == 'error')
    warning_count = sum(1 for issue in analysis.issues if issue.severity == 'warning')
    info_count = sum(1 for issue in analysis.issues if issue.severity == 'info')
    
    lines.append(f"Issues Found: {len(analysis.issues)} total")
    if error_count > 0:
        lines.append(f"  ❌ {error_count} error(s)")
    if warning_count > 0:
        lines.append(f"  ⚠️  {warning_count} warning(s)")
    if info_count > 0:
        lines.append(f"  ℹ️  {info_count} info")
    if len(analysis.issues) == 0:
        lines.append("  ✅ No issues found")
    lines.append("")
    
    # Critical path
    if analysis.critical_path:
        lines.append("Critical Path (Longest Dependency Chain)")
        lines.append("-" * 50)
        lines.append(" → ".join(analysis.critical_path))
        lines.append(f"({len(analysis.critical_path)} migrations must run sequentially)")
        lines.append("")
    
    # Parallel-safe sets
    if analysis.parallel_safe_sets:
        lines.append("Parallel-Safe Migration Sets")
        lines.append("-" * 50)
        for i, pset in enumerate(analysis.parallel_safe_sets, 1):
            if len(pset) > 1:
                lines.append(f"Layer {i}: {', '.join(pset)} (can run in parallel)")
            else:
                lines.append(f"Layer {i}: {pset[0]}")
        lines.append("")
    
    # Detailed dependency information
    if show_details:
        lines.append("Migration Dependencies")
        lines.append("-" * 50)
        for version in analysis.migrations:
            deps = analysis.dependency_map.get(version, [])
            rev_deps = analysis.reverse_dependency_map.get(version, [])
            
            lines.append(f"\n{version}")
            if deps:
                lines.append(f"  Depends on: {', '.join(deps)}")
            else:
                lines.append(f"  Depends on: (none)")
            
            if rev_deps:
                lines.append(f"  Required by: {', '.join(rev_deps)}")
            else:
                lines.append(f"  Required by: (none)")
        lines.append("")
    
    # Issues detail
    if analysis.issues:
        lines.append("Issues Detail")
        lines.append("-" * 50)
        
        # Group by severity
        errors = [i for i in analysis.issues if i.severity == 'error']
        warnings = [i for i in analysis.issues if i.severity == 'warning']
        infos = [i for i in analysis.issues if i.severity == 'info']
        
        if errors:
            lines.append("\nERRORS:")
            for issue in errors:
                lines.append(f"  [{issue.code}] {issue.message}")
        
        if warnings:
            lines.append("\nWARNINGS:")
            for issue in warnings:
                lines.append(f"  [{issue.code}] {issue.message}")
        
        if infos:
            lines.append("\nINFO:")
            for issue in infos:
                lines.append(f"  [{issue.code}] {issue.message}")
        
        lines.append("")
    
    return "\n".join(lines)


def format_json(analysis: DependencyAnalysis) -> str:
    """
    Format dependency analysis as JSON.
    
    Args:
        analysis: DependencyAnalysis results
    
    Returns:
        JSON string
    """
    data = {
        "summary": {
            "total_migrations": len(analysis.migrations),
            "total_dependencies": analysis.total_dependencies,
            "circular_dependencies_count": len(analysis.circular_dependencies),
            "parallel_safe_sets_count": len(analysis.parallel_safe_sets),
            "critical_path_length": len(analysis.critical_path),
            "issues_count": len(analysis.issues)
        },
        "migrations": analysis.migrations,
        "dependency_map": analysis.dependency_map,
        "reverse_dependency_map": analysis.reverse_dependency_map,
        "circular_dependencies": analysis.circular_dependencies,
        "parallel_safe_sets": analysis.parallel_safe_sets,
        "critical_path": analysis.critical_path,
        "issues": [
            {
                "severity": issue.severity,
                "code": issue.code,
                "message": issue.message,
                "migrations": issue.migrations
            }
            for issue in analysis.issues
        ],
        "unreferenced_objects": [
            {"migration": migration, "object": obj}
            for migration, obj in analysis.unreferenced_objects
        ]
    }
    return json.dumps(data, indent=2)


def format_dot(analysis: DependencyAnalysis) -> str:
    """
    Format dependency analysis as Graphviz DOT format.
    
    Args:
        analysis: DependencyAnalysis results
    
    Returns:
        DOT format string
    """
    lines = ['digraph MigrationDependencies {']
    lines.append('  rankdir=LR;')
    lines.append('  node [shape=box, style="rounded,filled"];')
    lines.append('')
    
    # Determine node colors based on issues
    problematic_migrations = set()
    for issue in analysis.issues:
        if issue.severity == 'error':
            problematic_migrations.update(issue.migrations)
    
    # Add nodes
    for version in analysis.migrations:
        if version in problematic_migrations:
            color = 'salmon'  # Error
        elif version in analysis.critical_path:
            color = 'gold'  # On critical path
        else:
            color = 'lightblue'
        
        lines.append(f'  "{version}" [fillcolor={color}];')
    
    lines.append('')
    
    # Add edges from dependency_map
    for version, deps in analysis.dependency_map.items():
        for dep_version in deps:
            lines.append(f'  "{dep_version}" -> "{version}";')
    
    # Highlight critical path
    if analysis.critical_path and len(analysis.critical_path) > 1:
        lines.append('')
        lines.append('  // Critical path')
        for i in range(len(analysis.critical_path) - 1):
            from_ver = analysis.critical_path[i]
            to_ver = analysis.critical_path[i + 1]
            lines.append(f'  "{from_ver}" -> "{to_ver}" [color=red, penwidth=2];')
    
    # Add legend
    lines.append('')
    lines.append('  // Legend')
    lines.append('  subgraph cluster_legend {')
    lines.append('    label="Legend";')
    lines.append('    style=dashed;')
    lines.append('    legend_error [label="Error", fillcolor=salmon, shape=box, style="rounded,filled"];')
    lines.append('    legend_critical [label="Critical Path", fillcolor=gold, shape=box, style="rounded,filled"];')
    lines.append('    legend_normal [label="Normal", fillcolor=lightblue, shape=box, style="rounded,filled"];')
    lines.append('  }')
    
    lines.append('}')
    return '\n'.join(lines)


# ─────────────────────────────────────────────
# VALIDATION
# ─────────────────────────────────────────────

def validate_dependencies(analysis: DependencyAnalysis, strict: bool = False) -> tuple[bool, str]:
    """
    Validate migration dependencies.
    
    Args:
        analysis: DependencyAnalysis results
        strict: If True, warnings are treated as errors
    
    Returns:
        (is_valid, summary_message)
    """
    error_count = sum(1 for issue in analysis.issues if issue.severity == 'error')
    warning_count = sum(1 for issue in analysis.issues if issue.severity == 'warning')
    
    if strict:
        is_valid = error_count == 0 and warning_count == 0
        if is_valid:
            return True, "✅ All dependencies valid (strict mode)"
        else:
            return False, f"❌ Found {error_count} error(s) and {warning_count} warning(s) (strict mode)"
    else:
        is_valid = error_count == 0
        if is_valid:
            if warning_count > 0:
                return True, f"⚠️  Dependencies valid with {warning_count} warning(s)"
            else:
                return True, "✅ All dependencies valid"
        else:
            return False, f"❌ Found {error_count} error(s)"

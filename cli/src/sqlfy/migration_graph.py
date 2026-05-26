"""
sqlfy.migration_graph
=====================
Migration timeline and dependency graph visualization.

Generates:
- DOT format (Graphviz) for static diagrams
- HTML format (vis.js) for interactive exploration
- Timeline format for chronological view

Dependency detection:
- CREATE TABLE → no dependencies
- ALTER TABLE → depends on migrations that created the table
- CREATE VIEW → depends on tables used in the view
- Foreign keys → depends on referenced tables
"""

from __future__ import annotations

import re
import json
from pathlib import Path
from typing import Optional, NamedTuple
from dataclasses import dataclass
from datetime import datetime

import sqlglot
import sqlglot.expressions as exp

# Suppress sqlglot warnings
import logging
logging.getLogger("sqlglot").setLevel(logging.CRITICAL)


# ─────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────

@dataclass
class MigrationNode:
    """Represents a single migration in the dependency graph."""
    version: str
    description: str
    filename: str
    timestamp: Optional[datetime]
    creates: list[str]  # Tables/views created by this migration
    alters: list[str]   # Tables altered by this migration
    references: list[str]  # Tables referenced (views, foreign keys)
    dependencies: list[str]  # Versions this migration depends on
    sql: str


@dataclass
class MigrationGraph:
    """Complete migration dependency graph."""
    nodes: dict[str, MigrationNode]
    edges: list[tuple[str, str]]  # (from_version, to_version)


# ─────────────────────────────────────────────
# MIGRATION PARSING
# ─────────────────────────────────────────────

def _extract_reference_table(ref) -> Optional[str]:
    """
    Extract table name from a Reference node.
    
    The structure can be:
      - Reference -> Schema -> Table -> Identifier
      - Reference -> Table -> Identifier
      - Direct table name string
    """
    if not ref:
        return None
    
    # Try various levels of nesting
    current = ref
    for _ in range(5):  # Max depth to avoid infinite loops
        if hasattr(current, 'name'):
            name = current.name if isinstance(current.name, str) else str(current.name)
            if name and name != '':
                return name
        if hasattr(current, 'this'):
            current = current.this
        else:
            break
    
    return None


def parse_migration_filename(filename: str) -> tuple[str, str, Optional[datetime]]:
    """
    Parse Flyway-style migration filename.
    
    Examples:
        V1__create_users.sql → ("V1", "create users", None)
        V2.1__add_email.sql → ("V2.1", "add email", None)
        V20260101120000__add_index.sql → ("V20260101120000", "add index", datetime(...))
    
    Returns:
        (version, description, timestamp)
    """
    # Match Vx__, Vx.y__, or Vyyyymmddhhmmss__
    match = re.match(r'^V([0-9._]+)__(.+)\.sql$', filename, re.IGNORECASE)
    if not match:
        return filename, filename, None
    
    version = match.group(1)
    description = match.group(2).replace('_', ' ')
    
    # Try to parse timestamp from version (format: yyyymmddhhmmss)
    timestamp = None
    if version.isdigit() and len(version) == 14:
        try:
            timestamp = datetime.strptime(version, '%Y%m%d%H%M%S')
        except ValueError:
            pass
    
    return f"V{version}", description, timestamp


def extract_table_operations(sql: str) -> tuple[list[str], list[str], list[str]]:
    """
    Extract tables created, altered, and referenced from SQL.
    
    Returns:
        (creates, alters, references)
        - creates: Tables/views created
        - alters: Tables modified
        - references: Tables referenced (views, foreign keys)
    """
    creates = []
    alters = []
    references = []
    
    try:
        statements = sqlglot.parse(sql, dialect='oracle')
        
        for stmt in statements:
            if isinstance(stmt, exp.Create):
                # CREATE TABLE or CREATE VIEW
                # stmt.this is usually a Schema node for CREATE TABLE
                table = stmt.this
                table_name = None
                
                if hasattr(table, 'this') and hasattr(table.this, 'name'):
                    # Schema node: table.this.name contains the table name
                    table_name = table.this.name
                elif hasattr(table, 'name'):
                    # Direct Table node
                    table_name = table.name
                
                if table_name:
                    table_name = table_name if isinstance(table_name, str) else str(table_name)
                    if table_name:
                        creates.append(table_name.upper())
                
                # Walk AST to find foreign keys (in CREATE TABLE)
                for node in stmt.walk():
                    if isinstance(node, exp.ForeignKey):
                        ref = node.args.get('reference')
                        if ref:
                            ref_table_name = _extract_reference_table(ref)
                            if ref_table_name:
                                references.append(ref_table_name.upper())
                
                # For views, extract referenced tables
                if stmt.kind == 'VIEW':
                    for node in stmt.walk():
                        if isinstance(node, exp.Table):
                            if hasattr(node, 'name'):
                                ref_name = node.name if isinstance(node.name, str) else str(node.name)
                                if ref_name:
                                    references.append(ref_name.upper())
            
            elif isinstance(stmt, exp.AlterTable):
                # ALTER TABLE
                table = stmt.this
                table_name = None
                
                if hasattr(table, 'this') and hasattr(table.this, 'name'):
                    table_name = table.this.name
                elif hasattr(table, 'name'):
                    table_name = table.name
                
                if table_name:
                    table_name = table_name if isinstance(table_name, str) else str(table_name)
                    if table_name:
                        alters.append(table_name.upper())
                
                # Check for foreign keys in ALTER
                for action in stmt.expressions:
                    if isinstance(action, exp.ForeignKey):
                        ref = action.args.get('reference')
                        if ref:
                            # Extract referenced table name from nested structure
                            ref_table_name = _extract_reference_table(ref)
                            if ref_table_name:
                                references.append(ref_table_name.upper())
            
            elif isinstance(stmt, exp.Drop):
                # DROP TABLE (treated as alter for dependency purposes)
                table = stmt.this
                table_name = None
                
                if hasattr(table, 'this') and hasattr(table.this, 'name'):
                    table_name = table.this.name
                elif hasattr(table, 'name'):
                    table_name = table.name
                
                if table_name:
                    table_name = table_name if isinstance(table_name, str) else str(table_name)
                    if table_name:
                        alters.append(table_name.upper())
    
    except Exception:
        # Fallback to regex parsing if sqlglot fails
        creates.extend(_extract_creates_regex(sql))
        alters.extend(_extract_alters_regex(sql))
        references.extend(_extract_references_regex(sql))
    
    return (
        list(dict.fromkeys([c for c in creates if c])),  # Remove duplicates and empty strings
        list(dict.fromkeys([a for a in alters if a])),
        list(dict.fromkeys([r for r in references if r]))
    )


def _extract_creates_regex(sql: str) -> list[str]:
    """Fallback regex extraction for CREATE statements."""
    tables = []
    for match in re.finditer(r'CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW)\s+([A-Z_][A-Z0-9_]*)', sql, re.IGNORECASE):
        tables.append(match.group(1).upper())
    return tables


def _extract_alters_regex(sql: str) -> list[str]:
    """Fallback regex extraction for ALTER statements."""
    tables = []
    for match in re.finditer(r'ALTER\s+TABLE\s+([A-Z_][A-Z0-9_]*)', sql, re.IGNORECASE):
        tables.append(match.group(1).upper())
    for match in re.finditer(r'DROP\s+TABLE\s+([A-Z_][A-Z0-9_]*)', sql, re.IGNORECASE):
        tables.append(match.group(1).upper())
    return tables


def _extract_references_regex(sql: str) -> list[str]:
    """Fallback regex extraction for table references."""
    tables = []
    # Foreign key references
    for match in re.finditer(r'REFERENCES\s+([A-Z_][A-Z0-9_]*)', sql, re.IGNORECASE):
        tables.append(match.group(1).upper())
    return tables


# ─────────────────────────────────────────────
# DEPENDENCY RESOLUTION
# ─────────────────────────────────────────────

def build_migration_graph(files: list[dict]) -> MigrationGraph:
    """
    Build dependency graph from migration files.
    
    Args:
        files: List of {filename, sql} dicts
    
    Returns:
        MigrationGraph with nodes and edges
    """
    nodes = {}
    table_creators = {}  # table_name → version
    
    # First pass: parse all migrations
    for file_data in files:
        filename = file_data['filename']
        sql = file_data['sql']
        
        version, description, timestamp = parse_migration_filename(filename)
        creates, alters, references = extract_table_operations(sql)
        
        node = MigrationNode(
            version=version,
            description=description,
            filename=filename,
            timestamp=timestamp,
            creates=creates,
            alters=alters,
            references=references,
            dependencies=[],
            sql=sql
        )
        nodes[version] = node
        
        # Track which migration created each table
        for table in creates:
            table_creators[table] = version
    
    # Second pass: resolve dependencies
    edges = []
    for version, node in nodes.items():
        deps = set()
        
        # Depend on migrations that created tables we alter
        for table in node.alters:
            if table in table_creators:
                creator_version = table_creators[table]
                if creator_version != version:
                    deps.add(creator_version)
        
        # Depend on migrations that created tables we reference
        for table in node.references:
            if table in table_creators:
                creator_version = table_creators[table]
                if creator_version != version:
                    deps.add(creator_version)
        
        node.dependencies = sorted(deps)
        
        # Add edges
        for dep_version in node.dependencies:
            edges.append((dep_version, version))
    
    return MigrationGraph(nodes=nodes, edges=edges)


# ─────────────────────────────────────────────
# OUTPUT FORMATTERS
# ─────────────────────────────────────────────

def format_dot(graph: MigrationGraph) -> str:
    """Generate Graphviz DOT format."""
    lines = ['digraph MigrationGraph {']
    lines.append('  rankdir=LR;')
    lines.append('  node [shape=box, style=rounded];')
    lines.append('')
    
    # Nodes
    for version, node in sorted(graph.nodes.items()):
        label = f"{version}\\n{node.description}"
        if node.timestamp:
            label += f"\\n{node.timestamp.strftime('%Y-%m-%d')}"
        
        # Color based on operations
        color = 'lightblue'
        if node.creates:
            color = 'lightgreen'
        elif node.alters:
            color = 'lightyellow'
        
        lines.append(f'  "{version}" [label="{label}", fillcolor={color}, style="filled,rounded"];')
    
    lines.append('')
    
    # Edges
    for from_ver, to_ver in graph.edges:
        lines.append(f'  "{from_ver}" -> "{to_ver}";')
    
    lines.append('}')
    return '\n'.join(lines)


def format_html(graph: MigrationGraph) -> str:
    """Generate interactive HTML visualization using vis.js."""
    
    # Build nodes and edges for vis.js
    vis_nodes = []
    for version, node in graph.nodes.items():
        label = f"{version}\n{node.description}"
        
        # Color based on operations
        color = '#9fc5e8'  # light blue
        if node.creates:
            color = '#b6d7a8'  # light green
        elif node.alters:
            color = '#ffe599'  # light yellow
        
        vis_nodes.append({
            'id': version,
            'label': label,
            'color': color,
            'shape': 'box',
            'title': f"<b>{version}</b><br>{node.description}<br><br>"
                     f"Creates: {', '.join(node.creates) or 'none'}<br>"
                     f"Alters: {', '.join(node.alters) or 'none'}<br>"
                     f"References: {', '.join(node.references) or 'none'}<br>"
                     f"Dependencies: {', '.join(node.dependencies) or 'none'}"
        })
    
    vis_edges = []
    for from_ver, to_ver in graph.edges:
        vis_edges.append({
            'from': from_ver,
            'to': to_ver,
            'arrows': 'to',
            'color': {'color': '#848484'}
        })
    
    html = f"""<!DOCTYPE html>
<html>
<head>
  <title>Migration Graph</title>
  <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style>
    body {{
      font-family: Arial, sans-serif;
      margin: 0;
      padding: 20px;
      background: #f5f5f5;
    }}
    #mynetwork {{
      width: 100%;
      height: 80vh;
      border: 1px solid #ddd;
      background: white;
    }}
    .header {{
      margin-bottom: 20px;
    }}
    h1 {{
      margin: 0 0 10px 0;
      color: #333;
    }}
    .stats {{
      color: #666;
      font-size: 14px;
    }}
  </style>
</head>
<body>
  <div class="header">
    <h1>Migration Dependency Graph</h1>
    <div class="stats">
      {len(graph.nodes)} migrations • {len(graph.edges)} dependencies
    </div>
  </div>
  <div id="mynetwork"></div>
  <script type="text/javascript">
    var nodes = new vis.DataSet({json.dumps(vis_nodes)});
    var edges = new vis.DataSet({json.dumps(vis_edges)});
    
    var container = document.getElementById('mynetwork');
    var data = {{
      nodes: nodes,
      edges: edges
    }};
    var options = {{
      layout: {{
        hierarchical: {{
          direction: 'LR',
          sortMethod: 'directed',
          levelSeparation: 200,
          nodeSpacing: 150
        }}
      }},
      physics: false,
      nodes: {{
        font: {{
          size: 14,
          face: 'monospace'
        }},
        margin: 10
      }},
      edges: {{
        smooth: {{
          type: 'cubicBezier'
        }}
      }}
    }};
    
    var network = new vis.Network(container, data, options);
  </script>
</body>
</html>"""
    return html


def format_timeline(graph: MigrationGraph) -> str:
    """Generate text-based timeline view."""
    lines = ['Migration Timeline', '=' * 80, '']
    
    # Sort by version (assumes Flyway ordering)
    sorted_nodes = sorted(graph.nodes.items(), key=lambda x: x[0])
    
    for i, (version, node) in enumerate(sorted_nodes):
        # Vertical connector
        if i > 0:
            lines.append('  │')
        
        # Node
        lines.append(f'  ├─ {version}: {node.description}')
        
        if node.timestamp:
            lines.append(f'  │  Date: {node.timestamp.strftime("%Y-%m-%d %H:%M")}')
        
        if node.creates:
            lines.append(f'  │  Creates: {", ".join(node.creates)}')
        
        if node.alters:
            lines.append(f'  │  Alters: {", ".join(node.alters)}')
        
        if node.references:
            lines.append(f'  │  References: {", ".join(node.references)}')
        
        if node.dependencies:
            lines.append(f'  │  Depends on: {", ".join(node.dependencies)}')
        
        lines.append('  │')
    
    lines.append('  └─ (end)')
    lines.append('')
    lines.append(f'Total: {len(graph.nodes)} migrations, {len(graph.edges)} dependencies')
    
    return '\n'.join(lines)


def format_json(graph: MigrationGraph) -> str:
    """Generate JSON representation of the graph."""
    data = {
        'nodes': [
            {
                'version': node.version,
                'description': node.description,
                'filename': node.filename,
                'timestamp': node.timestamp.isoformat() if node.timestamp else None,
                'creates': node.creates,
                'alters': node.alters,
                'references': node.references,
                'dependencies': node.dependencies
            }
            for node in graph.nodes.values()
        ],
        'edges': [
            {'from': from_ver, 'to': to_ver}
            for from_ver, to_ver in graph.edges
        ],
        'stats': {
            'migration_count': len(graph.nodes),
            'dependency_count': len(graph.edges)
        }
    }
    return json.dumps(data, indent=2)

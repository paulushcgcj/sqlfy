"""
Example: NetworkX Graph Construction (Feature #1)

Demonstrates how to convert a SchemaGraph to NetworkX format and use graph algorithms.
"""

from pathlib import Path

from sqlfy.core import apply_migrations, build_networkx_graph
from sqlfy.validator import (
    validate_graph_structure,
    validate_node_types,
    validate_edge_relations,
)

# Example migrations directory
migrations_dir = Path("../samples")

# Build schema graph from migrations
print("🔨 Building schema graph from migrations...")

# Load migration files
migration_files = []
for path in sorted(migrations_dir.glob("*.sql")):
    migration_files.append({
        'filename': path.name,
        'sql': path.read_text(),
    })

schema_graph = apply_migrations(
    migration_files,
    dialect="oracle",
)

print(f"   Tables: {len(schema_graph.tables)}")
print(f"   Sequences: {len(schema_graph.seqs)}")
print(f"   FK relationships: {len(schema_graph.edges)}")
print()

# Convert to NetworkX
print("🕸️  Converting to NetworkX graph...")
G = build_networkx_graph(schema_graph, directed=False)

print(f"   Nodes: {G.number_of_nodes()}")
print(f"   Edges: {G.number_of_edges()}")
print()

# Validate graph structure
print("✅ Validating graph structure...")
warnings = validate_graph_structure(G)
if warnings:
    print("   Warnings:")
    for w in warnings:
        print(f"   - {w}")
else:
    print("   ✓ Graph is valid")
print()

# Analyze node types
print("📊 Node type distribution:")
node_types = validate_node_types(G)
for node_type, count in sorted(node_types.items()):
    print(f"   {node_type}: {count}")
print()

# Analyze edge relations
print("📊 Edge relation distribution:")
edge_relations = validate_edge_relations(G)
for relation, count in sorted(edge_relations.items()):
    print(f"   {relation}: {count}")
print()

# Example: Find all tables
print("📋 Tables in schema:")
for node, data in G.nodes(data=True):
    if data.get("type") == "table":
        print(f"   - {data['label']} (created in {data.get('created_in', 'unknown')})")
print()

# Example: Find all foreign key relationships
print("🔗 Foreign key relationships:")
for u, v, data in G.edges(data=True):
    if data.get("relation") == "foreign_key":
        print(f"   {u} -> {v}")
        print(f"      Columns: {data['from_cols']} -> {data['to_cols']}")
        if data.get("on_delete"):
            print(f"      On delete: {data['on_delete']}")
print()

# Example: Graph algorithms (NetworkX features)
print("🧮 Graph algorithms:")

# Degree centrality (which nodes are most connected?)
import networkx as nx

degree_centrality = nx.degree_centrality(G)
top_nodes = sorted(degree_centrality.items(), key=lambda x: x[1], reverse=True)[:5]
print("   Most connected nodes:")
for node, centrality in top_nodes:
    node_data = G.nodes[node]
    print(f"   - {node} ({node_data.get('type')}): {centrality:.3f}")
print()

# Connected components
components = list(nx.connected_components(G))
print(f"   Connected components: {len(components)}")
print(f"   Largest component size: {len(max(components, key=len))}")
print()

# Shortest path example (if we have at least 2 tables)
tables = [n for n, d in G.nodes(data=True) if d.get("type") == "table"]
if len(tables) >= 2:
    try:
        path = nx.shortest_path(G, tables[0], tables[1])
        print(f"   Shortest path from {tables[0]} to {tables[1]}:")
        print(f"   {' -> '.join(path)}")
    except nx.NetworkXNoPath:
        print(f"   No path between {tables[0]} and {tables[1]}")
print()

print("✅ NetworkX graph construction complete!")
print(f"   Now you can use any NetworkX algorithm on this graph.")
print(f"   See: https://networkx.org/documentation/stable/reference/algorithms/")

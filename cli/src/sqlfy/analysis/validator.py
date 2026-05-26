"""
sqlfy.validator
===============
Graph validation utilities for NetworkX graphs.

Validates graph structure, catches missing attributes, and detects
structural issues like isolated nodes or missing edge attributes.
"""

from __future__ import annotations

from typing import Union

import networkx as nx


def validate_graph_structure(G: Union[nx.Graph, nx.DiGraph]) -> list[str]:
    """Validate graph structure and return list of warnings.
    
    Args:
        G: NetworkX graph to validate
    
    Returns:
        List of warning messages (empty if graph is valid)
    """
    warnings = []
    
    # Check for required node attributes
    for node, data in G.nodes(data=True):
        if "type" not in data:
            warnings.append(f"Node {node} missing 'type' attribute")
        if "label" not in data:
            warnings.append(f"Node {node} missing 'label' attribute")
    
    # Check for isolated nodes (except migrations, which can be isolated)
    isolated = [
        n for n in nx.isolates(G)
        if G.nodes[n].get("type") != "migration"
    ]
    if isolated:
        warnings.append(
            f"{len(isolated)} isolated non-migration nodes found: {isolated[:5]}"
        )
    
    # Check for required edge attributes
    for u, v, data in G.edges(data=True):
        if "relation" not in data:
            warnings.append(f"Edge {u}->{v} missing 'relation' attribute")
        if "confidence" not in data:
            warnings.append(f"Edge {u}->{v} missing 'confidence' attribute")
    
    # Check for disconnected components (warn if >1 component)
    if not isinstance(G, nx.DiGraph):
        components = list(nx.connected_components(G))
        if len(components) > 1:
            warnings.append(
                f"Graph has {len(components)} disconnected components "
                f"(sizes: {[len(c) for c in components[:5]]})"
            )
    
    return warnings


def validate_node_types(G: Union[nx.Graph, nx.DiGraph]) -> dict[str, int]:
    """Count nodes by type.
    
    Args:
        G: NetworkX graph to analyze
    
    Returns:
        Dictionary of node type counts
    """
    type_counts: dict[str, int] = {}
    
    for node, data in G.nodes(data=True):
        node_type = data.get("type", "unknown")
        type_counts[node_type] = type_counts.get(node_type, 0) + 1
    
    return type_counts


def validate_edge_relations(G: Union[nx.Graph, nx.DiGraph]) -> dict[str, int]:
    """Count edges by relation type.
    
    Args:
        G: NetworkX graph to analyze
    
    Returns:
        Dictionary of edge relation counts
    """
    relation_counts: dict[str, int] = {}
    
    for u, v, data in G.edges(data=True):
        relation = data.get("relation", "unknown")
        relation_counts[relation] = relation_counts.get(relation, 0) + 1
    
    return relation_counts

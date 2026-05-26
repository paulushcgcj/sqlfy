"""
clustering.py
=============
Community detection for schema graphs using Leiden/Louvain algorithms.

Adapted from graphify (https://github.com/safishamsi/graphify).
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Union

import networkx as nx


_MAX_COMMUNITY_FRACTION = 0.25
_MIN_SPLIT_SIZE = 10
_DEFAULT_RESOLUTION = 1.0
_DEFAULT_MIN_COHESION = 0.1


@dataclass
class CommunityResult:
    """Result of community detection."""
    communities: dict[int, list[str]]  # {community_id: [node_ids]}
    node_to_community: dict[str, int]  # {node_id: community_id}
    cohesion_scores: dict[int, float]  # {community_id: cohesion_score}
    algorithm: str  # 'leiden' or 'louvain'
    resolution: float
    
    @property
    def num_communities(self) -> int:
        """Return number of communities."""
        return len(self.communities)
    
    def get_community(self, node_id: str) -> int:
        """Get community ID for a node."""
        return self.node_to_community.get(node_id, -1)
    
    def get_nodes(self, community_id: int) -> list[str]:
        """Get all nodes in a community."""
        return self.communities.get(community_id, [])


def detect_communities(
    graph: Union[nx.Graph[Any], nx.DiGraph[Any]],
    resolution: float = _DEFAULT_RESOLUTION,
    min_cohesion: float = _DEFAULT_MIN_COHESION,
    enable_splitting: bool = True,
) -> CommunityResult:
    """
    Detect communities in a schema graph using Leiden or Louvain.
    
    Resolution:
      > 1.0 → more, smaller communities
      < 1.0 → fewer, larger communities
    
    Min Cohesion:
      Filter out communities with cohesion below this threshold.
    
    Enable Splitting:
      If True, split oversized communities (>25% of graph).
    
    Returns:
      CommunityResult with communities, assignments, and cohesion scores.
    """
    if graph.number_of_nodes() == 0:
        return CommunityResult(
            communities={},
            node_to_community={},
            cohesion_scores={},
            algorithm='none',
            resolution=resolution,
        )
    
    # Convert to undirected if needed (community detection requires undirected)
    G = graph.to_undirected() if graph.is_directed() else graph
    
    # Run Leiden or Louvain
    node_to_community, algorithm = _run_community_detection(G, resolution)
    
    # Group nodes by community
    communities: dict[int, list[str]] = defaultdict(list)
    for node, cid in node_to_community.items():
        communities[cid].append(node)
    
    # Convert defaultdict to regular dict
    communities = dict(communities)
    
    # Split oversized communities if enabled
    if enable_splitting:
        communities, node_to_community = _split_oversized_communities(
            G, communities, node_to_community, resolution
        )
    
    # Compute cohesion scores
    cohesion_scores = {
        cid: _cohesion_score(G, nodes)
        for cid, nodes in communities.items()
    }
    
    # Filter low-cohesion communities if threshold set
    if min_cohesion > 0:
        communities, node_to_community, cohesion_scores = _filter_low_cohesion(
            communities, node_to_community, cohesion_scores, min_cohesion
        )
    
    return CommunityResult(
        communities=communities,
        node_to_community=node_to_community,
        cohesion_scores=cohesion_scores,
        algorithm=algorithm,
        resolution=resolution,
    )


def _run_community_detection(
    G: nx.Graph[Any],
    resolution: float,
) -> tuple[dict[str, int], str]:
    """
    Run Leiden (preferred) or Louvain (fallback) community detection.
    
    Returns:
      (node_to_community_dict, algorithm_name)
    """
    # Try Leiden first (requires graspologic)
    try:
        from graspologic.partition import leiden
        
        # Leiden returns a dict {node: community_id}
        node_to_community = leiden(G, resolution=resolution, random_seed=42)
        return node_to_community, 'leiden'
    
    except ImportError:
        # Fallback to NetworkX Louvain
        communities = nx.community.louvain_communities(
            G, seed=42, resolution=resolution
        )
        
        # Convert to {node: community_id} format
        node_to_community = {
            node: cid
            for cid, nodes in enumerate(communities)
            for node in nodes
        }
        return node_to_community, 'louvain'


def _split_oversized_communities(
    G: nx.Graph[Any],
    communities: dict[int, list[str]],
    node_to_community: dict[str, int],
    resolution: float,
) -> tuple[dict[int, list[str]], dict[str, int]]:
    """
    Split communities that are larger than 25% of the graph.
    
    Returns:
      (updated_communities, updated_node_to_community)
    """
    total_nodes = G.number_of_nodes()
    max_size = int(total_nodes * _MAX_COMMUNITY_FRACTION)
    
    if max_size < _MIN_SPLIT_SIZE:
        # Graph too small to split
        return communities, node_to_community
    
    new_communities: dict[int, list[str]] = {}
    new_node_to_community: dict[str, int] = {}
    next_cid = max(communities.keys()) + 1 if communities else 0
    
    for cid, nodes in communities.items():
        if len(nodes) <= max_size:
            # Keep community as-is
            new_communities[cid] = nodes
            for node in nodes:
                new_node_to_community[node] = cid
        else:
            # Split oversized community
            subgraph = G.subgraph(nodes)
            
            # Run community detection on subgraph with higher resolution
            sub_node_to_community, _ = _run_community_detection(
                subgraph, resolution * 1.5
            )
            
            # Remap sub-community IDs to global IDs
            sub_communities: dict[int, list[str]] = defaultdict(list)
            for node, sub_cid in sub_node_to_community.items():
                sub_communities[sub_cid].append(node)
            
            for sub_nodes in sub_communities.values():
                new_communities[next_cid] = sub_nodes
                for node in sub_nodes:
                    new_node_to_community[node] = next_cid
                next_cid += 1
    
    return new_communities, new_node_to_community


def _cohesion_score(G: nx.Graph[Any], community_nodes: list[str]) -> float:
    """
    Compute cohesion score for a community.
    
    Cohesion = actual_edges / possible_edges
    
    A score of 1.0 means a fully connected clique.
    A score near 0.0 means few connections.
    """
    n = len(community_nodes)
    if n == 0:
        return 0.0  # Empty community has no cohesion
    if n == 1:
        return 1.0  # Single node is perfectly cohesive by definition
    
    subgraph = G.subgraph(community_nodes)
    actual = subgraph.number_of_edges()
    possible = n * (n - 1) / 2
    
    return actual / possible if possible > 0 else 0.0


def _filter_low_cohesion(
    communities: dict[int, list[str]],
    node_to_community: dict[str, int],
    cohesion_scores: dict[int, float],
    min_cohesion: float,
) -> tuple[dict[int, list[str]], dict[str, int], dict[int, float]]:
    """
    Filter out communities with cohesion below threshold.
    
    Low-cohesion nodes are reassigned to community -1 (unclustered).
    """
    new_communities: dict[int, list[str]] = {}
    new_node_to_community: dict[str, int] = {}
    new_cohesion_scores: dict[int, float] = {}
    
    unclustered: list[str] = []
    
    for cid, nodes in communities.items():
        cohesion = cohesion_scores[cid]
        
        if cohesion >= min_cohesion:
            # Keep community
            new_communities[cid] = nodes
            new_cohesion_scores[cid] = cohesion
            for node in nodes:
                new_node_to_community[node] = cid
        else:
            # Mark nodes as unclustered
            unclustered.extend(nodes)
    
    # Add unclustered nodes to community -1
    if unclustered:
        new_communities[-1] = unclustered
        new_cohesion_scores[-1] = 0.0
        for node in unclustered:
            new_node_to_community[node] = -1
    
    return new_communities, new_node_to_community, new_cohesion_scores


def label_communities(
    communities: dict[int, list[str]],
    graph: Union[nx.Graph[Any], nx.DiGraph[Any]],
) -> dict[int, str]:
    """
    Generate human-readable labels for communities based on node types.
    
    Uses heuristics:
    - Most common schema name prefix
    - Most common node type
    - Size of community
    
    Returns:
      {community_id: label}
    """
    labels: dict[int, str] = {}
    
    for cid, nodes in communities.items():
        if cid == -1:
            labels[cid] = 'Unclustered'
            continue
        
        if not nodes:
            labels[cid] = f'Community {cid}'
            continue
        
        # Count node types
        type_counts: dict[str, int] = defaultdict(int)
        schema_counts: dict[str, int] = defaultdict(int)
        
        for node in nodes:
            node_data = graph.nodes.get(node, {})
            node_type = node_data.get('type', 'unknown')
            type_counts[node_type] += 1
            
            # Extract schema prefix from node ID (e.g., "APP.USERS" → "APP")
            if '.' in node:
                schema = node.split('.')[0]
                schema_counts[schema] += 1
        
        # Find most common type and schema
        most_common_type = max(type_counts, key=type_counts.get) if type_counts else 'unknown'
        most_common_schema = max(schema_counts, key=schema_counts.get) if schema_counts else None
        
        # Generate label
        if most_common_schema:
            labels[cid] = f'{most_common_schema} {most_common_type.title()}s ({len(nodes)} nodes)'
        else:
            labels[cid] = f'{most_common_type.title()}s ({len(nodes)} nodes)'
    
    return labels

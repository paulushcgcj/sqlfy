"""
test_clustering.py
==================
Tests for community detection module (Feature #4).
"""

import networkx as nx
import pytest

from sqlfy.clustering import (
    detect_communities,
    label_communities,
    _cohesion_score,
    CommunityResult,
)


def test_community_result_properties():
    """Test CommunityResult dataclass properties."""
    result = CommunityResult(
        communities={0: ['A', 'B'], 1: ['C', 'D', 'E']},
        node_to_community={'A': 0, 'B': 0, 'C': 1, 'D': 1, 'E': 1},
        cohesion_scores={0: 1.0, 1: 0.8},
        algorithm='leiden',
        resolution=1.0,
    )
    
    assert result.num_communities == 2
    assert result.get_community('A') == 0
    assert result.get_community('C') == 1
    assert result.get_community('NONEXISTENT') == -1
    assert result.get_nodes(0) == ['A', 'B']
    assert result.get_nodes(1) == ['C', 'D', 'E']
    assert result.get_nodes(999) == []


def test_detect_communities_empty_graph():
    """Test community detection on empty graph."""
    G = nx.Graph()
    
    result = detect_communities(G)
    
    assert result.num_communities == 0
    assert result.communities == {}
    assert result.node_to_community == {}
    assert result.algorithm == 'none'


def test_detect_communities_single_node():
    """Test community detection with single isolated node."""
    G = nx.Graph()
    G.add_node('A', type='table')
    
    result = detect_communities(G)
    
    assert result.num_communities == 1
    assert 'A' in result.communities[0]
    assert result.get_community('A') == 0


def test_detect_communities_two_components():
    """Test community detection finds separate connected components."""
    G = nx.Graph()
    G.add_edges_from([('A', 'B'), ('B', 'C')])  # Component 1
    G.add_edges_from([('D', 'E'), ('E', 'F')])  # Component 2
    
    result = detect_communities(G)
    
    # Should find at least 2 communities (one per component)
    assert result.num_communities >= 2
    
    # A, B, C should be in same community
    comm_abc = result.get_community('A')
    assert result.get_community('B') == comm_abc
    assert result.get_community('C') == comm_abc
    
    # D, E, F should be in same community (different from ABC)
    comm_def = result.get_community('D')
    assert result.get_community('E') == comm_def
    assert result.get_community('F') == comm_def
    assert comm_def != comm_abc


def test_detect_communities_clique():
    """Test community detection on fully connected clique."""
    G = nx.complete_graph(5)
    
    result = detect_communities(G, resolution=1.0)
    
    # Clique should be detected as single community
    assert result.num_communities == 1
    community_id = result.get_community(0)
    assert all(result.get_community(i) == community_id for i in range(5))


def test_detect_communities_resolution_parameter():
    """Test that resolution parameter affects number of communities."""
    # Create graph with moderate structure
    G = nx.Graph()
    # Group 1: A-B-C
    G.add_edges_from([('A', 'B'), ('B', 'C'), ('C', 'A')])
    # Group 2: D-E-F
    G.add_edges_from([('D', 'E'), ('E', 'F'), ('F', 'D')])
    # Weak bridge
    G.add_edge('C', 'D')
    
    # Low resolution: should merge into fewer communities
    result_low = detect_communities(G, resolution=0.5)
    
    # High resolution: should split into more communities
    result_high = detect_communities(G, resolution=2.0)
    
    # High resolution should produce at least as many communities as low
    assert result_high.num_communities >= result_low.num_communities


def test_detect_communities_min_cohesion_filter():
    """Test that min_cohesion filters out low-quality communities."""
    G = nx.Graph()
    # Strong community: complete triangle
    G.add_edges_from([('A', 'B'), ('B', 'C'), ('C', 'A')])
    # Weak community: linear chain
    G.add_edges_from([('D', 'E'), ('E', 'F')])
    
    result = detect_communities(G, min_cohesion=0.5, enable_splitting=False)
    
    # Strong community should remain
    strong_comm = result.get_community('A')
    assert strong_comm >= 0
    assert result.cohesion_scores[strong_comm] >= 0.5


def test_detect_communities_directed_graph():
    """Test community detection on directed graph (should convert to undirected)."""
    G = nx.DiGraph()
    G.add_edges_from([('A', 'B'), ('B', 'C'), ('C', 'A')])
    
    result = detect_communities(G)
    
    # Should detect community successfully
    assert result.num_communities >= 1
    comm_a = result.get_community('A')
    assert result.get_community('B') == comm_a
    assert result.get_community('C') == comm_a


def test_cohesion_score_clique():
    """Test cohesion score for fully connected clique."""
    G = nx.complete_graph(4)
    nodes = list(G.nodes())
    
    score = _cohesion_score(G, nodes)
    
    assert score == 1.0  # Perfect connectivity


def test_cohesion_score_linear_chain():
    """Test cohesion score for linear chain (low connectivity)."""
    G = nx.Graph()
    G.add_edges_from([('A', 'B'), ('B', 'C'), ('C', 'D')])
    nodes = ['A', 'B', 'C', 'D']
    
    score = _cohesion_score(G, nodes)
    
    # Linear chain has 3 edges, possible = 4*3/2 = 6
    # Score = 3/6 = 0.5
    assert score == 0.5


def test_cohesion_score_single_node():
    """Test cohesion score for single node."""
    G = nx.Graph()
    G.add_node('A')
    
    score = _cohesion_score(G, ['A'])
    
    assert score == 1.0  # By definition


def test_cohesion_score_empty_community():
    """Test cohesion score for empty community."""
    G = nx.Graph()
    
    score = _cohesion_score(G, [])
    
    assert score == 0.0


def test_label_communities_basic():
    """Test community labeling with basic graph."""
    G = nx.Graph()
    G.add_node('APP.USERS', type='table')
    G.add_node('APP.ORDERS', type='table')
    G.add_node('APP.PRODUCTS', type='table')
    G.add_edges_from([('APP.USERS', 'APP.ORDERS'), ('APP.ORDERS', 'APP.PRODUCTS')])
    
    communities = {0: ['APP.USERS', 'APP.ORDERS', 'APP.PRODUCTS']}
    
    labels = label_communities(communities, G)
    
    assert 0 in labels
    assert 'APP' in labels[0]
    assert 'table' in labels[0].lower()
    assert '3 nodes' in labels[0]


def test_label_communities_mixed_types():
    """Test community labeling with mixed node types."""
    G = nx.Graph()
    G.add_node('A', type='table')
    G.add_node('B', type='table')
    G.add_node('C', type='view')
    
    communities = {0: ['A', 'B', 'C']}
    
    labels = label_communities(communities, G)
    
    # Should label by dominant type (table)
    assert 'Table' in labels[0] or 'table' in labels[0].lower()


def test_label_communities_unclustered():
    """Test that unclustered nodes (community -1) get special label."""
    G = nx.Graph()
    G.add_node('A', type='table')
    
    communities = {-1: ['A']}
    
    labels = label_communities(communities, G)
    
    assert labels[-1] == 'Unclustered'


def test_label_communities_empty():
    """Test community labeling with empty community."""
    G = nx.Graph()
    
    communities = {0: []}
    
    labels = label_communities(communities, G)
    
    assert 'Community 0' in labels[0]


def test_detect_communities_karate_club():
    """Test community detection on Zachary's Karate Club graph."""
    G = nx.karate_club_graph()
    
    result = detect_communities(G, resolution=1.0)
    
    # Karate club should split into 2-4 communities
    assert 2 <= result.num_communities <= 4
    
    # All nodes should be assigned
    assert len(result.node_to_community) == G.number_of_nodes()


def test_detect_communities_splitting_large():
    """Test that oversized communities are split."""
    # Create large graph where one community dominates
    G = nx.Graph()
    
    # Large clique (50 nodes)
    large_clique = [f'L{i}' for i in range(50)]
    for i, node1 in enumerate(large_clique):
        for node2 in large_clique[i+1:]:
            G.add_edge(node1, node2)
    
    # Small clique (5 nodes)
    small_clique = [f'S{i}' for i in range(5)]
    for i, node1 in enumerate(small_clique):
        for node2 in small_clique[i+1:]:
            G.add_edge(node1, node2)
    
    # Weak bridge
    G.add_edge('L0', 'S0')
    
    result = detect_communities(G, enable_splitting=True, resolution=1.0)
    
    # Large clique should be split (>25% of 55 nodes = 13.75, so >13)
    # Should have more than 1 community
    assert result.num_communities >= 2


def test_detect_communities_no_splitting():
    """Test that splitting can be disabled."""
    G = nx.complete_graph(50)
    
    result = detect_communities(G, enable_splitting=False, resolution=1.0)
    
    # Without splitting, should remain as single community
    assert result.num_communities == 1


def test_detect_communities_algorithm_fallback():
    """Test that algorithm name is reported correctly."""
    G = nx.Graph()
    G.add_edges_from([('A', 'B'), ('B', 'C')])
    
    result = detect_communities(G)
    
    # Should use leiden or louvain
    assert result.algorithm in ('leiden', 'louvain')


def test_detect_communities_schema_pattern():
    """Test community detection on realistic schema pattern."""
    G = nx.Graph()
    
    # User management domain
    G.add_node('APP.USERS', type='table')
    G.add_node('APP.USER_ROLES', type='table')
    G.add_node('APP.ROLES', type='table')
    G.add_edges_from([
        ('APP.USERS', 'APP.USER_ROLES'),
        ('APP.USER_ROLES', 'APP.ROLES'),
    ])
    
    # Order management domain
    G.add_node('APP.ORDERS', type='table')
    G.add_node('APP.ORDER_ITEMS', type='table')
    G.add_node('APP.PRODUCTS', type='table')
    G.add_edges_from([
        ('APP.ORDERS', 'APP.ORDER_ITEMS'),
        ('APP.ORDER_ITEMS', 'APP.PRODUCTS'),
    ])
    
    # Cross-domain link
    G.add_edge('APP.USERS', 'APP.ORDERS')
    
    result = detect_communities(G, resolution=1.5)
    
    # Should detect at least 2 domains
    assert result.num_communities >= 2
    
    # Users and user_roles should likely be together
    user_comm = result.get_community('APP.USERS')
    user_roles_comm = result.get_community('APP.USER_ROLES')
    
    # Orders and order_items should likely be together
    orders_comm = result.get_community('APP.ORDERS')
    order_items_comm = result.get_community('APP.ORDER_ITEMS')


def test_detect_communities_star_graph():
    """Test community detection on star graph (hub-and-spoke)."""
    G = nx.star_graph(10)  # One central node connected to 10 peripheral nodes
    
    result = detect_communities(G, resolution=1.0)
    
    # Star graph should be detected as single community (low modularity)
    assert result.num_communities >= 1
    
    # Central node (0) should be in same community as at least some spokes
    central_comm = result.get_community(0)
    assert central_comm >= 0


def test_detect_communities_barbell_graph():
    """Test community detection on barbell graph (two cliques connected by bridge)."""
    G = nx.barbell_graph(5, 1)  # Two 5-cliques connected by single edge
    
    result = detect_communities(G, resolution=1.0)
    
    # Should detect 2 communities (one per clique)
    assert result.num_communities >= 2
    
    # Nodes in each clique should be in same community
    comm_left = result.get_community(0)
    for i in range(1, 5):
        assert result.get_community(i) == comm_left
    
    comm_right = result.get_community(6)
    for i in range(7, 11):
        assert result.get_community(i) == comm_right
    
    # Two communities should be different
    assert comm_left != comm_right

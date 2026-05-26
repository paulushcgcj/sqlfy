"""
test_impact.py
==============
Tests for impact analysis module (Feature #3).
"""

import networkx as nx

from sqlfy.analysis.impact import (
    analyze_impact,
    ImpactResult,
    format_impact_text,
    format_impact_json,
)


def test_impact_result_total_count():
    """Test ImpactResult.total_count property."""
    result = ImpactResult(
        object_id='A',
        direct=['B', 'C'],
        transitive=['D', 'E', 'F'],
        depth_map={'B': 1, 'C': 1, 'D': 2, 'E': 2, 'F': 3},
    )
    
    assert result.total_count == 5


def test_impact_result_to_dict():
    """Test ImpactResult.to_dict() serialization."""
    result = ImpactResult(
        object_id='A',
        direct=['B'],
        transitive=['C'],
        depth_map={'B': 1, 'C': 2},
        by_type={'table': ['B', 'C']},
        critical_paths=[['A', 'B', 'C']],
        max_depth=2,
    )
    
    data = result.to_dict()
    
    assert data['object_id'] == 'A'
    assert data['direct'] == ['B']
    assert data['transitive'] == ['C']
    assert data['total_count'] == 2
    assert data['max_depth'] == 2


def test_analyze_impact_nonexistent_node():
    """Test impact analysis for non-existent node returns empty result."""
    G = nx.DiGraph()
    G.add_node('A')
    
    result = analyze_impact(G, 'NONEXISTENT')
    
    assert result.object_id == 'NONEXISTENT'
    assert result.total_count == 0
    assert result.direct == []
    assert result.transitive == []


def test_analyze_impact_linear_chain():
    """Test impact analysis on simple linear dependency chain."""
    # A → B → C → D
    G = nx.DiGraph()
    G.add_node('A', type='table')
    G.add_node('B', type='table')
    G.add_node('C', type='view')
    G.add_node('D', type='procedure')
    G.add_edges_from([('A', 'B'), ('B', 'C'), ('C', 'D')])
    
    result = analyze_impact(G, 'A', max_depth=5)
    
    assert result.object_id == 'A'
    assert result.direct == ['B']
    assert set(result.transitive) == {'C', 'D'}
    assert result.depth_map == {'B': 1, 'C': 2, 'D': 3}
    assert result.max_depth == 3
    assert result.total_count == 3


def test_analyze_impact_branching():
    """Test impact analysis with branching dependencies."""
    # A → B, A → C, B → D, C → D
    G = nx.DiGraph()
    for node in ['A', 'B', 'C', 'D']:
        G.add_node(node, type='table')
    G.add_edges_from([('A', 'B'), ('A', 'C'), ('B', 'D'), ('C', 'D')])
    
    result = analyze_impact(G, 'A', max_depth=5)
    
    assert result.object_id == 'A'
    assert set(result.direct) == {'B', 'C'}
    assert result.transitive == ['D']
    assert result.depth_map['B'] == 1
    assert result.depth_map['C'] == 1
    assert result.depth_map['D'] == 2  # Should be depth 2 (reached via B or C)


def test_analyze_impact_circular_dependency():
    """Test impact analysis handles circular dependencies gracefully."""
    # A → B → C → A (cycle)
    G = nx.DiGraph()
    for node in ['A', 'B', 'C']:
        G.add_node(node, type='table')
    G.add_edges_from([('A', 'B'), ('B', 'C'), ('C', 'A')])
    
    result = analyze_impact(G, 'A', max_depth=5)
    
    # Should visit each node once and stop
    assert result.object_id == 'A'
    assert result.total_count == 2  # B and C
    assert set(result.direct) == {'B'}
    assert set(result.transitive) == {'C'}


def test_analyze_impact_max_depth_limit():
    """Test impact analysis respects max_depth parameter."""
    # A → B → C → D → E
    G = nx.DiGraph()
    for node in ['A', 'B', 'C', 'D', 'E']:
        G.add_node(node, type='table')
    G.add_edges_from([('A', 'B'), ('B', 'C'), ('C', 'D'), ('D', 'E')])
    
    result = analyze_impact(G, 'A', max_depth=2)
    
    # Should only reach B and C (depth 1 and 2)
    assert result.total_count == 2
    assert 'B' in result.direct
    assert 'C' in result.transitive
    assert 'D' not in result.depth_map
    assert 'E' not in result.depth_map


def test_analyze_impact_by_type_grouping():
    """Test impact analysis groups results by object type."""
    G = nx.DiGraph()
    G.add_node('A', type='table')
    G.add_node('B', type='table')
    G.add_node('C', type='view')
    G.add_node('D', type='procedure')
    G.add_edges_from([('A', 'B'), ('A', 'C'), ('A', 'D')])
    
    result = analyze_impact(G, 'A')
    
    assert 'table' in result.by_type
    assert 'view' in result.by_type
    assert 'procedure' in result.by_type
    assert result.by_type['table'] == ['B']
    assert result.by_type['view'] == ['C']
    assert result.by_type['procedure'] == ['D']


def test_analyze_impact_critical_paths():
    """Test critical path identification."""
    # A → B → D (leaf)
    # A → C → E (leaf)
    G = nx.DiGraph()
    for node in ['A', 'B', 'C', 'D', 'E']:
        G.add_node(node, type='table')
    G.add_edges_from([('A', 'B'), ('B', 'D'), ('A', 'C'), ('C', 'E')])
    
    result = analyze_impact(G, 'A')
    
    # Should have 2 critical paths
    assert len(result.critical_paths) == 2
    paths_set = {tuple(path) for path in result.critical_paths}
    assert ('A', 'B', 'D') in paths_set
    assert ('A', 'C', 'E') in paths_set


def test_analyze_impact_undirected_graph():
    """Test impact analysis works on undirected graphs."""
    G = nx.Graph()  # Undirected
    G.add_node('A', type='table')
    G.add_node('B', type='table')
    G.add_node('C', type='table')
    G.add_edges_from([('A', 'B'), ('B', 'C')])
    
    result = analyze_impact(G, 'A')
    
    # In undirected graph, neighbors are all connected nodes
    assert result.total_count == 2
    assert 'B' in result.direct
    assert 'C' in result.transitive


def test_analyze_impact_follow_direction_in():
    """Test impact analysis can follow edges inward (predecessors)."""
    # A → B → C
    G = nx.DiGraph()
    for node in ['A', 'B', 'C']:
        G.add_node(node, type='table')
    G.add_edges_from([('A', 'B'), ('B', 'C')])
    
    # Analyze C with direction='in' (what depends ON C? nothing)
    result = analyze_impact(G, 'C', follow_direction='in')
    
    # Should find B and A (predecessors)
    assert result.total_count == 2
    assert 'B' in result.direct
    assert 'A' in result.transitive


def test_analyze_impact_isolated_node():
    """Test impact analysis on isolated node with no connections."""
    G = nx.DiGraph()
    G.add_node('A', type='table')
    G.add_node('B', type='table')  # No edge to A
    
    result = analyze_impact(G, 'A')
    
    assert result.total_count == 0
    assert result.direct == []
    assert result.transitive == []


def test_format_impact_text_no_affected():
    """Test text formatting when no objects are affected."""
    G = nx.DiGraph()
    G.add_node('A', type='table')
    
    result = analyze_impact(G, 'A')
    text = format_impact_text(result, G)
    
    assert 'No affected objects found' in text
    assert 'Impact Analysis: A' in text


def test_format_impact_text_with_affected():
    """Test text formatting with affected objects."""
    G = nx.DiGraph()
    G.add_node('A', type='table')
    G.add_node('B', type='view')
    G.add_node('C', type='procedure')
    G.add_edges_from([('A', 'B'), ('B', 'C')])
    
    result = analyze_impact(G, 'A')
    text = format_impact_text(result, G)
    
    assert 'Impact Analysis: A' in text
    assert 'Total affected: 2' in text
    assert 'Direct dependencies (1):' in text
    assert 'B (view)' in text
    assert 'Transitive dependencies (1):' in text
    assert 'C (procedure)' in text


def test_format_impact_json():
    """Test JSON formatting."""
    result = ImpactResult(
        object_id='A',
        direct=['B'],
        transitive=['C'],
        depth_map={'B': 1, 'C': 2},
        by_type={'table': ['B', 'C']},
        critical_paths=[['A', 'B', 'C']],
        max_depth=2,
    )
    
    json_str = format_impact_json(result)
    
    assert '"object_id": "A"' in json_str
    assert '"direct": [\n    "B"\n  ]' in json_str or '"direct":["B"]' in json_str
    assert '"total_count": 2' in json_str


def test_analyze_impact_complex_graph():
    """Test impact analysis on complex graph with multiple patterns."""
    # Complex graph:
    # A → B → D → F
    # A → C → D
    # B → E
    G = nx.DiGraph()
    for node in ['A', 'B', 'C', 'D', 'E', 'F']:
        G.add_node(node, type='table')
    G.add_edges_from([
        ('A', 'B'), ('A', 'C'),
        ('B', 'D'), ('B', 'E'),
        ('C', 'D'),
        ('D', 'F'),
    ])
    
    result = analyze_impact(G, 'A')
    
    # Direct: B, C
    assert set(result.direct) == {'B', 'C'}
    
    # Transitive: D (via B or C), E (via B), F (via D)
    assert set(result.transitive) == {'D', 'E', 'F'}
    
    # D should be at depth 2 (shortest path from A)
    assert result.depth_map['D'] == 2
    assert result.depth_map['E'] == 2
    assert result.depth_map['F'] == 3
    
    # Should have 2 critical paths: A→B→E and A→B→D→F (or A→C→D→F)
    assert len(result.critical_paths) >= 2


def test_analyze_impact_real_schema_pattern():
    """Test impact analysis on realistic schema pattern."""
    # users → orders → order_items → products
    # users → audit_log
    G = nx.DiGraph()
    G.add_node('USERS', type='table')
    G.add_node('ORDERS', type='table')
    G.add_node('ORDER_ITEMS', type='table')
    G.add_node('PRODUCTS', type='table')
    G.add_node('AUDIT_LOG', type='table')
    G.add_node('V_ORDER_SUMMARY', type='view')
    
    G.add_edges_from([
        ('USERS', 'ORDERS'),
        ('ORDERS', 'ORDER_ITEMS'),
        ('ORDERS', 'V_ORDER_SUMMARY'),
        ('ORDER_ITEMS', 'PRODUCTS'),
        ('USERS', 'AUDIT_LOG'),
    ])
    
    # What's affected if USERS changes?
    result = analyze_impact(G, 'USERS')
    
    assert 'ORDERS' in result.direct
    assert 'AUDIT_LOG' in result.direct
    assert 'ORDER_ITEMS' in result.transitive
    assert 'V_ORDER_SUMMARY' in result.transitive
    assert 'PRODUCTS' in result.transitive
    
    # Check type grouping
    assert 'table' in result.by_type
    assert 'view' in result.by_type
    assert 'V_ORDER_SUMMARY' in result.by_type['view']

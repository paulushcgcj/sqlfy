"""
test_graph_export.py
====================
Tests for NetworkX graph export functions (Feature #2).
"""

from pathlib import Path
import json
import tempfile

import networkx as nx

from sqlfy.output.graph_export import (
    export_graph_json,
    export_graph_html,
    export_graph_report,
    _compute_communities,
    _get_community_labels,
)


def test_compute_communities_placeholder():
    """Test community detection returns single community (placeholder)."""
    G = nx.DiGraph()
    G.add_nodes_from(['A', 'B', 'C'])
    G.add_edges_from([('A', 'B'), ('B', 'C')])
    
    communities = _compute_communities(G)
    
    assert len(communities) == 1
    assert 0 in communities
    assert set(communities[0]) == {'A', 'B', 'C'}


def test_get_community_labels():
    """Test community label generation."""
    G = nx.DiGraph()
    G.add_node('A', type='table')
    G.add_node('B', type='table')
    G.add_node('C', type='migration')
    
    communities = {0: ['A', 'B', 'C']}
    labels = _get_community_labels(communities, G)
    
    assert 0 in labels
    assert 'table' in labels[0].lower()
    assert '3 nodes' in labels[0]


def test_export_graph_json():
    """Test JSON export produces NetworkX node-link format."""
    G = nx.DiGraph()
    G.add_node('T1', label='TABLE1', type='table', schema='app')
    G.add_node('T2', label='TABLE2', type='table', schema='app')
    G.add_edge('T1', 'T2', relation='references', confidence='EXTRACTED')
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / 'test.json'
        export_graph_json(G, output_path=output_path)
        
        assert output_path.exists()
        
        data = json.loads(output_path.read_text())
        
        # Validate NetworkX node-link format
        assert 'directed' in data
        assert 'multigraph' in data
        assert 'nodes' in data
        assert 'edges' in data
        
        # Validate node enrichment
        assert len(data['nodes']) == 2
        node = data['nodes'][0]
        assert 'id' in node
        assert 'community' in node
        assert 'degree' in node
        
        # Validate edges
        assert len(data['edges']) == 1
        edge = data['edges'][0]
        assert 'source' in edge
        assert 'target' in edge


def test_export_graph_html():
    """Test HTML export produces valid HTML with vis.js."""
    G = nx.DiGraph()
    G.add_node('T1', label='TABLE1', type='table')
    G.add_node('T2', label='TABLE2', type='table')
    G.add_edge('T1', 'T2', relation='references', confidence='EXTRACTED')
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / 'test.html'
        export_graph_html(G, output_path=output_path)
        
        assert output_path.exists()
        
        html_content = output_path.read_text()
        
        # Validate HTML structure
        assert '<!DOCTYPE html>' in html_content
        assert '<html>' in html_content
        assert 'vis-network' in html_content
        
        # Validate vis.js data injection
        assert 'const nodesData' in html_content
        assert 'const edgesData' in html_content
        assert 'const legendData' in html_content
        
        # Validate search functionality
        assert 'getElementById(\'search\')' in html_content
        
        # Validate node data
        assert '"id": "T1"' in html_content or '"id":"T1"' in html_content
        assert 'TABLE1' in html_content


def test_export_graph_report():
    """Test report export produces valid Markdown."""
    G = nx.DiGraph()
    G.add_node('T1', label='TABLE1', type='table')
    G.add_node('T2', label='TABLE2', type='table')
    G.add_node('T3', label='TABLE3', type='table')
    G.add_edge('T1', 'T2', relation='references')
    G.add_edge('T1', 'T3', relation='references')
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / 'test.md'
        export_graph_report(G, output_path=output_path)
        
        assert output_path.exists()
        
        report_content = output_path.read_text()
        
        # Validate Markdown structure
        assert '# Schema Graph Report' in report_content
        assert '## Graph Metadata' in report_content
        assert '## God Nodes' in report_content
        assert '## Communities' in report_content
        assert '## Suggested Exploration Questions' in report_content
        
        # Validate metrics
        assert '**Nodes:** 3' in report_content
        assert '**Edges:** 2' in report_content
        
        # Validate god nodes table
        assert '| Rank | Node | Degree Centrality | Type |' in report_content
        
        # Validate suggestions
        assert 'sqlfy query' in report_content


def test_export_graph_json_with_custom_communities():
    """Test JSON export respects custom community assignments."""
    G = nx.DiGraph()
    G.add_node('T1', type='table')
    G.add_node('T2', type='table')
    G.add_node('T3', type='table')
    G.add_edge('T1', 'T2')
    
    # Custom communities: 2 groups
    communities = {
        0: ['T1', 'T2'],
        1: ['T3']
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / 'test.json'
        export_graph_json(G, communities=communities, output_path=output_path)
        
        data = json.loads(output_path.read_text())
        
        # Find node communities
        node_communities = {n['id']: n['community'] for n in data['nodes']}
        
        assert node_communities['T1'] == 0
        assert node_communities['T2'] == 0
        assert node_communities['T3'] == 1


def test_export_graph_html_empty_graph():
    """Test HTML export handles empty graph gracefully."""
    G = nx.DiGraph()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / 'test.html'
        export_graph_html(G, output_path=output_path)
        
        assert output_path.exists()
        
        html_content = output_path.read_text()
        assert '0 nodes, 0 edges' in html_content


def test_export_graph_report_calculates_density():
    """Test report includes graph density calculation."""
    G = nx.DiGraph()
    G.add_nodes_from(['A', 'B', 'C'])
    G.add_edge('A', 'B')
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / 'test.md'
        export_graph_report(G, output_path=output_path)
        
        report_content = output_path.read_text()
        
        # Density should be present
        assert 'Density:' in report_content
        assert '0.' in report_content  # Some decimal value


def test_export_creates_output_directory():
    """Test exports create missing directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        nested_path = Path(tmpdir) / 'nested' / 'dir' / 'graph.json'
        
        G = nx.DiGraph()
        G.add_node('A')
        
        export_graph_json(G, output_path=nested_path)
        
        assert nested_path.exists()
        assert nested_path.parent.exists()

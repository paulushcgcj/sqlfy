"""
sqlfy.graph_export
==================
NetworkX graph export utilities for interactive visualization and analysis.

Produces three outputs from a NetworkX graph:
  - graph.json:        NetworkX node-link format with community/degree data
  - graph.html:        Interactive vis.js visualization with search and filtering
  - GRAPH_REPORT.md:   Human-readable summary with god nodes and insights

Usage
-----
    from cli.core import build_networkx_graph
    from cli.graph_export import export_graph_json, export_graph_html, export_graph_report
    
    graph = build_networkx_graph(schema_graph)
    communities = _compute_communities(graph)  # Feature #4, placeholder for now
    
    export_graph_json(graph, communities, Path('graph.json'))
    export_graph_html(graph, communities, Path('graph.html'))
    export_graph_report(graph, Path('GRAPH_REPORT.md'))
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx

from ..domain.models import SchemaGraph


# ──────────────────────────────────────────────
# COMMUNITY DETECTION (Placeholder for Feature #4)
# ──────────────────────────────────────────────

def _compute_communities(graph: nx.Graph[Any] | nx.DiGraph[Any]) -> dict[int, list[str]]:
    """
    Compute community assignments for nodes.
    
    PLACEHOLDER: Currently assigns all nodes to community 0.
    Feature #4 will replace this with Leiden/Louvain clustering.
    
    Args:
        graph: NetworkX graph to analyze
    
    Returns:
        Dictionary mapping community ID to list of node IDs
    """
    # Placeholder: single community containing all nodes
    return {0: list(graph.nodes())}


def _get_community_labels(communities: dict[int, list[str]], graph: nx.Graph[Any] | nx.DiGraph[Any]) -> dict[int, str]:
    """
    Generate human-readable labels for communities.
    
    Args:
        communities: Community assignments
        graph: NetworkX graph
    
    Returns:
        Dictionary mapping community ID to label
    """
    labels = {}
    for cid, nodes in communities.items():
        # Count node types in this community
        type_counts: dict[str, int] = {}
        for node in nodes:
            node_type = graph.nodes[node].get('type', 'unknown')
            type_counts[node_type] = type_counts.get(node_type, 0) + 1
        
        # Label by dominant type
        if type_counts:
            dominant = max(type_counts.items(), key=lambda x: x[1])
            labels[cid] = f"{dominant[0].title()} Domain ({len(nodes)} nodes)"
        else:
            labels[cid] = f"Community {cid}"
    
    return labels


# ──────────────────────────────────────────────
# JSON EXPORT
# ──────────────────────────────────────────────

def export_graph_json(
    graph: nx.Graph[Any] | nx.DiGraph[Any],
    communities: dict[int, list[str]] | None = None,
    output_path: Path | str = Path('graph.json')
) -> None:
    """
    Export graph in NetworkX node-link JSON format.
    
    Compatible with NetworkX json_graph.node_link_data() format.
    Enriches nodes with community assignments and degree centrality.
    
    Args:
        graph: NetworkX graph to export
        communities: Optional community assignments (default: auto-compute)
        output_path: Output file path
    """
    if communities is None:
        communities = _compute_communities(graph)
    
    # Map node → community ID
    node_community: dict[str, int] = {}
    for cid, nodes in communities.items():
        for node in nodes:
            node_community[node] = cid
    
    # Convert to node-link format
    data = nx.node_link_data(graph)
    
    # Enrich nodes with community and degree
    for node in data['nodes']:
        node_id = node['id']
        node['community'] = node_community.get(node_id, 0)
        node['degree'] = graph.degree(node_id)
    
    # Write output
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


# ──────────────────────────────────────────────
# HTML EXPORT
# ──────────────────────────────────────────────

def _get_community_color(cid: int) -> str:
    """Get color for community using Tableau10 palette."""
    COLORS = [
        '#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f',
        '#edc949', '#af7aa1', '#ff9da7', '#9c755f', '#bab0ab'
    ]
    return COLORS[cid % len(COLORS)]


def export_graph_html(
    graph: nx.Graph[Any] | nx.DiGraph[Any],
    communities: dict[int, list[str]] | None = None,
    output_path: Path | str = Path('graph.html')
) -> None:
    """
    Export interactive HTML visualization using vis.js.
    
    Features:
      - Force-directed layout with physics simulation
      - Search bar with live filtering
      - Community legend with toggle checkboxes
      - Node inspector showing degree, type, neighbors
      - Edge tooltips with relation type and confidence
    
    Args:
        graph: NetworkX graph to visualize
        communities: Optional community assignments (default: auto-compute)
        output_path: Output file path
    """
    if communities is None:
        communities = _compute_communities(graph)
    
    community_labels = _get_community_labels(communities, graph)
    
    # Map node → community ID
    node_community: dict[str, int] = {}
    for cid, nodes in communities.items():
        for node in nodes:
            node_community[node] = cid
    
    # Prepare vis.js nodes
    nodes_data = []
    for node_id, attrs in graph.nodes(data=True):
        cid = node_community.get(node_id, 0)
        color = _get_community_color(cid)
        degree = graph.degree(node_id)
        
        nodes_data.append({
            'id': node_id,
            'label': attrs.get('label', node_id),
            'color': color,
            'size': min(50, 10 + degree * 2),
            'community': cid,
            'community_name': community_labels.get(cid, f'Community {cid}'),
            'type': attrs.get('type', 'unknown'),
            'degree': degree,
            'title': f"{attrs.get('type', 'unknown')}: {node_id}<br/>Degree: {degree}<br/>{community_labels.get(cid, '')}"
        })
    
    # Prepare vis.js edges
    edges_data = []
    for u, v, attrs in graph.edges(data=True):
        relation = attrs.get('relation', '')
        confidence = attrs.get('confidence', 'EXTRACTED')
        
        edges_data.append({
            'from': u,
            'to': v,
            'label': relation,
            'title': f"{relation}<br/>Confidence: {confidence}",
            'dashes': confidence == 'INFERRED',
            'width': 2 if confidence == 'EXTRACTED' else 1,
            'color': {'color': '#94a3b8', 'opacity': 0.6 if confidence == 'INFERRED' else 1.0}
        })
    
    # Prepare community legend
    legend_data = [
        {
            'cid': cid,
            'label': community_labels.get(cid, f'Community {cid}'),
            'color': _get_community_color(cid),
            'count': len(nodes_list)
        }
        for cid, nodes_list in sorted(communities.items(), key=lambda x: len(x[1]), reverse=True)
    ]
    
    # Render HTML
    html_content = _render_html_template(nodes_data, edges_data, legend_data, graph)
    
    # Write output
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content)


def _render_html_template(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], 
                          legend: list[dict[str, Any]], graph: nx.Graph[Any] | nx.DiGraph[Any]) -> str:
    """Render HTML template with vis.js visualization."""
    
    nodes_json = json.dumps(nodes, ensure_ascii=False)
    edges_json = json.dumps(edges, ensure_ascii=False)
    legend_json = json.dumps(legend, ensure_ascii=False)
    
    graph_type = 'directed' if isinstance(graph, nx.DiGraph) else 'undirected'
    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()
    
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>SQLfy Schema Graph — {node_count} nodes, {edge_count} edges</title>
  <script src="https://unpkg.com/vis-network@9.1.2/dist/vis-network.min.js"></script>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ 
      display: flex; 
      height: 100vh; 
      background: #0f172a; 
      color: #f1f5f9; 
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }}
    #graph {{ flex: 1; }}
    #sidebar {{ 
      width: 320px; 
      background: #1e2235; 
      border-left: 1px solid rgba(255,255,255,0.1); 
      display: flex; 
      flex-direction: column;
      overflow-y: auto;
    }}
    #search {{ 
      width: 100%; 
      padding: 14px; 
      background: #0f172a; 
      border: 1px solid rgba(255,255,255,0.15); 
      border-radius: 6px;
      color: #f1f5f9;
      font-size: 14px;
      margin: 16px;
      width: calc(100% - 32px);
    }}
    #search:focus {{ outline: 2px solid #7c3aed; outline-offset: 2px; }}
    .section {{ padding: 0 16px 16px; }}
    .section-title {{ 
      font-size: 11px; 
      text-transform: uppercase; 
      letter-spacing: 0.5px; 
      color: #94a3b8; 
      margin-bottom: 12px;
      font-weight: 600;
    }}
    .legend-item {{ 
      padding: 10px 12px; 
      cursor: pointer; 
      display: flex; 
      align-items: center; 
      gap: 12px;
      border-radius: 6px;
      margin-bottom: 4px;
      transition: background 0.15s;
    }}
    .legend-item:hover {{ background: rgba(255,255,255,0.05); }}
    .legend-item.hidden {{ opacity: 0.4; }}
    .legend-dot {{ 
      width: 14px; 
      height: 14px; 
      border-radius: 50%; 
      flex-shrink: 0;
    }}
    .legend-label {{ flex: 1; font-size: 13px; }}
    .legend-count {{ 
      font-size: 12px; 
      color: #94a3b8; 
      font-weight: 500;
    }}
    .stats {{ 
      padding: 16px; 
      background: rgba(124,58,237,0.1); 
      border-radius: 8px;
      margin-bottom: 16px;
    }}
    .stats-row {{ display: flex; justify-content: space-between; margin-bottom: 6px; }}
    .stats-label {{ color: #94a3b8; font-size: 13px; }}
    .stats-value {{ font-weight: 600; font-size: 14px; }}
  </style>
</head>
<body>
  <div id="graph"></div>
  <div id="sidebar">
    <input id="search" type="text" placeholder="Search nodes..." />
    
    <div class="section">
      <div class="stats">
        <div class="stats-row">
          <span class="stats-label">Graph Type</span>
          <span class="stats-value">{graph_type}</span>
        </div>
        <div class="stats-row">
          <span class="stats-label">Nodes</span>
          <span class="stats-value">{node_count}</span>
        </div>
        <div class="stats-row">
          <span class="stats-label">Edges</span>
          <span class="stats-value">{edge_count}</span>
        </div>
      </div>
    </div>
    
    <div class="section">
      <div class="section-title">Communities</div>
      <div id="legend"></div>
    </div>
  </div>
  
  <script>
    const nodesData = {nodes_json};
    const edgesData = {edges_json};
    const legendData = {legend_json};
    
    const nodes = new vis.DataSet(nodesData);
    const edges = new vis.DataSet(edgesData);
    
    const container = document.getElementById('graph');
    const options = {{
      physics: {{
        enabled: true,
        solver: 'forceAtlas2Based',
        forceAtlas2Based: {{
          gravitationalConstant: -80,
          centralGravity: 0.01,
          springLength: 150,
          springConstant: 0.05,
        }},
        stabilization: {{
          iterations: 150,
        }},
      }},
      edges: {{
        smooth: {{
          type: 'continuous',
          roundness: 0.5
        }},
        arrows: {{
          to: {{ enabled: true, scaleFactor: 0.5 }}
        }}
      }},
      nodes: {{
        font: {{
          size: 12,
          color: '#f1f5f9',
          face: 'monospace'
        }},
        borderWidth: 2,
        shadow: true
      }},
      interaction: {{
        hover: true,
        tooltipDelay: 100,
      }}
    }};
    
    const network = new vis.Network(container, {{ nodes, edges }}, options);
    
    // Hidden communities tracking
    const hiddenCommunities = new Set();
    
    // Search functionality
    const searchInput = document.getElementById('search');
    searchInput.addEventListener('input', (e) => {{
      const query = e.target.value.toLowerCase().trim();
      
      if (!query) {{
        // Reset: show all nodes except those in hidden communities
        nodesData.forEach(n => {{
          if (!hiddenCommunities.has(n.community)) {{
            nodes.update({{ id: n.id, hidden: false }});
          }}
        }});
        return;
      }}
      
      // Hide nodes that don't match query
      nodesData.forEach(n => {{
        const matches = n.label.toLowerCase().includes(query) || 
                       n.id.toLowerCase().includes(query) ||
                       n.type.toLowerCase().includes(query);
        const inHiddenCommunity = hiddenCommunities.has(n.community);
        nodes.update({{ id: n.id, hidden: !matches || inHiddenCommunity }});
      }});
    }});
    
    // Legend rendering and toggling
    const legendEl = document.getElementById('legend');
    legendData.forEach(c => {{
      const item = document.createElement('div');
      item.className = 'legend-item';
      item.innerHTML = `
        <div class="legend-dot" style="background-color: ${{c.color}}"></div>
        <div class="legend-label">${{c.label}}</div>
        <div class="legend-count">${{c.count}}</div>
      `;
      
      item.addEventListener('click', () => {{
        if (hiddenCommunities.has(c.cid)) {{
          hiddenCommunities.delete(c.cid);
          item.classList.remove('hidden');
        }} else {{
          hiddenCommunities.add(c.cid);
          item.classList.add('hidden');
        }}
        
        // Update node visibility
        nodesData.forEach(n => {{
          if (n.community === c.cid) {{
            nodes.update({{ id: n.id, hidden: hiddenCommunities.has(c.cid) }});
          }}
        }});
        
        // Re-apply search if active
        const query = searchInput.value.toLowerCase().trim();
        if (query) {{
          searchInput.dispatchEvent(new Event('input'));
        }}
      }});
      
      legendEl.appendChild(item);
    }});
    
    // Node click handler - show neighbors
    network.on('click', (params) => {{
      if (params.nodes.length > 0) {{
        const nodeId = params.nodes[0];
        const neighbors = network.getConnectedNodes(nodeId);
        console.log(`Node: ${{nodeId}}, Neighbors: ${{neighbors.length}}`);
      }}
    }});
  </script>
</body>
</html>"""


# ──────────────────────────────────────────────
# REPORT EXPORT
# ──────────────────────────────────────────────

def export_graph_report(
    graph: nx.Graph[Any] | nx.DiGraph[Any],
    communities: dict[int, list[str]] | None = None,
    output_path: Path | str = Path('GRAPH_REPORT.md')
) -> None:
    """
    Export human-readable GRAPH_REPORT.md with insights.
    
    Includes:
      - Graph metadata (nodes, edges, density)
      - God nodes (high-degree hubs)
      - Community summaries
      - Suggested exploration questions
    
    Args:
        graph: NetworkX graph to analyze
        communities: Optional community assignments (default: auto-compute)
        output_path: Output file path
    """
    if communities is None:
        communities = _compute_communities(graph)
    
    community_labels = _get_community_labels(communities, graph)
    
    # Compute god nodes (top 10 by degree)
    degree_centrality = nx.degree_centrality(graph)
    god_nodes = sorted(degree_centrality.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Compute graph metrics
    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()
    density = nx.density(graph)
    is_connected = nx.is_connected(graph.to_undirected()) if isinstance(graph, nx.DiGraph) else nx.is_connected(graph)
    
    # Build report
    lines = [
        "# Schema Graph Report",
        "",
        "**Generated by SQLfy**",
        "",
        "## Graph Metadata",
        "",
        f"- **Nodes:** {node_count}",
        f"- **Edges:** {edge_count}",
        f"- **Density:** {density:.4f}",
        f"- **Graph Type:** {'Directed' if isinstance(graph, nx.DiGraph) else 'Undirected'}",
        f"- **Connected:** {'Yes' if is_connected else 'No'}",
        "",
        "## God Nodes (Top 10 by Degree Centrality)",
        "",
        "High-degree nodes that serve as central hubs in the schema:",
        "",
        "| Rank | Node | Degree Centrality | Type |",
        "|------|------|-------------------|------|",
    ]
    
    for i, (node_id, centrality) in enumerate(god_nodes, 1):
        node_type = graph.nodes[node_id].get('type', 'unknown')
        lines.append(f"| {i} | `{node_id}` | {centrality:.4f} | {node_type} |")
    
    lines.extend([
        "",
        "## Communities",
        "",
        f"Detected {len(communities)} semantic domain(s):",
        "",
    ])
    
    for cid, nodes in sorted(communities.items(), key=lambda x: len(x[1]), reverse=True):
        label = community_labels.get(cid, f"Community {cid}")
        lines.append(f"### {label}")
        lines.append(f"")
        lines.append(f"- **Size:** {len(nodes)} nodes")
        
        # Node type breakdown
        type_counts: dict[str, int] = {}
        for node in nodes:
            node_type = graph.nodes[node].get('type', 'unknown')
            type_counts[node_type] = type_counts.get(node_type, 0) + 1
        
        lines.append(f"- **Composition:** " + ", ".join(f"{count} {t}" for t, count in sorted(type_counts.items())))
        lines.append("")
    
    lines.extend([
        "## Suggested Exploration Questions",
        "",
        "Use these prompts with the CLI or interactive graph:",
        "",
        "1. **Which tables are most interconnected?**",
        "   ```bash",
        "   sqlfy query 'show tables with most foreign keys'",
        "   ```",
        "",
        "2. **What breaks if I delete table X?**",
        "   ```bash",
        "   sqlfy query 'impact of deleting users'",
        "   ```",
        "",
        "3. **Are there any circular dependencies?**",
        "   ```bash",
        "   sqlfy query 'show cycles'",
        "   ```",
        "",
        "4. **Which tables have no relationships?**",
        "   ```bash",
        "   sqlfy query 'show orphan tables'",
        "   ```",
        "",
        "---",
        "",
        "*This report was generated automatically from your migration files.*",
        "*Re-run `sqlfy graph` to update after schema changes.*",
    ])
    
    report_content = "\n".join(lines)
    
    # Write output
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_content)

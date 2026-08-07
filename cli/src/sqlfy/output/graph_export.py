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

from ..clustering import detect_communities, label_communities

# ──────────────────────────────────────────────
# COMMUNITY DETECTION (Feature #4)
# ──────────────────────────────────────────────

def _compute_communities(
    graph: nx.Graph[Any] | nx.DiGraph[Any],
    resolution: float = 1.0,
    min_cohesion: float = 0.1,
    enable_splitting: bool = True,
) -> dict[int, list[str]]:
    """
    Compute community assignments for nodes using Leiden/Louvain.

    Args:
        graph: NetworkX graph to analyze
        resolution: Resolution parameter (>1 = more communities, <1 = fewer)
        min_cohesion: Minimum cohesion score to keep a community
        enable_splitting: Whether to split oversized communities

    Returns:
        Dictionary mapping community ID to list of node IDs
    """
    result = detect_communities(
        graph,
        resolution=resolution,
        min_cohesion=min_cohesion,
        enable_splitting=enable_splitting,
    )
    return result.communities


def _get_community_labels(communities: dict[int, list[str]], graph: nx.Graph[Any] | nx.DiGraph[Any]) -> dict[int, str]:
    """
    Generate human-readable labels for communities.

    Args:
        communities: Community assignments
        graph: NetworkX graph

    Returns:
        Dictionary mapping community ID to label
    """
    return label_communities(communities, graph)


# ──────────────────────────────────────────────
# JSON EXPORT
# ──────────────────────────────────────────────

def export_graph_json(
    graph: nx.Graph[Any] | nx.DiGraph[Any],
    communities: dict[int, list[str]] | None = None,
    output_path: Path | str = Path('graph.json'),
    resolution: float = 1.0,
    min_cohesion: float = 0.1,
    enable_splitting: bool = True,
) -> None:
    """
    Export graph in NetworkX node-link JSON format.

    Compatible with NetworkX json_graph.node_link_data() format.
    Enriches nodes with community assignments and degree centrality.

    Args:
        graph: NetworkX graph to export
        communities: Optional community assignments (default: auto-compute with Leiden/Louvain)
        output_path: Output file path
        resolution: Community detection resolution (>1 = more communities)
        min_cohesion: Minimum cohesion score for communities
        enable_splitting: Whether to split oversized communities
    """
    if communities is None:
        communities = _compute_communities(graph, resolution, min_cohesion, enable_splitting)

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
    output_path: Path | str = Path('graph.html'),
    resolution: float = 1.0,
    min_cohesion: float = 0.1,
    enable_splitting: bool = True,
    optimize_html: bool = False,
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
        graph: NetworkX graph to export
        communities: Optional community assignments (default: auto-compute with Leiden/Louvain)
        output_path: Output file path
        resolution: Community detection resolution (>1 = more communities)
        min_cohesion: Minimum cohesion score for communities
        enable_splitting: Whether to split oversized communities
        optimize_html: If True, freeze physics after stabilization and generate tooltips dynamically on-demand
    """
    if communities is None:
        communities = _compute_communities(graph, resolution, min_cohesion, enable_splitting)

    community_labels = _get_community_labels(communities, graph)

    # Map node → community ID
    node_community: dict[str, int] = {}
    for cid, nodes in communities.items():
        for node in nodes:
            node_community[node] = cid

    # Prepare vis.js nodes and column lookup table
    nodes_data = []
    table_columns_data: dict[str, list[dict[str, Any]]] = {}
    valid_node_ids = set()

    for node_id, attrs in graph.nodes(data=True):
        ntype = attrs.get('type', 'unknown')
        if ntype == 'column':
            continue  # Columns are stored inside table node attributes

        valid_node_ids.add(node_id)
        cid = node_community.get(node_id, 0)
        color = _get_community_color(cid)
        degree = graph.degree(node_id)

        cols = attrs.get('columns', [])
        if cols:
            table_columns_data[node_id] = cols

        if optimize_html:
            title_str = f"<b>{ntype.capitalize()}: {node_id}</b><br/>Columns: {attrs.get('column_count', len(cols))}<br/>Connections: {degree}"
        else:
            cols_summary = ""
            if cols:
                cols_lines = [
                    f"• {c['name']} <i>({c['type']})</i>{' [PK]' if c.get('primary_key') else ''}"
                    for c in cols[:12]
                ]
                if len(cols) > 12:
                    cols_lines.append(f"<i>... +{len(cols) - 12} more columns</i>")
                cols_summary = "<br/><br/><b>Columns:</b><br/>" + "<br/>".join(cols_lines)

            title_str = (
                f"<b>{ntype.capitalize()}: {node_id}</b><br/>"
                f"Columns: {attrs.get('column_count', len(cols))}<br/>"
                f"Connections: {degree}<br/>"
                f"Domain: {community_labels.get(cid, '')}"
                f"{cols_summary}"
            )

        nodes_data.append({
            'id': node_id,
            'label': attrs.get('label', node_id),
            'color': color,
            'size': min(50, 10 + degree * 2),
            'community': cid,
            'community_name': community_labels.get(cid, f'Community {cid}'),
            'type': ntype,
            'degree': degree,
            'title': title_str,
        })

    # Prepare vis.js edges
    edges_data = []
    for u, v, attrs in graph.edges(data=True):
        if u not in valid_node_ids or v not in valid_node_ids:
            continue
        relation = attrs.get('relation', '')
        confidence = attrs.get('confidence', 'EXTRACTED')

        edges_data.append({
            'id': f"{u}→{v}:{relation}",
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
    html_content = _render_html_template(
        nodes_data, edges_data, legend_data, graph,
        table_columns=table_columns_data, optimize_html=optimize_html
    )

    # Write output
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content)


def _render_html_template(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    legend: list[dict[str, Any]],
    graph: nx.Graph[Any] | nx.DiGraph[Any],
    table_columns: dict[str, Any] | None = None,
    optimize_html: bool = False,
) -> str:
    """Render HTML template with vis.js visualization."""

    nodes_json = json.dumps(nodes, ensure_ascii=False)
    edges_json = json.dumps(edges, ensure_ascii=False)
    legend_json = json.dumps(legend, ensure_ascii=False)
    table_columns_json = json.dumps(table_columns or {}, ensure_ascii=False)

    graph_type = 'directed' if isinstance(graph, nx.DiGraph) else 'undirected'
    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()

    freeze_physics_script = """
    network.once('stabilizationIterationsDone', function() {
      network.setOptions({ physics: { enabled: false } });
      console.log('Layout stabilized - physics simulation frozen for maximum performance.');
    });
    """ if optimize_html else ""

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>SQLfy Schema Graph - {node_count} nodes, {edge_count} edges</title>
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
      width: 360px;
      background: #1e2235;
      border-left: 1px solid rgba(255,255,255,0.1);
      display: flex;
      flex-direction: column;
      overflow-y: auto;
    }}
    .search-container {{
      position: relative;
      padding: 16px 16px 8px;
    }}
    #search {{
      width: 100%;
      padding: 12px 14px;
      background: #0f172a;
      border: 1px solid rgba(255,255,255,0.2);
      border-radius: 6px;
      color: #f1f5f9;
      font-size: 14px;
    }}
    #search:focus {{ outline: 2px solid #7c3aed; outline-offset: 2px; }}
    #search-results {{
      position: absolute;
      top: 60px;
      left: 16px;
      right: 16px;
      background: #0f172a;
      border: 1px solid rgba(255,255,255,0.2);
      border-radius: 6px;
      max-height: 220px;
      overflow-y: auto;
      z-index: 100;
      display: none;
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
    }}
    #search-results.active {{ display: block; }}
    .search-item {{
      padding: 10px 14px;
      cursor: pointer;
      font-size: 13px;
      font-family: monospace;
      border-bottom: 1px solid rgba(255,255,255,0.05);
      display: flex;
      justify-content: space-between;
    }}
    .search-item:hover {{ background: #7c3aed; color: #fff; }}
    .section {{ padding: 8px 16px 16px; }}
    .section-title {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: #94a3b8;
      margin: 12px 0 8px;
      font-weight: 600;
    }}
    .legend-item {{
      padding: 8px 12px;
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.06);
      border-radius: 6px;
      margin-bottom: 6px;
      display: flex;
      align-items: center;
      cursor: pointer;
      user-select: none;
      transition: all 0.15s ease;
    }}
    .legend-item:hover {{ background: rgba(255,255,255,0.08); }}
    .legend-item.hidden {{ opacity: 0.35; text-decoration: line-through; }}
    .legend-dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
      margin-right: 10px;
      flex-shrink: 0;
    }}
    .legend-label {{ flex: 1; font-size: 13px; font-weight: 500; }}
    .legend-count {{ font-size: 12px; color: #94a3b8; font-family: monospace; }}
    #inspector {{
      padding: 16px;
      background: rgba(255,255,255,0.02);
      border-top: 1px solid rgba(255,255,255,0.1);
      display: none;
    }}
    #inspector.active {{ display: block; }}
    .col-item {{
      font-size: 12px;
      font-family: monospace;
      padding: 4px 0;
      border-bottom: 1px dashed rgba(255,255,255,0.05);
    }}
    .col-pk {{ color: #fbbf24; font-weight: bold; }}
    .focus-btn {{
      margin-top: 10px;
      width: 100%;
      padding: 8px;
      background: #7c3aed;
      color: #fff;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-weight: 600;
      font-size: 12px;
    }}
    .focus-btn:hover {{ background: #6d28d9; }}
  </style>
</head>
<body>
  <div id="graph"></div>
  <div id="sidebar">
    <div class="search-container">
      <input type="text" id="search" placeholder="Type table/seq name to search & focus..." autocomplete="off" />
      <div id="search-results"></div>
    </div>

    <div class="section">
      <div class="section-title">Object Types</div>
      <div id="type-legend"></div>

      <div class="section-title">Top Domains / Communities</div>
      <div id="legend"></div>
    </div>

    <div id="inspector">
      <div class="section-title">Node Inspector</div>
      <div id="inspector-content">Select a node to inspect columns & connections.</div>
    </div>
  </div>

  <script>
    const nodesData = {nodes_json};
    const edgesData = {edges_json};
    const legendData = {legend_json};
    const tableColumns = {table_columns_json};

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
    {freeze_physics_script}

    const hiddenTypes = new Set();
    const hiddenCommunities = new Set();

    function updateVisibility() {{
      const updates = [];
      nodesData.forEach(n => {{
        const isTypeHidden = hiddenTypes.has(n.type);
        const isCommHidden = hiddenCommunities.has(n.community);
        updates.push({{ id: n.id, hidden: isTypeHidden || isCommHidden }});
      }});
      nodes.update(updates);
    }}

    // Render Type Legend
    const typeLegendEl = document.getElementById('type-legend');
    const typeCounts = {{}};
    nodesData.forEach(n => typeCounts[n.type] = (typeCounts[n.type] || 0) + 1);

    const typeColors = {{ 'table': '#3b82f6', 'sequence': '#10b981', 'unknown': '#94a3b8' }};
    Object.keys(typeCounts).forEach(type => {{
      const item = document.createElement('div');
      item.className = 'legend-item';
      item.innerHTML = `
        <div class="legend-dot" style="background-color: ${{typeColors[type] || '#8b5cf6'}}"></div>
        <div class="legend-label">${{type.toUpperCase()}}S</div>
        <div class="legend-count">${{typeCounts[type]}}</div>
      `;
      item.addEventListener('click', () => {{
        if (hiddenTypes.has(type)) {{
          hiddenTypes.delete(type);
          item.classList.remove('hidden');
        }} else {{
          hiddenTypes.add(type);
          item.classList.add('hidden');
        }}
        updateVisibility();
      }});
      typeLegendEl.appendChild(item);
    }});

    // Render Top Communities (limit to top 15 in legend sidebar)
    const legendEl = document.getElementById('legend');
    const topLegend = legendData.slice(0, 15);

    topLegend.forEach(c => {{
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
        updateVisibility();
      }});

      legendEl.appendChild(item);
    }});

    // Interactive Search with Live Dropdown & Auto Camera Focus
    const searchInput = document.getElementById('search');
    const searchResults = document.getElementById('search-results');

    function focusOnNode(nodeId) {{
      network.focus(nodeId, {{
        scale: 1.2,
        animation: {{ duration: 500, easingFunction: 'easeInOutQuad' }}
      }});
      network.selectNodes([nodeId]);
      showInspector(nodeId);
    }}

    searchInput.addEventListener('input', (e) => {{
      const query = e.target.value.toLowerCase().trim();
      searchResults.innerHTML = '';

      if (!query) {{
        searchResults.classList.remove('active');
        return;
      }}

      const matches = nodesData.filter(n =>
        n.id.toLowerCase().includes(query) || n.label.toLowerCase().includes(query)
      ).slice(0, 15);

      if (matches.length === 0) {{
        searchResults.classList.remove('active');
        return;
      }}

      matches.forEach(m => {{
        const div = document.createElement('div');
        div.className = 'search-item';
        div.innerHTML = `<span>${{m.id}}</span><span style="opacity:0.7">${{m.type}}</span>`;
        div.addEventListener('click', () => {{
          searchInput.value = m.id;
          searchResults.classList.remove('active');
          focusOnNode(m.id);
        }});
        searchResults.appendChild(div);
      }});

      searchResults.classList.add('active');
    }});

    document.addEventListener('click', (e) => {{
      if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {{
        searchResults.classList.remove('active');
      }}
    }});

    function highlightConnected(selectedId) {{
      const connectedNodes = new Set(network.getConnectedNodes(selectedId));
      connectedNodes.add(selectedId);
      const connectedEdgeIds = new Set(network.getConnectedEdges(selectedId));

      const nodeUpdates = nodesData.map(n => {{
        if (connectedNodes.has(n.id)) {{
          return {{ id: n.id, opacity: 1.0, font: {{ color: '#ffffff', size: n.id === selectedId ? 15 : 13 }} }};
        }} else {{
          return {{ id: n.id, opacity: 0.12, font: {{ color: '#475569', size: 10 }} }};
        }}
      }});

      const edgeUpdates = edgesData.map(e => {{
        if (connectedEdgeIds.has(e.id) || e.from === selectedId || e.to === selectedId) {{
          return {{
            id: e.id,
            color: {{ color: '#38bdf8', opacity: 1.0, highlight: '#38bdf8' }},
            width: 4,
            arrows: {{ to: {{ enabled: true, scaleFactor: 1.0 }} }}
          }};
        }} else {{
          return {{
            id: e.id,
            color: {{ color: '#1e293b', opacity: 0.05 }},
            width: 1
          }};
        }}
      }});

      nodes.update(nodeUpdates);
      edges.update(edgeUpdates);
    }}

    function resetHighlight() {{
      const nodeUpdates = nodesData.map(n => ({{
        id: n.id,
        opacity: 1.0,
        font: {{ color: '#f1f5f9', size: 12 }}
      }}));

      const edgeUpdates = edgesData.map(e => ({{
        id: e.id,
        color: {{ color: '#94a3b8', opacity: e.dashes ? 0.6 : 1.0 }},
        width: e.width || 1,
        arrows: {{ to: {{ enabled: true, scaleFactor: 0.5 }} }}
      }}));

      nodes.update(nodeUpdates);
      edges.update(edgeUpdates);
    }}

    function showInspector(nodeId) {{
      highlightConnected(nodeId);

      const nodeObj = nodesData.find(n => n.id === nodeId);
      const cols = tableColumns[nodeId] || [];
      const neighbors = network.getConnectedNodes(nodeId);

      let colsHtml = '';
      if (cols.length > 0) {{
        colsHtml = '<div style="margin-top:10px;"><b>Columns (' + cols.length + '):</b></div>' +
          cols.map(c => `<div class="col-item">${{c.primary_key ? '<span class="col-pk">[PK]</span> ' : ''}}${{c.name}} <span style="color:#94a3b8">(${{c.type}})</span></div>`).join('');
      }}

      inspectorContent.innerHTML = `
        <div style="font-size:15px; font-weight:bold; color:#7c3aed; margin-bottom:4px;">${{nodeId}}</div>
        <div style="font-size:12px; color:#94a3b8;">Type: ${{nodeObj ? nodeObj.type.toUpperCase() : 'TABLE'}} | Domain: ${{nodeObj ? nodeObj.community_name : ''}}</div>
        <div style="font-size:12px; color:#94a3b8; margin-bottom:10px;">Connections: ${{neighbors.length}}</div>
        <button class="focus-btn" onclick="focusOnNode('${{nodeId}}')">🔍 Focus Camera On Table</button>
        ${{colsHtml}}
      `;
      inspectorEl.classList.add('active');
    }}

    network.on('selectNode', (params) => {{
      if (params.nodes.length > 0) showInspector(params.nodes[0]);
    }});

    network.on('deselectNode', () => {{
      resetHighlight();
      inspectorEl.classList.remove('active');
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
    output_path: Path | str = Path('GRAPH_REPORT.md'),
    resolution: float = 1.0,
    min_cohesion: float = 0.1,
    enable_splitting: bool = True,
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
        communities: Optional community assignments (default: auto-compute with Leiden/Louvain)
        output_path: Output file path
        resolution: Community detection resolution (>1 = more communities)
        min_cohesion: Minimum cohesion score for communities
        enable_splitting: Whether to split oversized communities
    """
    if communities is None:
        communities = _compute_communities(graph, resolution, min_cohesion, enable_splitting)

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
        lines.append("")
        lines.append(f"- **Size:** {len(nodes)} nodes")

        # Node type breakdown
        type_counts: dict[str, int] = {}
        for node in nodes:
            node_type = graph.nodes[node].get('type', 'unknown')
            type_counts[node_type] = type_counts.get(node_type, 0) + 1

        lines.append("- **Composition:** " + ", ".join(f"{count} {t}" for t, count in sorted(type_counts.items())))
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

"""
test_html_optimization.py
==========================
Unit tests for gated --optimize-html visualization optimizations.
"""

from __future__ import annotations

import networkx as nx
from sqlfy.output.graph_export import export_graph_html


def test_export_graph_html_optimized(tmp_path):
    g = nx.DiGraph()
    g.add_node("THE.USERS", type="table", columns=[{"name": "ID", "type": "NUMBER", "primary_key": True}])
    g.add_node("THE.ORDERS", type="table", columns=[{"name": "ID", "type": "NUMBER", "primary_key": True}])
    g.add_edge("THE.ORDERS", "THE.USERS", relation="foreign_key", confidence="EXTRACTED")

    html_file = tmp_path / "graph_opt.html"
    export_graph_html(g, output_path=html_file, optimize_html=True)

    assert html_file.exists()
    content = html_file.read_text(encoding="utf-8")

    # Verify freeze physics script and tableColumns dictionary are generated
    assert "physics simulation frozen for maximum performance" in content
    assert "const tableColumns =" in content
    assert "THE.USERS" in content

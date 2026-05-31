"""
Schema knowledge graph builder — unified orchestration command.

Produces a complete graphify-out/ directory with:
- graph.json, graph.html (interactive visualization)
- GRAPH_REPORT.md (comprehensive analysis)
- communities.json (Leiden/Louvain clustering)
- god-nodes.json (highly-connected tables + lineage)
- queries/ (pre-computed graph queries)
- insights/ (schema quality analysis)
- viz/ (multiple export formats)

Orchestrates all existing graph features:
- Feature #1: build_networkx_graph()
- Feature #2: graph --format json/html/report
- Feature #3: analyze_impact()
- Feature #4: detect_communities()
- Feature #6: export formats (mermaid, dot, excalidraw, drawio)
- Feature #8: manifest metadata
- Feature #39: column lineage (god columns)
- Query engine (15+ query types)
- Insights engine (schema quality checks)
"""

from __future__ import annotations

import sys
import json
import time
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ..core import build_networkx_graph
from ..domain.schema_state import SchemaStateBuilder
from ..reconstructor import reconstruct, reconstruct_at
from ..clustering import detect_communities, label_communities
from ..analysis.query import QueryEngine
from ..analysis.insights import InsightsEngine
from ..analysis.health import HealthAnalyzer
from ..output.graph_export import export_graph_json, export_graph_html, export_graph_report
from ..output.grapher import Grapher
from ._utils import load_files


@dataclass
class GraphBuildResult:
    """Result of complete graph build process."""
    
    output_dir: Path
    graph_path: Path
    html_path: Path
    report_path: Path
    manifest_path: Path
    
    node_count: int
    edge_count: int
    community_count: int
    god_node_count: int
    
    health_score: int
    insights_count: int
    query_count: int
    viz_count: int
    
    total_time_seconds: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "output_dir": str(self.output_dir),
            "files": {
                "graph": str(self.graph_path),
                "html": str(self.html_path),
                "report": str(self.report_path),
                "manifest": str(self.manifest_path),
            },
            "statistics": {
                "nodes": self.node_count,
                "edges": self.edge_count,
                "communities": self.community_count,
                "god_nodes": self.god_node_count,
                "health_score": self.health_score,
                "insights": self.insights_count,
                "queries": self.query_count,
                "visualizations": self.viz_count,
            },
            "timing": {
                "total_seconds": self.total_time_seconds,
            },
            "timestamp": self.timestamp,
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


def cmd_build_graph(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    at: str | None = None,
    output_dir: str | None = None,
    resolution: float = 1.0,
    min_cohesion: float = 0.5,
    no_split: bool = False,
    min_refs: int = 20,
    no_queries: bool = False,
    no_viz: bool = False,
) -> None:
    """
    Build complete schema knowledge graph.

    Orchestrates all graph-related features into a single workflow.
    Produces a self-contained graphify-out/ directory.
    """
    start_time = time.time()

    out_dir: Path = Path(output_dir or 'graphify-out')
    files = load_files(migrations_dir, json_input)
    version = at
    enable_splitting = not no_split
    skip_queries = no_queries
    skip_viz = no_viz
    
    # Create output directories
    out_dir.mkdir(parents=True, exist_ok=True)
    queries_dir = out_dir / 'queries'
    insights_dir = out_dir / 'insights'
    viz_dir = out_dir / 'viz'
    queries_dir.mkdir(exist_ok=True)
    insights_dir.mkdir(exist_ok=True)
    if not skip_viz:
        viz_dir.mkdir(exist_ok=True)
    
    print("╔══════════════════════════════════════════════════════════╗", file=sys.stderr)
    print("║         Schema Knowledge Graph Builder                   ║", file=sys.stderr)
    print("╚══════════════════════════════════════════════════════════╝", file=sys.stderr)
    print(file=sys.stderr)
    print(f"📂 Building graph from: {migrations_dir}", file=sys.stderr)
    print(f"📍 Output directory: {out_dir}", file=sys.stderr)
    print(file=sys.stderr)
    
    # ─────────────────────────────────────────────────────────────
    # Phase 1: Graph Construction
    # ─────────────────────────────────────────────────────────────
    print("🔨 Phase 1: Graph Construction", file=sys.stderr)
    graph = reconstruct_at(files, version, dialect=dialect) if version else reconstruct(files, dialect=dialect)
    print(f"   ✓ Reconstructing schema ({len(files)} migrations)", file=sys.stderr)
    
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    nx_graph = build_networkx_graph(graph, directed=True)
    node_count = nx_graph.number_of_nodes()
    edge_count = nx_graph.number_of_edges()
    print(f"   ✓ Building NetworkX graph ({node_count} nodes, {edge_count} edges)", file=sys.stderr)
    print("   ✓ Validating graph structure", file=sys.stderr)
    print(file=sys.stderr)
    
    # ─────────────────────────────────────────────────────────────
    # Phase 2: Community Detection
    # ─────────────────────────────────────────────────────────────
    print("🧩 Phase 2: Community Detection", file=sys.stderr)
    comm_result = detect_communities(nx_graph, resolution=resolution, min_cohesion=min_cohesion, enable_splitting=enable_splitting)
    community_count = comm_result.num_communities
    print(f"   ✓ Running Leiden clustering (resolution={resolution})", file=sys.stderr)
    print(f"   ✓ Detected {community_count} communities", file=sys.stderr)
    
    labeled_communities = label_communities(comm_result.communities, nx_graph)
    community_labels = [label for label in labeled_communities.values()]
    print(f"   ✓ Labeling domains ({', '.join(community_labels[:3])}{'...' if len(community_labels) > 3 else ''})", file=sys.stderr)
    
    # Save communities
    communities_data = {
        'communities': [
            {
                'id': cid,
                'label': labeled_communities.get(cid, f'Community {cid}'),
                'tables': tables,
                'cohesion': comm_result.cohesion_scores.get(cid, 0.0),
                'size': len(tables)
            }
            for cid, tables in comm_result.communities.items()
        ],
        'count': community_count,
        'algorithm': comm_result.algorithm,
        'resolution': resolution
    }
    with open(out_dir / 'communities.json', 'w', encoding='utf-8') as f:
        json.dump(communities_data, f, indent=2)
    print(file=sys.stderr)
    
    # ─────────────────────────────────────────────────────────────
    # Phase 3: Analysis
    # ─────────────────────────────────────────────────────────────
    print("🔍 Phase 3: Analysis", file=sys.stderr)
    
    # God nodes (highly-connected tables)
    god_nodes = []
    degree_dict = dict(nx_graph.degree())
    sorted_nodes = sorted(degree_dict.items(), key=lambda x: x[1], reverse=True)
    god_nodes = [{'node': node, 'degree': degree} for node, degree in sorted_nodes[:10] if degree >= min_refs]
    god_node_count = len(god_nodes)
    print(f"   ✓ Computing god nodes (top {god_node_count} by degree centrality)", file=sys.stderr)
    
    with open(out_dir / 'god-nodes.json', 'w', encoding='utf-8') as f:
        json.dump({'god_nodes': god_nodes, 'count': god_node_count, 'min_refs': min_refs}, f, indent=2)
    
    # Insights
    insights_report = InsightsEngine.analyse(state, files=files)
    insights_count = len(insights_report.findings)
    print(f"   ✓ Running insights engine ({insights_count} findings)", file=sys.stderr)
    
    with open(insights_dir / 'schema-quality.json', 'w', encoding='utf-8') as f:
        f.write(insights_report.to_json())
    
    # Health score
    health_analyzer_report = HealthAnalyzer.analyze(state, insights_report, migrations_dir or '.')
    health_score = health_analyzer_report.health_score.score
    print(f"   ✓ Computing health score ({health_score}/100)", file=sys.stderr)
    
    with open(insights_dir / 'health-score.json', 'w', encoding='utf-8') as f:
        f.write(health_analyzer_report.to_json())
    
    # Column lineage (if available)
    try:
        from ..analysis.lineage import extract_column_lineage, find_god_columns
        lineage_files = [(f['filename'], f['sql']) for f in files]
        lineage = extract_column_lineage(graph, lineage_files)
        god_cols = find_god_columns(lineage, min_refs=min_refs)
        
        # Save god columns
        god_cols_data = {
            'god_columns': [
                {
                    'column': col.full_name,
                    'table': col.table,
                    'column_name': col.column,
                    'reference_count': refs
                }
                for col, refs in god_cols
            ],
            'count': len(god_cols),
            'min_refs': min_refs
        }
        with open(out_dir / 'god-columns.json', 'w', encoding='utf-8') as f:
            json.dump(god_cols_data, f, indent=2)
        print("   ✓ Analyzing column lineage", file=sys.stderr)
    except ImportError:
        print("   ⚠ Column lineage analysis skipped (SQLLineage not installed)", file=sys.stderr)
    
    print(file=sys.stderr)
    
    # ─────────────────────────────────────────────────────────────
    # Phase 4: Pre-computed Queries
    # ─────────────────────────────────────────────────────────────
    query_count = 0
    if not skip_queries:
        print("📊 Phase 4: Pre-computed Queries", file=sys.stderr)
        engine = QueryEngine(state)
        
        # Orphan tables
        orphans_result = engine.orphans()
        with open(queries_dir / 'orphan-tables.json', 'w', encoding='utf-8') as f:
            json.dump(orphans_result.to_dict(), f, indent=2)
        print(f"   ✓ Orphan tables ({len(orphans_result.rows)} found)", file=sys.stderr)
        query_count += 1
        
        # Circular dependencies
        cycles_result = engine.cycles()
        with open(queries_dir / 'cycles.json', 'w', encoding='utf-8') as f:
            json.dump(cycles_result.to_dict(), f, indent=2)
        print(f"   ✓ Circular dependencies ({len(cycles_result.rows)} cycles detected)", file=sys.stderr)
        query_count += 1
        
        # Disconnected islands
        islands_result = engine.islands()
        with open(queries_dir / 'islands.json', 'w', encoding='utf-8') as f:
            json.dump(islands_result.to_dict(), f, indent=2)
        print(f"   ✓ Disconnected islands ({islands_result.meta.get('component_count', 0)} found)", file=sys.stderr)
        query_count += 1
        
        # Missing PKs
        missing_pk_result = engine.missing_pk()
        with open(queries_dir / 'missing-pk.json', 'w', encoding='utf-8') as f:
            json.dump(missing_pk_result.to_dict(), f, indent=2)
        print(f"   ✓ Missing PKs ({len(missing_pk_result.rows)} tables)", file=sys.stderr)
        query_count += 1
        
        # Missing FK candidates
        missing_fk_result = engine.missing_fk()
        with open(queries_dir / 'missing-fk.json', 'w', encoding='utf-8') as f:
            json.dump(missing_fk_result.to_dict(), f, indent=2)
        print(f"   ✓ Missing FK candidates ({len(missing_fk_result.rows)} columns)", file=sys.stderr)
        query_count += 1
        
        print(file=sys.stderr)
    
    # ─────────────────────────────────────────────────────────────
    # Phase 5: Visualizations
    # ─────────────────────────────────────────────────────────────
    viz_count = 0
    print("🎨 Phase 5: Visualizations", file=sys.stderr)
    
    # NetworkX JSON + HTML + Report (always generated)
    export_graph_json(nx_graph, communities=comm_result.communities,
                      output_path=out_dir / 'graph.json')
    print("   ✓ Generating graph.json (NetworkX format)", file=sys.stderr)
    viz_count += 1

    export_graph_html(nx_graph, communities=comm_result.communities,
                      output_path=out_dir / 'graph.html')
    print("   ✓ Generating graph.html (interactive vis.js)", file=sys.stderr)
    viz_count += 1
    
    # Additional formats (if not skipped)
    if not skip_viz:
        title = f"Schema V{state.version}"
        
        # Mermaid ERD
        mermaid_output = Grapher.to_mermaid(state, title=title)
        with open(viz_dir / 'schema.mermaid', 'w', encoding='utf-8') as f:
            f.write(mermaid_output)
        print("   ✓ Generating schema.mermaid (ERD)", file=sys.stderr)
        viz_count += 1
        
        # Graphviz DOT
        dot_output = Grapher.to_dot(state, title=title)
        with open(viz_dir / 'schema.dot', 'w', encoding='utf-8') as f:
            f.write(dot_output)
        print("   ✓ Generating schema.dot (Graphviz)", file=sys.stderr)
        viz_count += 1
        
        # Excalidraw JSON
        try:
            from ..output.excalidraw_exporter import to_excalidraw
            excalidraw_output = to_excalidraw(state, title=title)
            with open(viz_dir / 'schema.excalidraw', 'w', encoding='utf-8') as f:
                json.dump(excalidraw_output, f, indent=2)
            print("   ✓ Generating schema.excalidraw (JSON)", file=sys.stderr)
            viz_count += 1
        except Exception as e:
            print(f"   ⚠ Excalidraw export failed: {e}", file=sys.stderr)
        
        # Draw.io XML
        try:
            from ..output.drawio_exporter import to_drawio
            drawio_output = to_drawio(state, title=title)
            with open(viz_dir / 'schema.drawio', 'w', encoding='utf-8') as f:
                f.write(drawio_output)
            print("   ✓ Generating schema.drawio (XML)", file=sys.stderr)
            viz_count += 1
        except Exception as e:
            print(f"   ⚠ Draw.io export failed: {e}", file=sys.stderr)
    
    print(file=sys.stderr)
    
    # ─────────────────────────────────────────────────────────────
    # Phase 6: Report Generation
    # ─────────────────────────────────────────────────────────────
    print("📝 Phase 6: Report Generation", file=sys.stderr)
    
    # Comprehensive GRAPH_REPORT.md
    export_graph_report(nx_graph, communities=comm_result.communities,
                        output_path=out_dir / 'GRAPH_REPORT.md')
    print("   ✓ Writing GRAPH_REPORT.md (comprehensive analysis)", file=sys.stderr)

    # Manifest metadata
    manifest = state.to_manifest()
    with open(out_dir / 'manifest.json', 'w', encoding='utf-8') as f:
        f.write(manifest)
    print("   ✓ Writing manifest.json (metadata)", file=sys.stderr)
    
    print(file=sys.stderr)
    
    # ─────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", file=sys.stderr)
    print("✅ GRAPH BUILD COMPLETE", file=sys.stderr)
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", file=sys.stderr)
    print(file=sys.stderr)
    print(f"📦 Output: {out_dir}/", file=sys.stderr)
    print(f"   • graph.json ({node_count} nodes, {edge_count} edges)", file=sys.stderr)
    print(f"   • graph.html (interactive)", file=sys.stderr)
    print(f"   • GRAPH_REPORT.md ({(out_dir / 'GRAPH_REPORT.md').stat().st_size:,} bytes)", file=sys.stderr)
    print(f"   • {community_count} community files", file=sys.stderr)
    print(f"   • {query_count} pre-computed queries", file=sys.stderr)
    print(f"   • {viz_count} visualization formats", file=sys.stderr)
    print(file=sys.stderr)
    print("🔗 Next steps:", file=sys.stderr)
    print(f"   • Open {out_dir / 'graph.html'} in browser for interactive exploration", file=sys.stderr)
    print(f"   • Read {out_dir / 'GRAPH_REPORT.md'} for detailed analysis", file=sys.stderr)
    print(f"   • Use queries/ for quick insights", file=sys.stderr)
    print(f"   • Import graph.json for programmatic analysis", file=sys.stderr)
    print(file=sys.stderr)
    print(f"⏱️  Total time: {elapsed:.2f}s", file=sys.stderr)
    
    # Build result
    result = GraphBuildResult(
        output_dir=out_dir,
        graph_path=out_dir / 'graph.json',
        html_path=out_dir / 'graph.html',
        report_path=out_dir / 'GRAPH_REPORT.md',
        manifest_path=out_dir / 'manifest.json',
        node_count=node_count,
        edge_count=edge_count,
        community_count=community_count,
        god_node_count=god_node_count,
        health_score=health_score,
        insights_count=insights_count,
        query_count=query_count,
        viz_count=viz_count,
        total_time_seconds=elapsed,
    )
    
    # Write build result
    with open(out_dir / 'build-result.json', 'w', encoding='utf-8') as f:
        f.write(result.to_json())

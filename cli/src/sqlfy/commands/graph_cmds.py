"""Graph commands: graph, graph-migrations."""

from __future__ import annotations

import sys
import argparse
from pathlib import Path

from ..reconstructor import reconstruct, reconstruct_at
from ..domain.schema_state import SchemaStateBuilder
from ..output.grapher import Grapher
from .io import load_files, write_output


def cmd_graph(args: argparse.Namespace) -> None:
    files = load_files(args.migrations_dir, args.json_input)
    dialect = getattr(args, 'dialect', 'oracle')
    graph = (
        reconstruct_at(files, args.at, dialect=dialect)
        if args.at
        else reconstruct(files, dialect=dialect)
    )
    state = SchemaStateBuilder.from_graph(graph)
    fmt = (args.format or 'dot').lower()
    title = getattr(args, 'title', '') or f'Schema V{state.version}'

    if fmt in ('dot', 'mermaid', 'excalidraw', 'drawio', 'summary'):
        if fmt == 'dot':
            output = Grapher.to_dot(state, title=title)
        elif fmt == 'mermaid':
            output = Grapher.to_mermaid(state, title=title)
        elif fmt == 'excalidraw':
            from ..output.excalidraw_exporter import to_excalidraw
            import json
            output = json.dumps(to_excalidraw(state, title=title), indent=2)
        elif fmt == 'drawio':
            from ..output.drawio_exporter import to_drawio
            output = to_drawio(state, title=title)
        else:
            output = Grapher.to_summary(state)
        write_output(output, args.out)
        return

    from ..core import build_networkx_graph
    from ..output.graph_export import export_graph_json, export_graph_html, export_graph_report

    nx_graph = build_networkx_graph(graph, directed=True)
    output_dir = Path(getattr(args, 'output_dir', None) or 'sqlfy-out')
    output_dir.mkdir(parents=True, exist_ok=True)
    resolution = getattr(args, 'resolution', 1.0)
    min_cohesion = getattr(args, 'min_cohesion', 0.1)
    enable_splitting = not getattr(args, 'no_split', False)

    if fmt == 'json':
        p = output_dir / 'graph.json'
        export_graph_json(nx_graph, output_path=p, resolution=resolution,
                          min_cohesion=min_cohesion, enable_splitting=enable_splitting)
        print(f'✓ Exported NetworkX graph to {p}', file=sys.stderr)
    elif fmt == 'html':
        p = output_dir / 'graph.html'
        export_graph_html(nx_graph, output_path=p, resolution=resolution,
                          min_cohesion=min_cohesion, enable_splitting=enable_splitting)
        print(f'✓ Exported interactive visualization to {p}', file=sys.stderr)
    elif fmt == 'report':
        p = output_dir / 'GRAPH_REPORT.md'
        export_graph_report(nx_graph, output_path=p, resolution=resolution,
                            min_cohesion=min_cohesion, enable_splitting=enable_splitting)
        print(f'✓ Exported graph report to {p}', file=sys.stderr)
    elif fmt == 'all':
        export_graph_json(nx_graph, output_path=output_dir / 'graph.json',
                          resolution=resolution, min_cohesion=min_cohesion, enable_splitting=enable_splitting)
        export_graph_html(nx_graph, output_path=output_dir / 'graph.html',
                          resolution=resolution, min_cohesion=min_cohesion, enable_splitting=enable_splitting)
        export_graph_report(nx_graph, output_path=output_dir / 'GRAPH_REPORT.md',
                            resolution=resolution, min_cohesion=min_cohesion, enable_splitting=enable_splitting)
        print(f'✓ Exported all graph outputs to {output_dir}/', file=sys.stderr)
    else:
        print(f'Error: unknown format "{fmt}".', file=sys.stderr)
        sys.exit(1)


def cmd_graph_migrations(args: argparse.Namespace) -> None:
    from ..migration_graph import build_migration_graph, format_dot, format_html, format_timeline, format_json
    files = load_files(args.migrations_dir, args.json_input, use_cache=False)
    migration_graph = build_migration_graph(files)
    fmt = getattr(args, 'format', 'timeline')
    if fmt == 'dot':
        output = format_dot(migration_graph)
    elif fmt == 'html':
        output = format_html(migration_graph)
    elif fmt == 'timeline':
        output = format_timeline(migration_graph)
    elif fmt == 'json':
        output = format_json(migration_graph)
    else:
        print(f'Error: unsupported format: {fmt}', file=sys.stderr)
        sys.exit(1)
    write_output(output, args.out)
    print(f'  {len(migration_graph.nodes)} migrations', file=sys.stderr)
    print(f'  {len(migration_graph.edges)} dependencies', file=sys.stderr)

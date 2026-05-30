"""Graph visualization commands: graph and graph-migrations."""

import sys
from pathlib import Path

from ..domain.schema_state import SchemaStateBuilder
from ..reconstructor import reconstruct, reconstruct_at
from ..output.grapher import Grapher
from ._utils import load_files, write_output


def cmd_graph(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    at: str | None = None,
    out: str | None = None,
    format: str = "dot",
    title: str = "",
    output_dir: str | None = None,
    resolution: float = 1.0,
    min_cohesion: float = 0.1,
    no_split: bool = False,
) -> None:
    """Output a schema graph in DOT, Mermaid, Excalidraw, Draw.io, JSON, HTML, or report format."""
    files = load_files(migrations_dir, json_input)
    graph = (
        reconstruct_at(files, at, dialect=dialect)
        if at
        else reconstruct(files, dialect=dialect)
    )
    state = SchemaStateBuilder.from_graph(graph)
    fmt = (format or "dot").lower()
    title = title or f"Schema V{state.version}"

    if fmt in ("dot", "mermaid", "excalidraw", "drawio", "summary"):
        if fmt == "dot":
            output = Grapher.to_dot(state, title=title)
        elif fmt == "mermaid":
            output = Grapher.to_mermaid(state, title=title)
        elif fmt == "excalidraw":
            from ..output.excalidraw_exporter import to_excalidraw
            import json as _json
            output = _json.dumps(to_excalidraw(state, title=title), indent=2)
        elif fmt == "drawio":
            from ..output.drawio_exporter import to_drawio
            output = to_drawio(state, title=title)
        else:
            output = Grapher.to_summary(state)
        write_output(output, out)
        return

    from ..core import build_networkx_graph
    from ..output.graph_export import export_graph_json, export_graph_html, export_graph_report

    nx_graph = build_networkx_graph(graph, directed=True)
    out_dir = Path(output_dir or "sqlfy-out")
    out_dir.mkdir(parents=True, exist_ok=True)
    enable_splitting = not no_split

    export_kwargs = dict(resolution=resolution, min_cohesion=min_cohesion, enable_splitting=enable_splitting)

    if fmt == "json":
        p = out_dir / "graph.json"
        export_graph_json(nx_graph, output_path=p, **export_kwargs)
        print(f"✓ Exported NetworkX graph to {p}", file=sys.stderr)
    elif fmt == "html":
        p = out_dir / "graph.html"
        export_graph_html(nx_graph, output_path=p, **export_kwargs)
        print(f"✓ Exported interactive visualization to {p}", file=sys.stderr)
    elif fmt == "report":
        p = out_dir / "GRAPH_REPORT.md"
        export_graph_report(nx_graph, output_path=p, **export_kwargs)
        print(f"✓ Exported graph report to {p}", file=sys.stderr)
    elif fmt == "all":
        export_graph_json(nx_graph, output_path=out_dir / "graph.json", **export_kwargs)
        export_graph_html(nx_graph, output_path=out_dir / "graph.html", **export_kwargs)
        export_graph_report(nx_graph, output_path=out_dir / "GRAPH_REPORT.md", **export_kwargs)
        print(f"✓ Exported all graph outputs to {out_dir}/", file=sys.stderr)
    else:
        print(f'Error: unknown format "{fmt}".', file=sys.stderr)
        sys.exit(1)


def cmd_graph_migrations(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    out: str | None = None,
    format: str = "timeline",
) -> None:
    """Visualize migration timeline and dependency graph."""
    files = load_files(migrations_dir, json_input, use_cache=False)
    from ..migration_graph import build_migration_graph, format_dot, format_html, format_timeline, format_json

    migration_graph = build_migration_graph(files)
    fmt = (format or "timeline").lower()
    if fmt == "dot":
        output = format_dot(migration_graph)
    elif fmt == "html":
        output = format_html(migration_graph)
    elif fmt == "timeline":
        output = format_timeline(migration_graph)
    elif fmt == "json":
        output = format_json(migration_graph)
    else:
        print(f"Error: unsupported format: {fmt}", file=sys.stderr)
        sys.exit(1)
    write_output(output, out)
    print(f"  {len(migration_graph.nodes)} migrations", file=sys.stderr)
    print(f"  {len(migration_graph.edges)} dependencies", file=sys.stderr)

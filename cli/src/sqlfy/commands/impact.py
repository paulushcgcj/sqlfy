"""Impact analysis command."""

import sys

from ..reconstructor import reconstruct, reconstruct_at
from ._utils import load_files, write_output


def cmd_impact(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    at: str | None = None,
    object: str,
    depth: int = 5,
    direction: str = "out",
    format: str = "text",
    out: str | None = None,
) -> None:
    """Analyze transitive impact of changes to a schema object via BFS/DFS traversal."""
    from ..core import build_networkx_graph
    from ..analysis.impact import analyze_impact, format_impact_text, format_impact_json

    files = load_files(migrations_dir, json_input)
    graph_data = (
        reconstruct_at(files, at, dialect=dialect)
        if at
        else reconstruct(files, dialect=dialect)
    )
    nx_graph = build_networkx_graph(graph_data, directed=True)
    object_id = object.upper()
    result = analyze_impact(
        nx_graph,
        object_id,
        max_depth=depth,
        follow_direction=direction,
    )
    fmt = (format or "text").lower()
    write_output(format_impact_json(result) if fmt == "json" else format_impact_text(result, nx_graph), out)

    if result.total_count == 0:
        print(f"No affected objects found for {object_id}", file=sys.stderr)
    else:
        print(f"  {result.total_count} affected object(s)", file=sys.stderr)
        print(f"  {len(result.direct)} direct, {len(result.transitive)} transitive", file=sys.stderr)
        print(f"  Max depth: {result.max_depth}", file=sys.stderr)

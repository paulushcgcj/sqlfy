"""Impact analysis command."""

import sys
import argparse

from ..reconstructor import reconstruct, reconstruct_at
from ._utils import load_files, write_output


def cmd_impact(args: argparse.Namespace) -> None:
    """Analyze transitive impact of changes to a schema object via BFS/DFS traversal."""
    from ..core import build_networkx_graph
    from ..analysis.impact import analyze_impact, format_impact_text, format_impact_json

    files = load_files(args.migrations_dir, args.json_input)
    dialect = getattr(args, "dialect", "oracle")
    graph_data = (
        reconstruct_at(files, args.at, dialect=dialect)
        if getattr(args, "at", None)
        else reconstruct(files, dialect=dialect)
    )
    nx_graph = build_networkx_graph(graph_data, directed=True)
    object_id = args.object.upper()
    result = analyze_impact(
        nx_graph,
        object_id,
        max_depth=getattr(args, "depth", 5),
        follow_direction=getattr(args, "direction", "out"),
    )
    fmt = getattr(args, "format", "text")
    write_output(format_impact_json(result) if fmt == "json" else format_impact_text(result, nx_graph), args.out)

    if result.total_count == 0:
        print(f"No affected objects found for {object_id}", file=sys.stderr)
    else:
        print(f"  {result.total_count} affected object(s)", file=sys.stderr)
        print(f"  {len(result.direct)} direct, {len(result.transitive)} transitive", file=sys.stderr)
        print(f"  Max depth: {result.max_depth}", file=sys.stderr)

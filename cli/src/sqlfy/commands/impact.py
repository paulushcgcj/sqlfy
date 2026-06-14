"""Impact analysis command."""

from __future__ import annotations

import sys

from ..reconstructor import reconstruct, reconstruct_at
from ._git_diff import extract_tables_from_diff, get_diff_files
from ._utils import load_files, write_output


def cmd_impact(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    at: str | None = None,
    object: str | None = None,
    table: list[str] | None = None,
    from_diff: str | None = None,
    depth: int = 5,
    direction: str = "out",
    format: str = "text",
    out: str | None = None,
) -> None:
    """Analyze transitive impact of changes to a schema object via BFS/DFS traversal."""
    from ..core import build_networkx_graph
    from ..analysis.impact import (
        analyze_impact,
        format_impact_json,
        format_impact_text,
        merge_impact_results,
    )

    # ── Resolve tables to analyze ───────────────────────────────────────
    explicit_tables: list[str] = []
    if object:
        explicit_tables.append(object.upper())
    if table:
        explicit_tables.extend(t.upper() for t in table)

    diff_tables: list[str] = []
    diff_files: list[str] = []
    ref_display: str = ""

    if from_diff is not None:
        if not migrations_dir:
            print(
                "Error: --from-diff requires <migrations-dir>.",
                file=sys.stderr,
            )
            sys.exit(1)

        ref_display = "staged changes" if from_diff == "staged" else f"{from_diff}..HEAD"
        try:
            diff_files = get_diff_files(migrations_dir, ref=from_diff if from_diff != "staged" else None)
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        if not diff_files:
            print("No SQL files changed in diff.", file=sys.stderr)
            if not explicit_tables:
                return

        tables_map = extract_tables_from_diff(diff_files, dialect=dialect)
        for files_tables in tables_map.values():
            diff_tables.extend(sorted(files_tables))

        if not diff_tables and not explicit_tables:
            print("No tables found in changed SQL files.", file=sys.stderr)
            return

    # Fallback: original positional object
    if not diff_tables and not explicit_tables:
        print(
            "Error: you must specify an object (--table OBJECT_ID or positional) "
            "or use --from-diff.",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── Analyse impact for each table ───────────────────────────────────
    all_tables = list(dict.fromkeys(diff_tables + explicit_tables))

    files = load_files(migrations_dir, json_input)
    graph_data = (
        reconstruct_at(files, at, dialect=dialect)
        if at
        else reconstruct(files, dialect=dialect)
    )
    nx_graph = build_networkx_graph(graph_data, directed=True)

    results = [
        analyze_impact(
            nx_graph,
            tbl,
            max_depth=depth,
            follow_direction=direction,
        )
        for tbl in all_tables
    ]

    fmt = (format or "text").lower()

    if from_diff is not None:
        from ..analysis.impact import format_impact_from_diff_text

        merged = merge_impact_results(
            results,
            changed_tables=diff_tables,
            migration_files=list(dict.fromkeys(diff_files)),
        )
        if fmt == "json":
            from ..analysis.impact import format_impact_from_diff_json

            write_output(
                format_impact_from_diff_json(merged, ref_display=ref_display),
                out,
            )
        else:
            write_output(
                format_impact_from_diff_text(merged, nx_graph, ref_display=ref_display),
                out,
            )

        if merged.total_count == 0:
            print("No downstream tables affected.", file=sys.stderr)
        else:
            print(f"  {merged.total_count} affected object(s)", file=sys.stderr)
            print(f"  {len(merged.direct)} direct, {len(merged.transitive)} transitive", file=sys.stderr)
            print(f"  Max depth: {merged.max_depth}", file=sys.stderr)
    else:
        result = results[0] if len(results) == 1 else merge_impact_results(results)
        write_output(
            format_impact_json(result) if fmt == "json" else format_impact_text(result, nx_graph),
            out,
        )

        if result.total_count == 0:
            print(f"No affected objects found for {result.object_id}", file=sys.stderr)
        else:
            print(f"  {result.total_count} affected object(s)", file=sys.stderr)
            print(f"  {len(result.direct)} direct, {len(result.transitive)} transitive", file=sys.stderr)
            print(f"  Max depth: {result.max_depth}", file=sys.stderr)

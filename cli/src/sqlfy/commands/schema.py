"""Schema state, chunks, and export commands."""

import sys
import json

from ..domain.schema_state import SchemaStateBuilder
from ..reconstructor import reconstruct, reconstruct_at
from ..output.chunker import build_chunks
from ..output.exporter import Exporter
from ..analysis.insights import InsightsEngine
from ._utils import load_files, write_output, format_human_chunks, graph_to_dict, chunks_to_list, format_state_summary


def cmd_dump(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    at: str | None = None,
    format: str = "json",
    out: str | None = None,
) -> None:
    """Output the Schema State Dictionary as JSON, YAML, or human summary."""
    files = load_files(migrations_dir, json_input)
    graph = (
        reconstruct_at(files, version=at, dialect=dialect)
        if at
        else reconstruct(files, dialect=dialect)
    )
    state = SchemaStateBuilder.from_graph(graph)
    fmt = (format or "json").lower()
    if fmt == "yaml":
        output = state.to_yaml()
    elif fmt == "json":
        output = state.to_json()
    elif fmt == "summary":
        output = format_state_summary(state)
    else:
        print(f'Error: unknown format "{fmt}". Choose json, yaml, or summary.', file=sys.stderr)
        sys.exit(1)
    write_output(output, out)


def cmd_manifest(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    at: str | None = None,
    format: str = "json",
    out: str | None = None,
) -> None:
    """Output graph manifest with high-level metadata."""
    files = load_files(migrations_dir, json_input)
    graph = (
        reconstruct_at(files, version=at, dialect=dialect)
        if at
        else reconstruct(files, dialect=dialect)
    )
    state = SchemaStateBuilder.from_graph(graph)
    fmt = (format or "json").lower()
    if fmt == "text":
        import json as _json
        data = _json.loads(state.to_manifest())
        lines = [
            f"Schema Version  : {data.get('schemaVersion', '-')}",
            f"Dialect         : {data.get('dialect', '-')}",
            f"Generated At    : {data.get('generatedAt', '-')}",
            f"Fingerprint     : {data.get('fingerprint', '-')}",
            f"Tables          : {data.get('tableCount', 0)}",
            f"Columns         : {data.get('columnCount', 0)}",
            f"Sequences       : {data.get('sequenceCount', 0)}",
            f"Relationships   : {data.get('relationshipCount', 0)}",
            f"Indexes         : {data.get('indexCount', 0)}",
            f"Migrations      : {data.get('migrationCount', 0)}",
            f"Tables w/o PK   : {data.get('tablesWithoutPk', 0)}",
        ]
        output = "\n".join(lines)
    else:
        output = state.to_manifest()
    write_output(output, out)


def cmd_chunks(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    at: str | None = None,
    format: str = "json",
    out: str | None = None,
) -> None:
    """Output LLM vector chunks from the schema."""
    files = load_files(migrations_dir, json_input)
    graph = (
        reconstruct_at(files, at, dialect=dialect)
        if at
        else reconstruct(files, dialect=dialect)
    )
    chunks = build_chunks(graph)
    fmt = (format or "json").lower()
    if fmt == "json":
        output = json.dumps(chunks_to_list(chunks), indent=2, ensure_ascii=False)
    else:
        output = format_human_chunks(chunks)
    write_output(output, out)


def cmd_export(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    at: str | None = None,
    out: str | None = None,
    insights: bool = False,
    title: str = "",
) -> None:
    """Export schema as a self-contained HTML documentation file."""
    files = load_files(migrations_dir, json_input)
    graph = (
        reconstruct_at(files, at, dialect=dialect)
        if at
        else reconstruct(files, dialect=dialect)
    )
    state = SchemaStateBuilder.from_graph(graph)
    report = InsightsEngine.analyse(state) if insights else None
    title = title or f"Schema Documentation — V{state.version}"
    html = Exporter.to_html(state, report=report, title=title)
    out = out or "schema_docs.html"
    write_output(html, out)
    print(f"HTML documentation written to {out}", file=sys.stderr)
    print(f"  Tables   : {state.stats['table_count']}", file=sys.stderr)
    print(f"  Columns  : {state.stats['column_count']}", file=sys.stderr)
    print(f"  Size     : {len(html):,} chars", file=sys.stderr)


def legacy_main(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    all: bool = False,
    chunks: bool = False,
    as_json: bool = False,
    out: str | None = None,
) -> None:
    """Backward-compatible flag-based interface."""
    files = load_files(migrations_dir, json_input)
    if all:
        graph = reconstruct(files, dialect=dialect)
        graph_chunks = build_chunks(graph)
        output = json.dumps(
            {"graph": graph_to_dict(graph), "chunks": chunks_to_list(graph_chunks)},
            indent=2,
            ensure_ascii=False,
        )
    elif chunks:
        graph = reconstruct(files, dialect=dialect)
        graph_chunks = build_chunks(graph)
        output = (
            json.dumps(chunks_to_list(graph_chunks), indent=2, ensure_ascii=False)
            if as_json
            else format_human_chunks(graph_chunks)
        )
    else:
        from ._utils import format_human_graph
        graph = reconstruct(files, dialect=dialect)
        output = (
            json.dumps(graph_to_dict(graph), indent=2, ensure_ascii=False)
            if as_json
            else format_human_graph(graph)
        )
    write_output(output, out)

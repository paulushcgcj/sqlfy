"""Schema state, chunks, and export commands."""

import sys
import json
import argparse

from ..domain.schema_state import SchemaStateBuilder
from ..reconstructor import reconstruct, reconstruct_at
from ..output.chunker import build_chunks
from ..output.exporter import Exporter
from ..analysis.insights import InsightsEngine
from ._utils import load_files, write_output, format_human_chunks, graph_to_dict, chunks_to_list, format_state_summary


def cmd_dump(args: argparse.Namespace) -> None:
    """Output the Schema State Dictionary as JSON, YAML, or human summary."""
    files = load_files(args.migrations_dir, args.json_input)
    dialect = getattr(args, "dialect", "oracle")
    graph = (
        reconstruct_at(files, version=args.at, dialect=dialect)
        if args.at
        else reconstruct(files, dialect=dialect)
    )
    state = SchemaStateBuilder.from_graph(graph)
    fmt = (args.format or "json").lower()
    if fmt == "yaml":
        output = state.to_yaml()
    elif fmt == "json":
        output = state.to_json()
    elif fmt == "summary":
        output = format_state_summary(state)
    else:
        print(f'Error: unknown format "{fmt}". Choose json, yaml, or summary.', file=sys.stderr)
        sys.exit(1)
    write_output(output, args.out)


def cmd_manifest(args: argparse.Namespace) -> None:
    """Output graph manifest with high-level metadata."""
    files = load_files(args.migrations_dir, args.json_input)
    dialect = getattr(args, "dialect", "oracle")
    graph = (
        reconstruct_at(files, version=args.at, dialect=dialect)
        if getattr(args, "at", None)
        else reconstruct(files, dialect=dialect)
    )
    state = SchemaStateBuilder.from_graph(graph)
    write_output(json.dumps(state.to_manifest(), indent=2, ensure_ascii=False), args.out)


def cmd_chunks(args: argparse.Namespace) -> None:
    """Output LLM vector chunks from the schema."""
    files = load_files(args.migrations_dir, args.json_input)
    dialect = getattr(args, "dialect", "oracle")
    graph = (
        reconstruct_at(files, args.at, dialect=dialect)
        if args.at
        else reconstruct(files, dialect=dialect)
    )
    chunks = build_chunks(graph)
    fmt = (args.format or "json").lower()
    if fmt == "json":
        output = json.dumps(chunks_to_list(chunks), indent=2, ensure_ascii=False)
    else:
        output = format_human_chunks(chunks)
    write_output(output, args.out)


def cmd_export(args: argparse.Namespace) -> None:
    """Export schema as a self-contained HTML documentation file."""
    files = load_files(args.migrations_dir, args.json_input)
    dialect = getattr(args, "dialect", "oracle")
    graph = (
        reconstruct_at(files, args.at, dialect=dialect)
        if getattr(args, "at", None)
        else reconstruct(files, dialect=dialect)
    )
    state = SchemaStateBuilder.from_graph(graph)
    report = InsightsEngine.analyse(state) if getattr(args, "insights", False) else None
    title = getattr(args, "title", "") or f"Schema Documentation — V{state.version}"
    html = Exporter.to_html(state, report=report, title=title)
    out = args.out or "schema_docs.html"
    write_output(html, out)
    print(f"HTML documentation written to {out}", file=sys.stderr)
    print(f"  Tables   : {state.stats['table_count']}", file=sys.stderr)
    print(f"  Columns  : {state.stats['column_count']}", file=sys.stderr)
    print(f"  Size     : {len(html):,} chars", file=sys.stderr)


def legacy_main(args: argparse.Namespace) -> None:
    """Backward-compatible flag-based interface."""
    files = load_files(args.migrations_dir, getattr(args, "json_input", None))
    dialect = getattr(args, "dialect", "oracle")
    if getattr(args, "all", False):
        graph = reconstruct(files, dialect=dialect)
        chunks = build_chunks(graph)
        output = json.dumps(
            {"graph": graph_to_dict(graph), "chunks": chunks_to_list(chunks)},
            indent=2,
            ensure_ascii=False,
        )
    elif getattr(args, "chunks", False):
        graph = reconstruct(files, dialect=dialect)
        chunks = build_chunks(graph)
        output = (
            json.dumps(chunks_to_list(chunks), indent=2, ensure_ascii=False)
            if getattr(args, "json", False)
            else format_human_chunks(chunks)
        )
    else:
        from ._utils import format_human_graph
        graph = reconstruct(files, dialect=dialect)
        output = (
            json.dumps(graph_to_dict(graph), indent=2, ensure_ascii=False)
            if getattr(args, "json", False)
            else format_human_graph(graph)
        )
    write_output(output, getattr(args, "out", None))

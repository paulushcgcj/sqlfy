"""AI and query commands: ask, chat, query."""

import sys
import argparse

from ..domain.schema_state import SchemaStateBuilder
from ..reconstructor import reconstruct, reconstruct_at
from ..analysis.asker import Asker, ChatSession
from ..analysis.query import QueryEngine
from ._utils import load_files, write_output, parse_bool

_QUERY_TYPES = [
    "tables", "columns", "fk-path", "refs",
    "orphans", "islands", "cycles",
    "missing-pk", "missing-fk", "impact", "indexes",
]


def cmd_ask(args: argparse.Namespace) -> None:
    """Ask a single natural language question about the schema (RAG)."""
    files = load_files(args.migrations_dir, args.json_input)
    dialect = getattr(args, "dialect", "oracle")
    graph = (
        reconstruct_at(files, args.at, dialect=dialect)
        if getattr(args, "at", None)
        else reconstruct(files, dialect=dialect)
    )
    try:
        asker = Asker(
            graph,
            api_key=getattr(args, "api_key", None),
            use_embeddings=getattr(args, "embed", False),
            k=getattr(args, "k", 6),
            use_cache=not getattr(args, "no_cache", False),
            files=files,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    question = " ".join(args.question) if isinstance(args.question, list) else args.question
    fmt = getattr(args, "format", "text")

    if fmt == "json":
        result = asker.ask(question)
        write_output(result.to_json(), args.out)
    else:
        result = asker.ask_print(question, show_sources=not getattr(args, "no_sources", False), stream=True)
        if args.out:
            write_output(result.to_json(), args.out)


def cmd_chat(args: argparse.Namespace) -> None:
    """Start an interactive multi-turn chat session about the schema."""
    files = load_files(args.migrations_dir, args.json_input)
    dialect = getattr(args, "dialect", "oracle")
    graph = (
        reconstruct_at(files, args.at, dialect=dialect)
        if getattr(args, "at", None)
        else reconstruct(files, dialect=dialect)
    )
    try:
        asker = Asker(
            graph,
            api_key=getattr(args, "api_key", None),
            use_embeddings=getattr(args, "embed", False),
            k=getattr(args, "k", 6),
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    session = ChatSession(asker)
    n_tables = len(graph.tables)
    n_edges = len(graph.edges)
    ver = graph.mig_hist[-1].version if graph.mig_hist else "?"
    print(f"\n\033[1msqlfy chat\033[0m — schema V{ver} ({n_tables} tables, {n_edges} FK edges)")
    print('\033[2mType your question. "reset" clears history. "exit" quits.\033[0m\n')

    while True:
        try:
            question = input("\033[1m?\033[0m  ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break
        if not question:
            continue
        if question.lower() in ("exit", "quit", "q", "bye"):
            print("Bye!")
            break
        if question.lower() == "reset":
            session.reset()
            print("\033[2mConversation history cleared.\033[0m\n")
            continue
        print()
        try:
            session.ask(question, stream=True)
        except Exception as e:
            print(f"\n\033[31mError: {e}\033[0m\n")
        print()


def cmd_query(args: argparse.Namespace) -> None:
    """Run a deterministic graph-traversal query — no LLM, no API calls."""
    files = load_files(args.migrations_dir, args.json_input)
    dialect = getattr(args, "dialect", "oracle")
    graph = (
        reconstruct_at(files, args.at, dialect=dialect)
        if getattr(args, "at", None)
        else reconstruct(files, dialect=dialect)
    )
    state = SchemaStateBuilder.from_graph(graph)
    engine = QueryEngine(state)
    qt = args.query_type
    fmt = getattr(args, "format", "text")

    if qt == "tables":
        result = engine.tables(
            pattern=getattr(args, "pattern", None),
            schema=getattr(args, "schema", None),
            has_pk=parse_bool(getattr(args, "has_pk", None)),
            is_orphan=parse_bool(getattr(args, "is_orphan", None)),
            min_cols=getattr(args, "min_cols", None),
            max_cols=getattr(args, "max_cols", None),
            created_in=getattr(args, "created_in", None),
        )
    elif qt == "columns":
        result = engine.columns(
            table=getattr(args, "table", None),
            pattern=getattr(args, "pattern", None),
            type_like=getattr(args, "type_like", None),
            is_pk=parse_bool(getattr(args, "is_pk", None)),
            is_fk=parse_bool(getattr(args, "is_fk", None)),
            is_unique=parse_bool(getattr(args, "is_unique", None)),
            nullable=parse_bool(getattr(args, "nullable", None)),
            has_default=parse_bool(getattr(args, "has_default", None)),
        )
    elif qt == "fk-path":
        if not args.from_table or not args.to_table:
            print("Error: fk-path requires --from TABLE and --to TABLE", file=sys.stderr)
            sys.exit(1)
        result = engine.fk_path(args.from_table, args.to_table)
    elif qt == "refs":
        if not args.table:
            print("Error: refs requires --table TABLE", file=sys.stderr)
            sys.exit(1)
        result = engine.refs(args.table, direction=getattr(args, "direction", "both"))
    elif qt == "orphans":
        result = engine.orphans()
    elif qt == "islands":
        result = engine.islands()
    elif qt == "cycles":
        result = engine.cycles()
    elif qt == "missing-pk":
        result = engine.missing_pk()
    elif qt == "missing-fk":
        result = engine.missing_fk()
    elif qt == "impact":
        if not args.table:
            print("Error: impact requires --table TABLE", file=sys.stderr)
            sys.exit(1)
        result = engine.impact(args.table)
    elif qt == "indexes":
        result = engine.indexes(
            table=getattr(args, "table", None),
            unique_only=getattr(args, "unique_only", False),
        )
    else:
        print(f"Unknown query type: {qt}", file=sys.stderr)
        sys.exit(1)

    if fmt == "json":
        output = result.to_json()
    elif fmt == "csv":
        output = result.to_csv()
    else:
        output = result.to_text()

    write_output(output, args.out)
    print(f"  {len(result)} row(s)", file=sys.stderr)

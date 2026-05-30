"""AI and query commands: ask, chat, query."""

import sys

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


def cmd_ask(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    at: str | None = None,
    api_key: str | None = None,
    embed: bool = False,
    k: int = 6,
    no_cache: bool = False,
    question,
    format: str = "text",
    out: str | None = None,
    no_sources: bool = False,
) -> None:
    """Ask a single natural language question about the schema (RAG)."""
    files = load_files(migrations_dir, json_input)
    graph = (
        reconstruct_at(files, at, dialect=dialect)
        if at
        else reconstruct(files, dialect=dialect)
    )
    try:
        asker = Asker(
            graph,
            api_key=api_key,
            use_embeddings=embed,
            k=k,
            use_cache=not no_cache,
            files=files,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    question_str = " ".join(question) if isinstance(question, list) else question
    fmt = (format or "text").lower()

    if fmt == "json":
        result = asker.ask(question_str)
        write_output(result.to_json(), out)
    else:
        result = asker.ask_print(question_str, show_sources=not no_sources, stream=True)
        if out:
            write_output(result.to_json(), out)


def cmd_chat(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    at: str | None = None,
    api_key: str | None = None,
    embed: bool = False,
    k: int = 6,
) -> None:
    """Start an interactive multi-turn chat session about the schema."""
    files = load_files(migrations_dir, json_input)
    graph = (
        reconstruct_at(files, at, dialect=dialect)
        if at
        else reconstruct(files, dialect=dialect)
    )
    try:
        asker = Asker(
            graph,
            api_key=api_key,
            use_embeddings=embed,
            k=k,
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
            q = input("\033[1m?\033[0m  ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break
        if not q:
            continue
        if q.lower() in ("exit", "quit", "q", "bye"):
            print("Bye!")
            break
        if q.lower() == "reset":
            session.reset()
            print("\033[2mConversation history cleared.\033[0m\n")
            continue
        print()
        try:
            session.ask(q, stream=True)
        except Exception as e:
            print(f"\n\033[31mError: {e}\033[0m\n")
        print()


def cmd_query(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    at: str | None = None,
    query_type: str,
    format: str = "text",
    out: str | None = None,
    pattern: str | None = None,
    schema: str | None = None,
    table: str | None = None,
    type_like: str | None = None,
    from_table: str | None = None,
    to_table: str | None = None,
    direction: str = "both",
    has_pk: str | None = None,
    is_orphan: str | None = None,
    is_pk: str | None = None,
    is_fk: str | None = None,
    is_unique: str | None = None,
    nullable: str | None = None,
    has_default: str | None = None,
    min_cols: int | None = None,
    max_cols: int | None = None,
    created_in: str | None = None,
    unique_only: bool = False,
) -> None:
    """Run a deterministic graph-traversal query — no LLM, no API calls."""
    files = load_files(migrations_dir, json_input)
    graph = (
        reconstruct_at(files, at, dialect=dialect)
        if at
        else reconstruct(files, dialect=dialect)
    )
    state = SchemaStateBuilder.from_graph(graph)
    engine = QueryEngine(state)
    qt = query_type
    fmt = (format or "text").lower()

    if qt == "tables":
        result = engine.tables(
            pattern=pattern,
            schema=schema,
            has_pk=parse_bool(has_pk),
            is_orphan=parse_bool(is_orphan),
            min_cols=min_cols,
            max_cols=max_cols,
            created_in=created_in,
        )
    elif qt == "columns":
        result = engine.columns(
            table=table,
            pattern=pattern,
            type_like=type_like,
            is_pk=parse_bool(is_pk),
            is_fk=parse_bool(is_fk),
            is_unique=parse_bool(is_unique),
            nullable=parse_bool(nullable),
            has_default=parse_bool(has_default),
        )
    elif qt == "fk-path":
        if not from_table or not to_table:
            print("Error: fk-path requires --from TABLE and --to TABLE", file=sys.stderr)
            sys.exit(1)
        result = engine.fk_path(from_table, to_table)
    elif qt == "refs":
        if not table:
            print("Error: refs requires --table TABLE", file=sys.stderr)
            sys.exit(1)
        result = engine.refs(table, direction=direction)
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
        if not table:
            print("Error: impact requires --table TABLE", file=sys.stderr)
            sys.exit(1)
        result = engine.impact(table)
    elif qt == "indexes":
        result = engine.indexes(table=table, unique_only=unique_only)
    else:
        print(f"Unknown query type: {qt}", file=sys.stderr)
        sys.exit(1)

    if fmt == "json":
        output = result.to_json()
    elif fmt == "csv":
        output = result.to_csv()
    else:
        output = result.to_text()

    write_output(output, out)
    print(f"  {len(result)} row(s)", file=sys.stderr)

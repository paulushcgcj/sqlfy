"""
sqlfy.cli.intelligence
======================
Typer app for AI / RAG commands: ask, chat, query.
"""
from __future__ import annotations

import typer

app = typer.Typer(help="Natural language schema intelligence commands.", no_args_is_help=True)


@app.command("ask")
def cmd_ask(
    migrations_dir: str | None = typer.Argument(None),
    question: list[str] = typer.Argument(..., help="Natural language question"),
    json_input: str | None = typer.Option(None, "--json-input", metavar="FILE"),
    dialect: str = typer.Option("oracle", "--dialect"),
    at: str | None = typer.Option(None, "--at"),
    out: str | None = typer.Option(None, "--out"),
    embed: bool = typer.Option(False, "--embed"),
    api_key: str | None = typer.Option(None, "--api-key"),
    k: int = typer.Option(6, "-k"),
    fmt: str = typer.Option("text", "--format"),
) -> None:
    """Ask a natural language question about the schema (RAG)."""
    from ..commands.ai import cmd_ask as _cmd
    _cmd(migrations_dir=migrations_dir, json_input=json_input, dialect=dialect,
         at=at, out=out, embed=embed, api_key=api_key, k=k,
         question=question, format=fmt)


@app.command("chat")
def cmd_chat(
    migrations_dir: str | None = typer.Argument(None),
    json_input: str | None = typer.Option(None, "--json-input", metavar="FILE"),
    dialect: str = typer.Option("oracle", "--dialect"),
    at: str | None = typer.Option(None, "--at"),
    out: str | None = typer.Option(None, "--out"),
    embed: bool = typer.Option(False, "--embed"),
    api_key: str | None = typer.Option(None, "--api-key"),
    k: int = typer.Option(6, "-k"),
) -> None:
    """Interactive multi-turn schema chat session."""
    from ..commands.ai import cmd_chat as _cmd
    _cmd(migrations_dir=migrations_dir, json_input=json_input, dialect=dialect,
         at=at, embed=embed, api_key=api_key, k=k)


@app.command("query")
def cmd_query(
    migrations_dir: str | None = typer.Argument(None),
    query_type: str = typer.Argument(..., help="Query type (tables/columns/fk/orphans/no-pk/all-types)"),
    json_input: str | None = typer.Option(None, "--json-input", metavar="FILE"),
    dialect: str = typer.Option("oracle", "--dialect"),
    at: str | None = typer.Option(None, "--at"),
    out: str | None = typer.Option(None, "--out"),
    fmt: str = typer.Option("text", "--format"),
) -> None:
    """Run a structured schema query."""
    from ..commands.ai import cmd_query as _cmd
    _cmd(migrations_dir=migrations_dir, json_input=json_input, dialect=dialect,
         at=at, out=out, query_type=query_type, format=fmt)

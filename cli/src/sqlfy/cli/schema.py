"""
sqlfy.cli.schema
================
Typer app for schema-related commands: dump, manifest, chunks.
"""

from __future__ import annotations

import typer

app = typer.Typer(help="Schema state and extraction commands.", no_args_is_help=True)

_DIALECT_HELP = "SQL dialect: oracle, postgres, mysql, sqlite (default: oracle)"
_FORMAT_HELP = "Output format: json, yaml, summary"


@app.command("dump")
def cmd_dump(
    migrations_dir: str | None = typer.Argument(None, help="Path to migrations directory"),
    json_input: str | None = typer.Option(None, "--json-input", metavar="FILE"),
    dialect: str = typer.Option("oracle", "--dialect", help=_DIALECT_HELP),
    at: str | None = typer.Option(None, "--at", metavar="VERSION"),
    out: str | None = typer.Option(None, "--out", metavar="FILE"),
    fmt: str = typer.Option("json", "--format", help=_FORMAT_HELP),
) -> None:
    """Output the Schema State Dictionary."""
    from ..commands.schema import cmd_dump as _cmd
    _cmd(migrations_dir=migrations_dir, json_input=json_input, dialect=dialect,
         at=at, out=out, format=fmt)


@app.command("manifest")
def cmd_manifest(
    migrations_dir: str | None = typer.Argument(None),
    json_input: str | None = typer.Option(None, "--json-input", metavar="FILE"),
    dialect: str = typer.Option("oracle", "--dialect", help=_DIALECT_HELP),
    at: str | None = typer.Option(None, "--at", metavar="VERSION"),
    out: str | None = typer.Option(None, "--out", metavar="FILE"),
) -> None:
    """Output graph manifest/metadata summary."""
    from ..commands.schema import cmd_manifest as _cmd
    _cmd(migrations_dir=migrations_dir, json_input=json_input, dialect=dialect,
         at=at, out=out)


@app.command("chunks")
def cmd_chunks(
    migrations_dir: str | None = typer.Argument(None),
    json_input: str | None = typer.Option(None, "--json-input", metavar="FILE"),
    dialect: str = typer.Option("oracle", "--dialect", help=_DIALECT_HELP),
    at: str | None = typer.Option(None, "--at", metavar="VERSION"),
    out: str | None = typer.Option(None, "--out", metavar="FILE"),
) -> None:
    """Output vector chunks for RAG/embedding use."""
    from ..commands.schema import cmd_chunks as _cmd
    _cmd(migrations_dir=migrations_dir, json_input=json_input, dialect=dialect,
         at=at, out=out)

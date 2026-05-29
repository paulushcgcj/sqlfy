"""
sqlfy.cli.schema
================
Typer app for schema-related commands: dump, manifest, chunks.
"""

from __future__ import annotations

from typing import Optional
import typer

app = typer.Typer(help="Schema state and extraction commands.", no_args_is_help=True)

_DIALECT_HELP = "SQL dialect: oracle, postgres, mysql, sqlite (default: oracle)"
_FORMAT_HELP = "Output format: json, yaml, summary"


def _load(
    migrations_dir: Optional[str],
    json_input: Optional[str],
    dialect: str,
    at: Optional[str],
):
    """Common: load files, reconstruct schema, optionally slice at version."""
    from ..migrations.loader import load_files
    from ..reconstructor import reconstruct

    files = load_files(migrations_dir, json_input)
    graph = reconstruct(files, dialect=dialect)

    if at:
        from ..domain.schema_state import SchemaStateBuilder
        state = SchemaStateBuilder.from_graph(graph, at_version=at)
        return state, graph
    return graph, graph


@app.command("dump")
def cmd_dump(
    migrations_dir: Optional[str] = typer.Argument(None, help="Path to migrations directory"),
    json_input: Optional[str] = typer.Option(None, "--json-input", metavar="FILE"),
    dialect: str = typer.Option("oracle", "--dialect", help=_DIALECT_HELP),
    at: Optional[str] = typer.Option(None, "--at", metavar="VERSION"),
    out: Optional[str] = typer.Option(None, "--out", metavar="FILE"),
    fmt: str = typer.Option("json", "--format", help=_FORMAT_HELP),
) -> None:
    """Output the Schema State Dictionary."""
    import argparse
    from ..commands.schema import cmd_dump as _cmd

    ns = argparse.Namespace(
        migrations_dir=migrations_dir,
        json_input=json_input,
        dialect=dialect,
        at=at,
        out=out,
        format=fmt,
    )
    _cmd(ns)


@app.command("manifest")
def cmd_manifest(
    migrations_dir: Optional[str] = typer.Argument(None),
    json_input: Optional[str] = typer.Option(None, "--json-input", metavar="FILE"),
    dialect: str = typer.Option("oracle", "--dialect", help=_DIALECT_HELP),
    at: Optional[str] = typer.Option(None, "--at", metavar="VERSION"),
    out: Optional[str] = typer.Option(None, "--out", metavar="FILE"),
) -> None:
    """Output graph manifest/metadata summary."""
    import argparse
    from ..commands.schema import cmd_manifest as _cmd

    ns = argparse.Namespace(
        migrations_dir=migrations_dir,
        json_input=json_input,
        dialect=dialect,
        at=at,
        out=out,
    )
    _cmd(ns)


@app.command("chunks")
def cmd_chunks(
    migrations_dir: Optional[str] = typer.Argument(None),
    json_input: Optional[str] = typer.Option(None, "--json-input", metavar="FILE"),
    dialect: str = typer.Option("oracle", "--dialect", help=_DIALECT_HELP),
    at: Optional[str] = typer.Option(None, "--at", metavar="VERSION"),
    out: Optional[str] = typer.Option(None, "--out", metavar="FILE"),
) -> None:
    """Output vector chunks for RAG/embedding use."""
    import argparse
    from ..commands.schema import cmd_chunks as _cmd

    ns = argparse.Namespace(
        migrations_dir=migrations_dir,
        json_input=json_input,
        dialect=dialect,
        at=at,
        out=out,
    )
    _cmd(ns)

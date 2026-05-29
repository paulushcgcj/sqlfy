"""
sqlfy.cli.graph
===============
Typer app for graph commands: show, build, migrations.
"""

from __future__ import annotations

from typing import Optional
import typer

app = typer.Typer(help="Graph construction and visualization commands.", no_args_is_help=True)

_DIALECT_HELP = "SQL dialect: oracle, postgres, mysql, sqlite"


def _ns(**kwargs):
    import argparse
    return argparse.Namespace(**kwargs)


@app.command("show")
def cmd_graph(
    migrations_dir: Optional[str] = typer.Argument(None),
    json_input: Optional[str] = typer.Option(None, "--json-input", metavar="FILE"),
    dialect: str = typer.Option("oracle", "--dialect", help=_DIALECT_HELP),
    at: Optional[str] = typer.Option(None, "--at"),
    out: Optional[str] = typer.Option(None, "--out", metavar="FILE"),
    fmt: str = typer.Option("human", "--format"),
) -> None:
    """Display the schema graph."""
    from ..commands.graph import cmd_graph as _cmd
    _cmd(_ns(migrations_dir=migrations_dir, json_input=json_input, dialect=dialect,
             at=at, out=out, format=fmt))


@app.command("build")
def cmd_build_graph(
    migrations_dir: Optional[str] = typer.Argument(None),
    json_input: Optional[str] = typer.Option(None, "--json-input", metavar="FILE"),
    dialect: str = typer.Option("oracle", "--dialect", help=_DIALECT_HELP),
    out: Optional[str] = typer.Option(None, "--out", metavar="FILE"),
    fmt: str = typer.Option("gexf", "--format"),
    resolution: float = typer.Option(1.0, "--resolution"),
    min_cohesion: float = typer.Option(0.1, "--min-cohesion"),
    directed: bool = typer.Option(False, "--directed"),
) -> None:
    """Build and export NetworkX graph with community detection."""
    from ..commands.build_graph import cmd_build_graph as _cmd
    _cmd(_ns(migrations_dir=migrations_dir, json_input=json_input, dialect=dialect,
             out=out, format=fmt, resolution=resolution, min_cohesion=min_cohesion,
             directed=directed))


@app.command("migrations")
def cmd_graph_migrations(
    migrations_dir: Optional[str] = typer.Argument(None),
    json_input: Optional[str] = typer.Option(None, "--json-input", metavar="FILE"),
    dialect: str = typer.Option("oracle", "--dialect", help=_DIALECT_HELP),
    out: Optional[str] = typer.Option(None, "--out", metavar="FILE"),
    fmt: str = typer.Option("timeline", "--format"),
) -> None:
    """Build migration dependency/timeline graph."""
    from ..commands.graph import cmd_graph_migrations as _cmd
    _cmd(_ns(migrations_dir=migrations_dir, json_input=json_input, dialect=dialect,
             out=out, format=fmt))

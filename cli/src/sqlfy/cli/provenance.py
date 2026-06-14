"""
sqlfy.cli.provenance
====================
Typer app for provenance and impact commands: provenance, impact.
"""
from __future__ import annotations
from typing import Optional
import typer

app = typer.Typer(help="Provenance and impact analysis commands.", no_args_is_help=True)


@app.command("provenance")
def cmd_provenance(
    migrations_dir: str = typer.Argument(..., help="Path to migrations directory"),
    fmt: str = typer.Option("text", "--format"),
    out: Optional[str] = typer.Option(None, "--out"),
    record: bool = typer.Option(False, "--record"),
) -> None:
    """Collect git provenance for migrations (author, commit, branches, PR)."""
    from ..commands.provenance import cmd_provenance as _cmd
    _cmd(migrations_dir=migrations_dir, format=fmt, out=out, record=record)


@app.command("impact")
def cmd_impact(
    migrations_dir: Optional[str] = typer.Argument(None,
        help="Path to migrations directory"),
    obj: Optional[str] = typer.Argument(None, metavar="OBJECT_ID",
        help="Schema object to analyze (e.g. APP.USERS). Optional when --from-diff is used."),
    json_input: Optional[str] = typer.Option(None, "--json-input"),
    dialect: str = typer.Option("oracle", "--dialect"),
    at: Optional[str] = typer.Option(None, "--at"),
    out: Optional[str] = typer.Option(None, "--out"),
    fmt: str = typer.Option("text", "--format"),
    depth: int = typer.Option(5, "--depth"),
    direction: str = typer.Option("out", "--direction"),
    from_diff: Optional[str] = typer.Option(None, "--from-diff",
        help="Analyze tables from changes in a git diff. "
             "Use 'staged' for staged-only changes."),
    table: Optional[list[str]] = typer.Option(None, "--table",
        help="Additional table to analyze (repeatable)."),
) -> None:
    """Analyze impact of schema object changes."""
    from ..commands.impact import cmd_impact as _cmd
    _cmd(migrations_dir=migrations_dir, json_input=json_input, dialect=dialect,
         at=at, out=out, object=obj, table=table, from_diff=from_diff,
         format=fmt, depth=depth, direction=direction)

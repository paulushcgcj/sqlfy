"""
sqlfy.cli.evolution
===================
Typer app for schema evolution commands: diff, diff-versions,
rollback-analysis, simulate, drift.
"""
from __future__ import annotations
from typing import Optional
import typer

app = typer.Typer(help="Schema evolution and change-analysis commands.", no_args_is_help=True)

def _ns(**kw):
    import argparse; return argparse.Namespace(**kw)

@app.command("diff")
def cmd_diff(
    state_a: str = typer.Argument(..., help="First schema state JSON or migrations dir"),
    state_b: str = typer.Argument(..., help="Second schema state JSON or migrations dir"),
    fmt: str = typer.Option("text", "--format", help="Output format: json | text"),
    out: Optional[str] = typer.Option(None, "--out", metavar="FILE"),
) -> None:
    """Compare two schema state dictionaries or migration directories."""
    from ..commands.evolution import cmd_diff as _cmd
    _cmd(_ns(state_a=state_a, state_b=state_b, format=fmt, out=out))

@app.command("diff-versions")
def cmd_diff_versions(
    migrations_dir: Optional[str] = typer.Argument(None),
    json_input: Optional[str] = typer.Option(None, "--json-input", metavar="FILE"),
    dialect: str = typer.Option("oracle", "--dialect"),
    from_version: Optional[str] = typer.Option(None, "--from"),
    to_version: Optional[str] = typer.Option(None, "--to"),
    fmt: str = typer.Option("json", "--format"),
    out: Optional[str] = typer.Option(None, "--out"),
) -> None:
    """Compare two version snapshots of the same migration set."""
    from ..commands.evolution import cmd_diff_versions as _cmd
    _cmd(_ns(migrations_dir=migrations_dir, json_input=json_input, dialect=dialect,
             from_version=from_version, to_version=to_version, format=fmt, out=out))

@app.command("rollback-analysis")
def cmd_rollback_analysis(
    migrations_dir: Optional[str] = typer.Argument(None),
    json_input: Optional[str] = typer.Option(None, "--json-input", metavar="FILE"),
    dialect: str = typer.Option("oracle", "--dialect"),
    at: Optional[str] = typer.Option(None, "--at"),
    out: Optional[str] = typer.Option(None, "--out"),
    fmt: str = typer.Option("text", "--format"),
    generate: bool = typer.Option(False, "--generate"),
) -> None:
    """Analyze migration rollback feasibility."""
    from ..commands.evolution import cmd_rollback_analysis as _cmd
    _cmd(_ns(migrations_dir=migrations_dir, json_input=json_input, dialect=dialect,
             at=at, out=out, format=fmt, generate=generate))

@app.command("simulate")
def cmd_simulate(
    migrations_dir: Optional[str] = typer.Argument(None),
    json_input: Optional[str] = typer.Option(None, "--json-input", metavar="FILE"),
    dialect: str = typer.Option("oracle", "--dialect"),
    at: Optional[str] = typer.Option(None, "--at"),
    out: Optional[str] = typer.Option(None, "--out"),
    sql: Optional[str] = typer.Option(None, "--sql"),
    file: Optional[str] = typer.Option(None, "--file"),
    fmt: str = typer.Option("text", "--format"),
    diff: bool = typer.Option(False, "--diff"),
) -> None:
    """Simulate applying DDL to the current schema without persisting."""
    from ..commands.evolution import cmd_simulate as _cmd
    _cmd(_ns(migrations_dir=migrations_dir, json_input=json_input, dialect=dialect,
             at=at, out=out, sql=sql, file=file, format=fmt, diff=diff))

@app.command("drift")
def cmd_drift(
    base_migrations: str = typer.Argument(...),
    target_migrations: str = typer.Argument(...),
    dialect: str = typer.Option("oracle", "--dialect"),
    fmt: str = typer.Option("text", "--format"),
    out: Optional[str] = typer.Option(None, "--out"),
    generate_migration: bool = typer.Option(False, "--generate-migration"),
    next_version: Optional[str] = typer.Option(None, "--next-version"),
    description: str = typer.Option("catch_up_drift", "--description"),
) -> None:
    """Detect schema drift between two migration folders."""
    from ..commands.evolution import cmd_drift as _cmd
    _cmd(_ns(base_migrations=base_migrations, target_migrations=target_migrations,
             dialect=dialect, format=fmt, out=out, generate_migration=generate_migration,
             next_version=next_version, description=description))

"""
sqlfy.cli.analysis
==================
Typer app for analysis commands: insights, health, integrity, lint, domains,
stability, validate, deps, lineage, drift, classify, safety, cost, naming.
"""

from __future__ import annotations

from typing import Optional
import typer

app = typer.Typer(help="Schema analysis and quality commands.", no_args_is_help=True)

_DIALECT_HELP = "SQL dialect: oracle, postgres, mysql, sqlite"


def _ns(**kwargs):
    import argparse
    return argparse.Namespace(**kwargs)


def _shared_opts(
    migrations_dir: Optional[str],
    json_input: Optional[str],
    dialect: str,
    at: Optional[str],
    out: Optional[str],
) -> dict:
    return dict(migrations_dir=migrations_dir, json_input=json_input,
                dialect=dialect, at=at, out=out)


@app.command("insights")
def cmd_insights(
    migrations_dir: Optional[str] = typer.Argument(None),
    json_input: Optional[str] = typer.Option(None, "--json-input", metavar="FILE"),
    dialect: str = typer.Option("oracle", "--dialect"),
    at: Optional[str] = typer.Option(None, "--at"),
    out: Optional[str] = typer.Option(None, "--out"),
) -> None:
    """Run schema analysis and display insights."""
    from ..commands.analysis import cmd_insights as _cmd
    _cmd(_ns(**_shared_opts(migrations_dir, json_input, dialect, at, out)))


@app.command("health")
def cmd_health(
    migrations_dir: Optional[str] = typer.Argument(None),
    json_input: Optional[str] = typer.Option(None, "--json-input", metavar="FILE"),
    dialect: str = typer.Option("oracle", "--dialect"),
    at: Optional[str] = typer.Option(None, "--at"),
    out: Optional[str] = typer.Option(None, "--out"),
) -> None:
    """Schema health score and issue breakdown."""
    from ..commands.analysis import cmd_health as _cmd
    _cmd(_ns(**_shared_opts(migrations_dir, json_input, dialect, at, out)))


@app.command("integrity")
def cmd_integrity(
    migrations_dir: Optional[str] = typer.Argument(None),
    json_input: Optional[str] = typer.Option(None, "--json-input", metavar="FILE"),
    dialect: str = typer.Option("oracle", "--dialect"),
    at: Optional[str] = typer.Option(None, "--at"),
    out: Optional[str] = typer.Option(None, "--out"),
) -> None:
    """Check referential integrity across the schema."""
    from ..commands.analysis import cmd_integrity as _cmd
    _cmd(_ns(**_shared_opts(migrations_dir, json_input, dialect, at, out)))


@app.command("lint")
def cmd_lint(
    migrations_dir: Optional[str] = typer.Argument(None),
    json_input: Optional[str] = typer.Option(None, "--json-input", metavar="FILE"),
    dialect: str = typer.Option("oracle", "--dialect"),
    at: Optional[str] = typer.Option(None, "--at"),
    out: Optional[str] = typer.Option(None, "--out"),
) -> None:
    """Lint schema for anti-patterns and naming issues."""
    from ..commands.analysis import cmd_lint as _cmd
    _cmd(_ns(**_shared_opts(migrations_dir, json_input, dialect, at, out)))


@app.command("domains")
def cmd_domains(
    migrations_dir: Optional[str] = typer.Argument(None),
    json_input: Optional[str] = typer.Option(None, "--json-input", metavar="FILE"),
    dialect: str = typer.Option("oracle", "--dialect"),
    at: Optional[str] = typer.Option(None, "--at"),
    out: Optional[str] = typer.Option(None, "--out"),
) -> None:
    """Detect bounded domains/modules via community detection."""
    from ..commands.analysis import cmd_domains as _cmd
    _cmd(_ns(**_shared_opts(migrations_dir, json_input, dialect, at, out)))

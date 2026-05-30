"""
sqlfy.cli.devtools
==================
Typer app for developer tool commands: lint, validate, naming, deps,
lineage, classify, safety, domains, stability, cost, cache.
"""
from __future__ import annotations
from typing import Optional
import typer

app = typer.Typer(help="Developer tooling and schema quality commands.", no_args_is_help=True)


@app.command("lint")
def cmd_lint(
    path: str = typer.Argument(..., help="SQL file or directory to lint"),
    fmt: str = typer.Option("text", "--format"),
    out: Optional[str] = typer.Option(None, "--out"),
    min_score: Optional[int] = typer.Option(None, "--min-score"),
) -> None:
    """Lint migration SQL files for quality and style."""
    from ..commands.devtools import cmd_lint as _cmd
    _cmd(path=path, format=fmt, out=out, min_score=min_score or 0)


@app.command("validate")
def cmd_validate(
    migrations_dir: str = typer.Argument(...),
    fmt: str = typer.Option("text", "--format"),
    out: Optional[str] = typer.Option(None, "--out"),
    fix_numbering: bool = typer.Option(False, "--fix-numbering"),
) -> None:
    """Validate migration ordering and detect issues."""
    from ..commands.devtools import cmd_validate as _cmd
    _cmd(migrations_dir=migrations_dir, format=fmt, out=out, fix_numbering=fix_numbering)


@app.command("naming")
def cmd_naming(
    migrations_dir: str = typer.Argument(...),
    fmt: str = typer.Option("text", "--format"),
    out: Optional[str] = typer.Option(None, "--out"),
    pattern: Optional[str] = typer.Option(None, "--pattern"),
) -> None:
    """Enforce migration naming conventions."""
    from ..commands.devtools import cmd_naming as _cmd
    kw: dict = dict(migrations_dir=migrations_dir, format=fmt, out=out)
    if pattern is not None:
        kw["pattern"] = pattern
    _cmd(**kw)


@app.command("deps")
def cmd_deps(
    migrations_dir: str = typer.Argument(...),
    fmt: str = typer.Option("text", "--format"),
    out: Optional[str] = typer.Option(None, "--out"),
    critical_path: bool = typer.Option(False, "--critical-path"),
) -> None:
    """Analyze migration dependencies and detect issues."""
    from ..commands.devtools import cmd_deps as _cmd
    _cmd(migrations_dir=migrations_dir, format=fmt, out=out, critical_path=critical_path)


@app.command("lineage")
def cmd_lineage(
    migrations_dir: Optional[str] = typer.Argument(None),
    column: Optional[str] = typer.Argument(None, help="TABLE.COLUMN identifier"),
    json_input: Optional[str] = typer.Option(None, "--json-input"),
    dialect: str = typer.Option("oracle", "--dialect"),
    at: Optional[str] = typer.Option(None, "--at"),
    out: Optional[str] = typer.Option(None, "--out"),
    fmt: str = typer.Option("text", "--format"),
    downstream: bool = typer.Option(True, "--downstream"),
    upstream: bool = typer.Option(False, "--upstream"),
    unused_columns: bool = typer.Option(False, "--unused-columns"),
    god_columns: bool = typer.Option(False, "--god-columns"),
    min_refs: int = typer.Option(20, "--min-refs"),
    max_depth: int = typer.Option(3, "--max-depth"),
) -> None:
    """Column-level lineage and data flow analysis."""
    from ..commands.devtools import cmd_lineage as _cmd
    _cmd(migrations_dir=migrations_dir, json_input=json_input, dialect=dialect,
         at=at, out=out, column=column, format=fmt,
         upstream=upstream, unused_columns=unused_columns, god_columns=god_columns,
         min_refs=min_refs, max_depth=max_depth)


@app.command("classify")
def cmd_classify(
    migrations_dir: Optional[str] = typer.Argument(None),
    json_input: Optional[str] = typer.Option(None, "--json-input"),
    dialect: str = typer.Option("oracle", "--dialect"),
    at: Optional[str] = typer.Option(None, "--at"),
    out: Optional[str] = typer.Option(None, "--out"),
    fmt: str = typer.Option("text", "--format"),
    category: Optional[str] = typer.Option(None, "--category"),
) -> None:
    """Classify migrations by semantic category."""
    from ..commands.devtools import cmd_classify as _cmd
    _cmd(migrations_dir=migrations_dir, json_input=json_input, dialect=dialect,
         out=out, format=fmt, category=category)


@app.command("safety")
def cmd_safety(
    migrations_dir: Optional[str] = typer.Argument(None),
    json_input: Optional[str] = typer.Option(None, "--json-input"),
    dialect: str = typer.Option("oracle", "--dialect"),
    at: Optional[str] = typer.Option(None, "--at"),
    out: Optional[str] = typer.Option(None, "--out"),
    fmt: str = typer.Option("text", "--format"),
    threshold: Optional[str] = typer.Option(None, "--threshold"),
) -> None:
    """Score migrations by safety level."""
    from ..commands.devtools import cmd_safety as _cmd
    _cmd(migrations_dir=migrations_dir, json_input=json_input, dialect=dialect,
         out=out, format=fmt, threshold=threshold)


@app.command("domains")
def cmd_domains(
    migrations_dir: Optional[str] = typer.Argument(None),
    json_input: Optional[str] = typer.Option(None, "--json-input"),
    dialect: str = typer.Option("oracle", "--dialect"),
    at: Optional[str] = typer.Option(None, "--at"),
    out: Optional[str] = typer.Option(None, "--out"),
    fmt: str = typer.Option("text", "--format"),
) -> None:
    """Detect semantic business domains via community detection."""
    from ..commands.analysis import cmd_domains as _cmd
    _cmd(migrations_dir=migrations_dir, json_input=json_input, dialect=dialect,
         at=at, out=out, format=fmt)


@app.command("stability")
def cmd_stability(
    migrations_dir: Optional[str] = typer.Argument(None),
    json_input: Optional[str] = typer.Option(None, "--json-input"),
    dialect: str = typer.Option("oracle", "--dialect"),
    at: Optional[str] = typer.Option(None, "--at"),
    out: Optional[str] = typer.Option(None, "--out"),
    fmt: str = typer.Option("text", "--format"),
) -> None:
    """Calculate schema stability metrics and churn rates."""
    from ..commands.analysis import cmd_stability as _cmd
    _cmd(migrations_dir=migrations_dir, json_input=json_input, dialect=dialect,
         at=at, out=out, format=fmt)


@app.command("cost")
def cmd_cost(
    migrations_dir: str = typer.Argument(...),
    fmt: str = typer.Option("text", "--format"),
    out: Optional[str] = typer.Option(None, "--out"),
) -> None:
    """Estimate migration execution cost (heuristic)."""
    from ..commands.devtools import cmd_cost as _cmd
    _cmd(migrations_dir=migrations_dir, format=fmt, out=out)


@app.command("cache")
def cmd_cache(
    cache_action: str = typer.Argument(..., help="Action: clear | info"),
) -> None:
    """Manage the file-based caching system."""
    from ..commands.devtools import cmd_cache as _cmd
    _cmd(cache_action=cache_action)

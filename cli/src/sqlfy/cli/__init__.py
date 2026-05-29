"""
sqlfy.cli
=========
Typer-based CLI package for sqlfy.

This package provides a modern CLI built on Typer/Rich while the legacy
argparse interface in sqlfy.main remains fully functional.

Sub-apps (Typer groups):
  - schema        Schema state and dump commands
  - graph         Graph construction and visualization
  - analysis      Schema analysis, insights, health, integrity
  - intelligence  AI ask/chat/RAG commands
  - evolution     Diff, rollback-analysis, simulate, drift
  - devtools      Lint, validate, naming, deps, lineage, classify, safety
  - provenance    Git provenance and impact analysis
"""

import typer

from .schema import app as schema_app
from .graph import app as graph_app
from .analysis import app as analysis_app
from .evolution import app as evolution_app
from .intelligence import app as intelligence_app
from .devtools import app as devtools_app
from .provenance import app as provenance_app

app = typer.Typer(
    name="sqlfy",
    help="SQLfy — database schema intelligence for Flyway migrations.",
    no_args_is_help=True,
)

app.add_typer(schema_app, name="schema")
app.add_typer(graph_app, name="graph")
app.add_typer(analysis_app, name="analysis")
app.add_typer(evolution_app, name="evolution")
app.add_typer(intelligence_app, name="intelligence")
app.add_typer(devtools_app, name="devtools")
app.add_typer(provenance_app, name="provenance")

__all__ = ["app"]

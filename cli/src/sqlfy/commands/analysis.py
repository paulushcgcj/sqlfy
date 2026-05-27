"""Analysis commands: insights, health, domains, stability."""

import sys
import argparse

from ..domain.schema_state import SchemaStateBuilder
from ..reconstructor import reconstruct, reconstruct_at
from ..analysis.insights import InsightsEngine
from ._utils import load_files, write_output


def cmd_insights(args: argparse.Namespace) -> None:
    """Analyse the schema and report insights (orphans, missing PKs, circular FKs, etc.)."""
    files = load_files(args.migrations_dir, args.json_input)
    dialect = getattr(args, "dialect", "oracle")
    graph = (
        reconstruct_at(files, args.at, dialect=dialect)
        if getattr(args, "at", None)
        else reconstruct(files, dialect=dialect)
    )
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    report = InsightsEngine.analyse(state)

    if getattr(args, "severity", None):
        sev = args.severity.lower()
        report.findings = [f for f in report.findings if f.severity == sev]

    fmt = (args.format or "text").lower()
    write_output(report.to_json() if fmt == "json" else report.to_text(), args.out)

    if getattr(args, "strict", False) and report.errors():
        sys.exit(1)


def cmd_health(args: argparse.Namespace) -> None:
    """Generate a migration folder health report with score and per-file status."""
    from ..analysis.health import HealthAnalyzer

    files = load_files(args.migrations_dir, args.json_input)
    dialect = getattr(args, "dialect", "oracle")
    graph = (
        reconstruct_at(files, args.at, dialect=dialect)
        if getattr(args, "at", None)
        else reconstruct(files, dialect=dialect)
    )
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    report = InsightsEngine.analyse(state)
    health_report = HealthAnalyzer.analyze(state, report, args.migrations_dir or ".")

    fmt = (args.format or "text").lower()
    write_output(health_report.to_json() if fmt == "json" else health_report.to_text(), args.out)

    if getattr(args, "strict", False) and health_report.health_score.grade == "critical":
        sys.exit(1)


def cmd_domains(args: argparse.Namespace) -> None:
    """Detect semantic business domains via community detection and naming patterns."""
    from ..analysis.domains import detect_domains, format_text, format_json

    files = load_files(args.migrations_dir, args.json_input)
    dialect = getattr(args, "dialect", "oracle")
    graph = (
        reconstruct_at(files, version=args.at, dialect=dialect)
        if getattr(args, "at", None)
        else reconstruct(files, dialect=dialect)
    )
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    result = detect_domains(
        state,
        resolution=getattr(args, "resolution", 1.0),
        min_cohesion=getattr(args, "min_cohesion", 0.1),
        enable_splitting=not getattr(args, "no_split", False),
    )
    fmt = getattr(args, "format", "text")
    write_output(format_json(result) if fmt == "json" else format_text(result), args.out)


def cmd_stability(args: argparse.Namespace) -> None:
    """Calculate churn rates and stability scores per table."""
    from ..analysis.stability import calculate_stability, format_text, format_json

    files = load_files(args.migrations_dir, args.json_input)
    dialect = getattr(args, "dialect", "oracle")
    graph = (
        reconstruct_at(files, version=args.at, dialect=dialect)
        if getattr(args, "at", None)
        else reconstruct(files, dialect=dialect)
    )
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    report = calculate_stability(
        state,
        high_churn_threshold=getattr(args, "high_churn_threshold", 20.0),
        stable_threshold=getattr(args, "stable_threshold", 10.0),
    )
    fmt = getattr(args, "format", "text")
    show_all = getattr(args, "show_all", False)
    write_output(format_json(report) if fmt == "json" else format_text(report, show_all=show_all), args.out)

"""Analysis commands: insights, health, domains, stability."""

import sys

from ..domain.schema_state import SchemaStateBuilder
from ..reconstructor import reconstruct, reconstruct_at
from ..analysis.insights import InsightsEngine
from ._utils import load_files, write_output


def cmd_insights(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    at: str | None = None,
    format: str = "text",
    out: str | None = None,
    severity: str | None = None,
    strict: bool = False,
) -> None:
    """Analyse the schema and report insights (orphans, missing PKs, circular FKs, etc.)."""
    files = load_files(migrations_dir, json_input)
    graph = (
        reconstruct_at(files, at, dialect=dialect)
        if at
        else reconstruct(files, dialect=dialect)
    )
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    report = InsightsEngine.analyse(state, files=files)

    if severity:
        sev = severity.lower()
        report.findings = [f for f in report.findings if f.severity == sev]

    fmt = (format or "text").lower()
    write_output(report.to_json() if fmt == "json" else report.to_text(), out)

    if strict and report.errors():
        sys.exit(1)


def cmd_health(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    at: str | None = None,
    format: str = "text",
    out: str | None = None,
    strict: bool = False,
) -> None:
    """Generate a migration folder health report with score and per-file status."""
    from ..analysis.health import HealthAnalyzer

    files = load_files(migrations_dir, json_input)
    graph = (
        reconstruct_at(files, at, dialect=dialect)
        if at
        else reconstruct(files, dialect=dialect)
    )
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    report = InsightsEngine.analyse(state, files=files)
    health_report = HealthAnalyzer.analyze(state, report, migrations_dir or ".")

    fmt = (format or "text").lower()
    write_output(health_report.to_json() if fmt == "json" else health_report.to_text(), out)

    if strict and health_report.health_score.grade == "critical":
        sys.exit(1)


def cmd_domains(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    at: str | None = None,
    format: str = "text",
    out: str | None = None,
    resolution: float = 1.0,
    min_cohesion: float = 0.1,
    no_split: bool = False,
) -> None:
    """Detect semantic business domains via community detection and naming patterns."""
    from ..analysis.domains import detect_domains, format_text, format_json

    files = load_files(migrations_dir, json_input)
    graph = (
        reconstruct_at(files, version=at, dialect=dialect)
        if at
        else reconstruct(files, dialect=dialect)
    )
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    result = detect_domains(
        state,
        resolution=resolution,
        min_cohesion=min_cohesion,
        enable_splitting=not no_split,
    )
    fmt = (format or "text").lower()
    write_output(format_json(result) if fmt == "json" else format_text(result), out)


def cmd_stability(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    at: str | None = None,
    format: str = "text",
    out: str | None = None,
    high_churn_threshold: float = 20.0,
    stable_threshold: float = 10.0,
    show_all: bool = False,
) -> None:
    """Calculate churn rates and stability scores per table."""
    from ..analysis.stability import calculate_stability, format_text, format_json

    files = load_files(migrations_dir, json_input)
    graph = (
        reconstruct_at(files, version=at, dialect=dialect)
        if at
        else reconstruct(files, dialect=dialect)
    )
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    report = calculate_stability(
        state,
        high_churn_threshold=high_churn_threshold,
        stable_threshold=stable_threshold,
    )
    fmt = (format or "text").lower()
    write_output(format_json(report) if fmt == "json" else format_text(report, show_all=show_all), out)

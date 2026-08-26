"""Analysis commands: insights, health, domains, stability."""

from __future__ import annotations

import sys

from ..analysis.insights import InsightsEngine
from ..domain.schema_state import SchemaStateBuilder
from ..reconstructor import (
    ReconstructionError,
    Reconstructor,
    reconstruct,
    reconstruct_at,
)
from ._utils import load_files, validate_json_output, write_output


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
    detect_domains: bool = False,
    resolution: float = 1.0,
) -> None:
    """Analyse the schema and report insights (orphans, missing PKs, circular FKs, etc.)."""
    files = load_files(migrations_dir, json_input)
    try:
        reconstructor = Reconstructor(dialect=dialect, strict=strict)
        graph = (
            reconstructor.apply_up_to(files, at)
            if at
            else reconstructor.apply_all(files)
        )
    except ReconstructionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    state = SchemaStateBuilder.from_graph(graph, source_files=files)

    # Optionally detect communities for god-table & surprising-join analysis
    communities: dict[int, list[str]] | None = None
    if detect_domains:
        from ..clustering import detect_communities
        from ..graph.builder import build_networkx_graph

        nx_graph = build_networkx_graph(graph, directed=False)
        comm_result = detect_communities(
            nx_graph,
            resolution=resolution,
            min_cohesion=0.1,
            enable_splitting=True,
        )
        communities = comm_result.communities

    report = InsightsEngine.analyse(state, files=files, communities=communities)

    if severity:
        sev = severity.lower()
        report.findings = [f for f in report.findings if f.severity == sev]

    fmt = (format or "text").lower()
    if fmt == "json":
        # Include diagnostic totals in JSON output
        import json

        report_dict = json.loads(report.to_json())
        report_dict["diagnostics"] = {
            "total": len(reconstructor._all_diagnostics),
            "errors": len(
                [d for d in reconstructor._all_diagnostics if d.severity == "error"]
            ),
            "warnings": len(
                [d for d in reconstructor._all_diagnostics if d.severity == "warning"]
            ),
            "infos": len(
                [d for d in reconstructor._all_diagnostics if d.severity == "info"]
            ),
        }
        # Validate against contract before output
        output = json.dumps(report_dict, indent=2, ensure_ascii=False)
        valid, err = validate_json_output("insights", output)
        if not valid:
            print(f"Error: JSON output validation failed: {err}", file=sys.stderr)
            sys.exit(1)
    else:
        output = report.to_text()
    write_output(output, out)

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
    if fmt == "json":
        output = health_report.to_json()
        # Validate against contract before output
        valid, err = validate_json_output("health", output)
        if not valid:
            print(f"Error: JSON output validation failed: {err}", file=sys.stderr)
            sys.exit(1)
    else:
        output = health_report.to_text()
    write_output(output, out)

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
    from ..analysis.domains import detect_domains, format_json, format_text

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
    from ..analysis.stability import calculate_stability, format_json, format_text

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
    write_output(
        format_json(report)
        if fmt == "json"
        else format_text(report, show_all=show_all),
        out,
    )

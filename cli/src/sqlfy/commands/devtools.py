"""Developer tooling commands: lint, validate, deps, lineage, cache."""

import sys
import json
from pathlib import Path

from ..analysis import ordering
from ..domain.schema_state import SchemaStateBuilder
from ..reconstructor import reconstruct, reconstruct_at
from ._utils import load_files, write_output


def cmd_lint(
    *,
    path: str,
    dialect: str = "oracle",
    config: str | None = None,
    min_score: int = 0,
    format: str = "text",
    fix: bool = False,
    out: str | None = None,
    no_recursive: bool = False,
) -> None:
    """Lint migration SQL files for quality and style using sqlfluff."""
    from ..analysis.linter import (
        lint_migration, lint_directory, fix_migration,
        format_text, format_json,
        format_directory_text, format_directory_json,
        SQLFLUFF_AVAILABLE,
    )

    if not SQLFLUFF_AVAILABLE:
        print("Error: sqlfluff is not installed", file=sys.stderr)
        print("Install with: pip install sqlfluff>=3.0.0", file=sys.stderr)
        sys.exit(1)

    fmt = (format or "text").lower()
    p = Path(path)
    if not p.exists():
        print(f"Error: path does not exist: {path}", file=sys.stderr)
        sys.exit(1)

    if p.is_file():
        original = p.read_text(encoding="utf-8")
        if fix:
            try:
                fixed = fix_migration(original, p.name, dialect=dialect, config_path=config)
            except Exception as e:
                print(f"Error applying fixes: {e}", file=sys.stderr)
                sys.exit(1)

            if fixed != original:
                bak = p.with_name(p.name + '.bak')
                bak.write_text(original, encoding='utf-8')
                p.write_text(fixed, encoding='utf-8')
                print(f"Updated: {p} (backup: {bak})", file=sys.stderr)
            else:
                print(f"No changes for: {p}", file=sys.stderr)

            result = lint_migration(fixed, p.name, dialect=dialect, config_path=config)
        else:
            result = lint_migration(original, p.name, dialect=dialect, config_path=config)

        write_output(format_json(result) if fmt == "json" else format_text(result), out)
        if result.score < (min_score or 0):
            print(f"\nError: Score {result.score} is below minimum {min_score}", file=sys.stderr)
            sys.exit(1)
    else:
        if fix:
            sql_files = sorted([f for f in p.rglob("*.sql")])
            changed = 0
            for sql_file in sql_files:
                try:
                    original = sql_file.read_text(encoding='utf-8')
                    fixed = fix_migration(original, sql_file.name, dialect=dialect, config_path=config)
                    if fixed != original:
                        bak = sql_file.with_name(sql_file.name + '.bak')
                        bak.write_text(original, encoding='utf-8')
                        sql_file.write_text(fixed, encoding='utf-8')
                        changed += 1
                        print(f"Updated: {sql_file} (backup: {bak})", file=sys.stderr)
                except Exception as e:
                    print(f"Error fixing {sql_file}: {e}", file=sys.stderr)

            results = lint_directory(str(p), min_score=min_score, recursive=not no_recursive, dialect=dialect, config_path=config)
            write_output(format_directory_json(results) if fmt == "json" else format_directory_text(results), out)
            failed = [r for r in results if r.score < (min_score or 0)]
            if failed:
                print(f"\nError: {len(failed)}/{len(results)} files below minimum score {min_score}", file=sys.stderr)
                sys.exit(1)
            else:
                print(f"\nApplied fixes to {changed}/{len(sql_files)} files", file=sys.stderr)
        else:
            results = lint_directory(str(p), min_score=min_score, recursive=not no_recursive, dialect=dialect, config_path=config)
            write_output(format_directory_json(results) if fmt == "json" else format_directory_text(results), out)
            failed = [r for r in results if r.score < (min_score or 0)]
            if failed:
                print(f"\nError: {len(failed)}/{len(results)} files below minimum score {min_score}", file=sys.stderr)
                sys.exit(1)


def cmd_validate(
    *,
    migrations_dir: str,
    format: str = "text",
    out: str | None = None,
    fix_numbering: bool = False,
    strict: bool = False,
) -> int:
    """Validate migration ordering — detect gaps, duplicates, and out-of-order files."""
    migrations_path = Path(migrations_dir)
    if not migrations_path.is_dir():
        print(f"Error: migrations directory not found: {migrations_path}", file=sys.stderr)
        return 1

    report = ordering.validate_migrations(migrations_path)
    fmt = (format or "text").lower()
    write_output(
        ordering.format_json(report) if fmt == "json" else ordering.format_text(report, show_suggestions=True),
        out,
    )

    if fix_numbering:
        suggestions = ordering.suggest_renumbering(migrations_path)
        if suggestions:
            print("\n📋 Renumbering suggestions:")
            for s in suggestions:
                print(f"  {s['old']} → {s['new']}")
        else:
            print("\n✓ No renumbering needed")

    if report.has_errors:
        return 1
    if strict and report.has_warnings:
        return 1
    return 0


def cmd_naming(
    *,
    migrations_dir: str,
    format: str = "text",
    out: str | None = None,
    pattern: str = r"^[a-z0-9_]+$",
    max_len: int = 120,
    strict: bool = False,
) -> int:
    """Enforce migration naming conventions and report violations."""
    from ..analysis import naming

    migrations_path = Path(migrations_dir)
    if not migrations_path.is_dir():
        print(f"Error: migrations directory not found: {migrations_path}", file=sys.stderr)
        return 1

    report = naming.validate_naming(migrations_path, pattern=pattern, max_length=max_len)

    fmt = (format or "text").lower()
    write_output(naming.format_json(report) if fmt == "json" else naming.format_text(report), out)

    if report.has_errors:
        return 1
    if strict and report.has_warnings:
        return 1
    return 0


def cmd_deps(
    *,
    migrations_dir: str,
    format: str = "text",
    out: str | None = None,
    validate: bool = False,
    strict: bool = False,
    critical_path: bool = False,
    summary_only: bool = False,
) -> int:
    """Analyze migration dependencies — detect circular deps and critical path."""
    from ..analysis.deps import analyze_dependencies, format_text, format_json, format_dot, validate_dependencies

    migrations_path = Path(migrations_dir)
    if not migrations_path.is_dir():
        print(f"Error: migrations directory not found: {migrations_path}", file=sys.stderr)
        return 1

    try:
        analysis = analyze_dependencies(migrations_path)
        fmt = (format or "text").lower()
        show_details = not summary_only

        if fmt == "json":
            output = format_json(analysis)
        elif fmt == "dot":
            output = format_dot(analysis)
        else:
            output = format_text(analysis, show_details=show_details)
        write_output(output, out)

        if validate:
            is_valid, message = validate_dependencies(analysis, strict=strict)
            print(f"\n{message}", file=sys.stderr)
            if not is_valid:
                return 1

        if critical_path and analysis.critical_path:
            print("\n🔴 Critical Path:", file=sys.stderr)
            print(f"  {' → '.join(analysis.critical_path)}", file=sys.stderr)
            print(f"  ({len(analysis.critical_path)} migrations must run sequentially)", file=sys.stderr)

        error_count = sum(1 for issue in analysis.issues if issue.severity == "error")
        warning_count = sum(1 for issue in analysis.issues if issue.severity == "warning")
        if error_count > 0:
            return 1
        if strict and warning_count > 0:
            return 1
        return 0

    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Install networkx: pip install networkx", file=sys.stderr)
        return 1
    except Exception as e:
        import traceback
        print(f"Error analyzing dependencies: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


def cmd_lineage(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    at: str | None = None,
    column: str | None = None,
    format: str = "text",
    out: str | None = None,
    upstream: bool = False,
    unused_columns: bool = False,
    god_columns: bool = False,
    min_refs: int = 20,
    max_depth: int = 3,
) -> None:
    """Column-level lineage and data flow analysis."""
    from ..analysis.lineage import (
        extract_column_lineage, find_downstream, find_upstream,
        find_unused_columns, find_god_columns,
        format_lineage_text, format_lineage_json, format_lineage_mermaid,
    )

    files = load_files(migrations_dir, json_input)
    graph = (
        reconstruct_at(files, at, dialect=dialect)
        if at
        else reconstruct(files, dialect=dialect)
    )
    lineage_files = [(f['filename'], f['sql']) for f in files]
    lineage = extract_column_lineage(graph, lineage_files)
    fmt = (format or "text").lower()

    if unused_columns:
        unused = find_unused_columns(graph, lineage)
        if fmt == "json":
            output = json.dumps({
                "unused_columns": [
                    {"column": col.full_name, "table": col.table, "column_name": col.column, "created_in": version}
                    for col, version in unused
                ]
            }, indent=2)
        else:
            lines = [f"Unused Columns Report", "=" * 60, "", f"Found {len(unused)} unused column(s):", ""]
            for col, version in unused:
                lines += [f"  {col.full_name}", f"    Created: {version}", f"    Status: Never referenced", ""]
            if not unused:
                lines.append("  (none)")
            output = "\n".join(lines)
        write_output(output, out)
        print(f"  {len(unused)} unused column(s)", file=sys.stderr)

    elif god_columns:
        god_cols = find_god_columns(lineage, min_refs=min_refs)
        if fmt == "json":
            output = json.dumps({
                "god_columns": [
                    {"column": col.full_name, "table": col.table, "column_name": col.column, "reference_count": refs}
                    for col, refs in god_cols
                ]
            }, indent=2)
        else:
            lines = [f"God Columns Report (min_refs={min_refs})", "=" * 60, "", f"Found {len(god_cols)} god column(s):", ""]
            for col, refs in god_cols:
                lines.append(f"  {col.full_name}")
                lines.append(f"    Total references: {refs}")
                if col.id in lineage:
                    col_lineage = lineage[col.id]
                    lines.append(f"    Downstream columns: {len(col_lineage.downstream)}")
                lines.append("")
            if not god_cols:
                lines.append("  (none)")
            output = "\n".join(lines)
        write_output(output, out)
        print(f"  {len(god_cols)} god column(s)", file=sys.stderr)

    elif column:
        col_id = column.upper()
        if col_id not in lineage:
            print(f"Error: Column not found: {column}", file=sys.stderr)
            print("Hint: Use format TABLE.COLUMN (e.g., APP.USERS.EMAIL)", file=sys.stderr)
            sys.exit(1)
        direction = "upstream" if upstream else "downstream"
        if fmt == "json":
            output = json.dumps(lineage[col_id].to_dict(), indent=2)
        elif fmt == "mermaid":
            output = format_lineage_mermaid(col_id, lineage, direction=direction, max_depth=max_depth)
        else:
            output = format_lineage_text(col_id, lineage, direction=direction)
        write_output(output, out)
        col_lineage = lineage[col_id]
        deps = col_lineage.upstream if direction == "upstream" else col_lineage.downstream
        print(f"  {len(deps)} {direction} column(s)", file=sys.stderr)

    else:
        if fmt == "json":
            output = json.dumps(format_lineage_json(lineage), indent=2)
        else:
            pk_count = sum(1 for c in lineage.values() if c.is_pk)
            fk_count = sum(1 for c in lineage.values() if c.is_fk)
            with_upstream = sum(1 for c in lineage.values() if c.upstream)
            with_downstream = sum(1 for c in lineage.values() if c.downstream)
            lines = [
                "Column Lineage Summary", "=" * 60, "",
                f"Total columns analyzed: {len(lineage)}", "",
                f"  Primary key columns: {pk_count}",
                f"  Foreign key columns: {fk_count}",
                f"  Columns with upstream deps: {with_upstream}",
                f"  Columns with downstream deps: {with_downstream}", "",
                "Usage:",
                "  sqlfy lineage TABLE.COLUMN            # Analyze specific column",
                "  sqlfy lineage --unused-columns        # Find unused columns",
                "  sqlfy lineage --god-columns          # Find heavily used columns",
            ]
            output = "\n".join(lines)
        write_output(output, out)
        print(f"  {len(lineage)} column(s) analyzed", file=sys.stderr)


def cmd_classify(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    format: str = "text",
    out: str | None = None,
    category: str | None = None,
    risk: str | None = None,
    group_by: bool = False,
) -> int:
    """Classify migrations by semantic category (table_creation, data_migration, etc.)."""
    from ..analysis.classifier import (
        classify_migrations, format_text, format_json, MigrationCategory,
    )

    files = load_files(migrations_dir, json_input)
    classifications = classify_migrations(files, dialect=dialect)

    if category:
        try:
            cat = MigrationCategory(category)
            classifications = [c for c in classifications if c.primary_category == cat]
        except ValueError:
            print(f"Error: unknown category '{category}'", file=sys.stderr)
            print(
                "Valid categories: table_creation, column_addition, column_removal, "
                "constraint_modification, index_management, data_migration, "
                "cleanup, refactor, view_trigger_procedure, mixed",
                file=sys.stderr,
            )
            return 1

    if risk:
        classifications = [c for c in classifications if c.risk_level == risk]

    fmt = (format or "text").lower()
    write_output(format_json(classifications) if fmt == "json" else format_text(classifications, group_by=group_by), out)
    return 0


def cmd_safety(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    format: str = "text",
    out: str | None = None,
    threshold: str | None = None,
    verbose: bool = False,
) -> int:
    """Score migrations by safety level (SAFE / MEDIUM_RISK / HIGH_RISK / DANGEROUS)."""
    from ..analysis.safety import score_migrations, format_text, format_json

    files = load_files(migrations_dir, json_input)
    scores = score_migrations(files, dialect=dialect)

    fmt = (format or "text").lower()
    write_output(format_json(scores) if fmt == "json" else format_text(scores, verbose=verbose), out)

    if threshold:
        _order = {"safe": 0, "medium": 1, "high": 2, "dangerous": 3}
        _score_order = {"SAFE": 0, "MEDIUM_RISK": 1, "HIGH_RISK": 2, "DANGEROUS": 3}
        min_ord = _order.get(threshold, 0)
        violations = [s for s in scores if _score_order[s.overall_level] >= min_ord]
        if violations:
            print(
                f"\n❌ {len(violations)} migration(s) at or above threshold '{threshold}'",
                file=sys.stderr,
            )
            return 1
    return 0


def cmd_cost(
    *,
    migrations_dir: str,
    dialect: str = "oracle",
    format: str = "text",
    out: str | None = None,
    no_recursive: bool = False,
    verbose: bool = False,
    table_stats: str | None = None,
    throughput: float | None = None,
    weight_profile: str = "default",
) -> int:
    """Estimate migration execution cost based on SQL operations."""
    from ..analysis.cost_estimator import estimate_migrations, format_text, format_json

    if no_recursive:
        p = Path(migrations_dir)
        if not p.is_dir():
            print(f"Error: migrations directory not found: {p}", file=sys.stderr)
            return 1
        sql_files = sorted([f for f in p.glob("*.sql") if f.is_file()])
        files = [{"filename": str(f.relative_to(p)), "sql": f.read_text(encoding="utf-8")} for f in sql_files]
        print(f"Loaded {len(files)} migration file(s) from {p} (no-recursive)", file=sys.stderr)
    else:
        files = load_files(migrations_dir, None)

    table_stats_data = None
    if table_stats:
        stats_path = Path(table_stats)
        if not stats_path.exists():
            print(f"Error: table stats file not found: {stats_path}", file=sys.stderr)
            return 1
        try:
            raw = json.loads(stats_path.read_text(encoding="utf-8"))
            table_stats_data = {str(k).lower(): v for k, v in raw.items()}
        except Exception as e:
            print(f"Error reading table stats: {e}", file=sys.stderr)
            return 1

    fmt = (format or "text").lower()
    if throughput is not None:
        try:
            throughput_bps = int(float(throughput) * 1024.0 * 1024.0)
        except Exception:
            print(f"Error: invalid --throughput value: {throughput}", file=sys.stderr)
            return 1
        results = estimate_migrations(files, dialect=dialect, table_stats=table_stats_data, throughput_bytes_per_sec=throughput_bps, weight_profile=weight_profile)
    else:
        results = estimate_migrations(files, dialect=dialect, table_stats=table_stats_data, weight_profile=weight_profile)

    write_output(format_json(results) if fmt == "json" else format_text(results, verbose=verbose, weight_profile=weight_profile), out)
    return 0


def cmd_cache(
    *,
    cache_action: str,
) -> None:
    """Manage the file-based caching system (clear or show info)."""
    from ..cache import clear_cache, _CACHE_ROOT

    if cache_action == "clear":
        clear_cache()
        print("✓ Cache cleared")
    elif cache_action == "info":
        cache_dir = _CACHE_ROOT / "migrations"
        stat_index = _CACHE_ROOT / "stat-index.json"

        if not cache_dir.exists() and not stat_index.exists():
            print("Cache is empty")
            return

        cache_count = len(list(cache_dir.glob("*.json"))) if cache_dir.exists() else 0
        total_size = 0
        if cache_dir.exists():
            for f in cache_dir.glob("*.json"):
                try:
                    total_size += f.stat().st_size
                except OSError:
                    pass
        if stat_index.exists():
            try:
                total_size += stat_index.stat().st_size
            except OSError:
                pass

        print(f"Cache location: {_CACHE_ROOT}")
        print(f"Cached entries: {cache_count}")
        print(f"Total size: {total_size / (1024 * 1024):.2f} MB")


def cmd_pii_scan(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    at: str | None = None,
    format: str = "text",
    out: str | None = None,
    min_confidence: float = 0.6,
    extra_patterns: str | None = None,
) -> int:
    """Scan schema columns for PII patterns."""
    from ..analysis.pii_scanner import scan_pii, format_text

    extra: dict[str, list[str]] | None = None
    if extra_patterns:
        ep_path = Path(extra_patterns)
        if not ep_path.exists():
            print(f"Error: extra-patterns file not found: {extra_patterns}", file=sys.stderr)
            return 1
        try:
            extra = json.loads(ep_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Error reading extra-patterns file: {e}", file=sys.stderr)
            return 1

    files = load_files(migrations_dir, json_input)
    graph = (
        reconstruct_at(files, at, dialect=dialect)
        if at
        else reconstruct(files, dialect=dialect)
    )
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    result = scan_pii(state, extra_patterns=extra)

    # Filter by min-confidence
    if min_confidence > 0.0:
        result.findings = [f for f in result.findings if f.confidence >= min_confidence]
        result.pii_column_count = len(result.findings)
        result.pii_table_count = len({f.table_name for f in result.findings})

    fmt = (format or "text").lower()

    if fmt == "json":
        from ..models import PiiScanFinding as PiiScanFindingModel, PiiScanResult as PiiScanResultModel

        findings = [
            PiiScanFindingModel(
                table_name=f.table_name,
                column_name=f.column_name,
                column_type=f.column_type,
                pii_categories=f.pii_categories,
                confidence=f.confidence,
                evidence=f.evidence,
            )
            for f in result.findings
        ]
        model = PiiScanResultModel(
            findings=findings,
            tables_scanned=result.tables_scanned,
            columns_scanned=result.columns_scanned,
            pii_table_count=result.pii_table_count,
            pii_column_count=result.pii_column_count,
        )
        write_output(model.model_dump_json(by_alias=True, indent=2), out)
    else:
        write_output(format_text(result), out)

    if not result.findings:
        print("No PII columns found.", file=sys.stderr)

    return 0

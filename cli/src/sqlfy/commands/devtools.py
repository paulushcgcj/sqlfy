"""Developer tooling commands: lint, validate, deps, lineage, cache."""

import sys
import json
import argparse
from pathlib import Path

from ..analysis import ordering
from ..reconstructor import reconstruct, reconstruct_at
from ._utils import load_files, write_output


def cmd_lint(args: argparse.Namespace) -> None:
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

    path = args.path
    dialect = getattr(args, "dialect", "oracle")
    config_path = getattr(args, "config", None)
    min_score = getattr(args, "min_score", 0)
    fmt = getattr(args, "format", "text")

    p = Path(path)
    if not p.exists():
        print(f"Error: path does not exist: {path}", file=sys.stderr)
        sys.exit(1)

    if p.is_file():
        original = p.read_text(encoding="utf-8")
        if getattr(args, "fix", False):
            try:
                fixed = fix_migration(original, p.name, dialect=dialect, config_path=config_path)
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

            result = lint_migration(fixed, p.name, dialect=dialect, config_path=config_path)
        else:
            result = lint_migration(original, p.name, dialect=dialect, config_path=config_path)

        write_output(format_json(result) if fmt == "json" else format_text(result), args.out)
        if result.score < min_score:
            print(f"\nError: Score {result.score} is below minimum {min_score}", file=sys.stderr)
            sys.exit(1)
    else:
        # Directory path
        if getattr(args, "fix", False):
            # Apply fixes in-place per-file, writing a .bak for each original
            sql_files = sorted([f for f in p.rglob("*.sql")])
            changed = 0
            for sql_file in sql_files:
                try:
                    original = sql_file.read_text(encoding='utf-8')
                    fixed = fix_migration(original, sql_file.name, dialect=dialect, config_path=config_path)
                    if fixed != original:
                        bak = sql_file.with_name(sql_file.name + '.bak')
                        bak.write_text(original, encoding='utf-8')
                        sql_file.write_text(fixed, encoding='utf-8')
                        changed += 1
                        print(f"Updated: {sql_file} (backup: {bak})", file=sys.stderr)
                except Exception as e:
                    print(f"Error fixing {sql_file}: {e}", file=sys.stderr)

            # Re-run lint to show updated results
            results = lint_directory(str(p), min_score=min_score, recursive=not getattr(args, "no_recursive", False), dialect=dialect, config_path=config_path)
            write_output(format_directory_json(results) if fmt == "json" else format_directory_text(results), args.out)
            failed = [r for r in results if r.score < min_score]
            if failed:
                print(f"\nError: {len(failed)}/{len(results)} files below minimum score {min_score}", file=sys.stderr)
                sys.exit(1)
            else:
                print(f"\nApplied fixes to {changed}/{len(sql_files)} files", file=sys.stderr)
        else:
            results = lint_directory(str(p), min_score=min_score, recursive=not getattr(args, "no_recursive", False), dialect=dialect, config_path=config_path)
            write_output(format_directory_json(results) if fmt == "json" else format_directory_text(results), args.out)
            failed = [r for r in results if r.score < min_score]
            if failed:
                print(f"\nError: {len(failed)}/{len(results)} files below minimum score {min_score}", file=sys.stderr)
                sys.exit(1)


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate migration ordering — detect gaps, duplicates, and out-of-order files."""
    migrations_dir = Path(args.migrations_dir)
    if not migrations_dir.is_dir():
        print(f"Error: migrations directory not found: {migrations_dir}", file=sys.stderr)
        return 1

    report = ordering.validate_migrations(migrations_dir)
    fmt = getattr(args, "format", "text")
    write_output(
        ordering.format_json(report) if fmt == "json" else ordering.format_text(report, show_suggestions=True),
        getattr(args, "out", None),
    )

    if getattr(args, "fix_numbering", False):
        suggestions = ordering.suggest_renumbering(migrations_dir)
        if suggestions:
            print("\n📋 Renumbering suggestions:")
            for s in suggestions:
                print(f"  {s['old']} → {s['new']}")
        else:
            print("\n✓ No renumbering needed")

    if report.has_errors:
        return 1
    if getattr(args, "strict", False) and report.has_warnings:
        return 1
    return 0


def cmd_naming(args: argparse.Namespace) -> int:
    """Enforce migration naming conventions and report violations."""
    from ..analysis import naming

    migrations_dir = Path(args.migrations_dir)
    if not migrations_dir.is_dir():
        print(f"Error: migrations directory not found: {migrations_dir}", file=sys.stderr)
        return 1

    pattern = getattr(args, "pattern", r"^[a-z0-9_]+$")
    max_len = getattr(args, "max_len", 120)

    # Use the on-disk validator
    report = naming.validate_naming(migrations_dir, pattern=pattern, max_length=max_len)

    fmt = getattr(args, "format", "text")
    if fmt == "json":
        output = naming.format_json(report)
    else:
        output = naming.format_text(report)

    write_output(output, getattr(args, "out", None))

    if report.has_errors:
        return 1
    if getattr(args, "strict", False) and report.has_warnings:
        return 1
    return 0


def cmd_deps(args: argparse.Namespace) -> int:
    """Analyze migration dependencies — detect circular deps and critical path."""
    from ..analysis.deps import analyze_dependencies, format_text, format_json, format_dot, validate_dependencies

    migrations_dir = Path(args.migrations_dir)
    if not migrations_dir.is_dir():
        print(f"Error: migrations directory not found: {migrations_dir}", file=sys.stderr)
        return 1

    try:
        analysis = analyze_dependencies(migrations_dir)
        fmt = getattr(args, "format", "text")
        show_details = not getattr(args, "summary_only", False)

        if fmt == "json":
            output = format_json(analysis)
        elif fmt == "dot":
            output = format_dot(analysis)
        else:
            output = format_text(analysis, show_details=show_details)
        write_output(output, getattr(args, "out", None))

        if getattr(args, "validate", False):
            is_valid, message = validate_dependencies(analysis, strict=getattr(args, "strict", False))
            print(f"\n{message}", file=sys.stderr)
            if not is_valid:
                return 1

        if getattr(args, "critical_path", False) and analysis.critical_path:
            print("\n🔴 Critical Path:", file=sys.stderr)
            print(f"  {' → '.join(analysis.critical_path)}", file=sys.stderr)
            print(f"  ({len(analysis.critical_path)} migrations must run sequentially)", file=sys.stderr)

        error_count = sum(1 for issue in analysis.issues if issue.severity == "error")
        warning_count = sum(1 for issue in analysis.issues if issue.severity == "warning")
        if error_count > 0:
            return 1
        if getattr(args, "strict", False) and warning_count > 0:
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


def cmd_lineage(args: argparse.Namespace) -> None:
    """Column-level lineage and data flow analysis."""
    from ..analysis.lineage import (
        extract_column_lineage, find_downstream, find_upstream,
        find_unused_columns, find_god_columns,
        format_lineage_text, format_lineage_json, format_lineage_mermaid,
    )

    files = load_files(args.migrations_dir, args.json_input)
    dialect = getattr(args, "dialect", "oracle")
    graph = (
        reconstruct_at(files, args.at, dialect=dialect)
        if getattr(args, "at", None)
        else reconstruct(files, dialect=dialect)
    )
    lineage = extract_column_lineage(graph, files)
    fmt = getattr(args, "format", "text")

    if getattr(args, "unused_columns", False):
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
        write_output(output, args.out)
        print(f"  {len(unused)} unused column(s)", file=sys.stderr)

    elif getattr(args, "god_columns", False):
        min_refs = getattr(args, "min_refs", 20)
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
        write_output(output, args.out)
        print(f"  {len(god_cols)} god column(s)", file=sys.stderr)

    elif args.column:
        column = args.column.upper()
        if column not in lineage:
            print(f"Error: Column not found: {column}", file=sys.stderr)
            print("Hint: Use format TABLE.COLUMN (e.g., APP.USERS.EMAIL)", file=sys.stderr)
            sys.exit(1)
        direction = "upstream" if getattr(args, "upstream", False) else "downstream"
        if fmt == "json":
            output = json.dumps(lineage[column].to_dict(), indent=2)
        elif fmt == "mermaid":
            output = format_lineage_mermaid(column, lineage, direction=direction, max_depth=getattr(args, "max_depth", 3))
        else:
            output = format_lineage_text(column, lineage, direction=direction)
        write_output(output, args.out)
        col_lineage = lineage[column]
        deps = col_lineage.upstream if direction == "upstream" else col_lineage.downstream
        print(f"  {len(deps)} {direction} column(s)", file=sys.stderr)

    else:
        if fmt == "json":
            output = format_lineage_json(lineage)
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
        write_output(output, args.out)
        print(f"  {len(lineage)} column(s) analyzed", file=sys.stderr)


def cmd_classify(args: argparse.Namespace) -> int:
    """Classify migrations by semantic category (table_creation, data_migration, etc.)."""
    from ..analysis.classifier import (
        classify_migrations, format_text, format_json, MigrationCategory,
    )

    files = load_files(args.migrations_dir, args.json_input)
    dialect = getattr(args, "dialect", "oracle")

    classifications = classify_migrations(files, dialect=dialect)

    # Filter by primary category
    category_filter = getattr(args, "category", None)
    if category_filter:
        try:
            cat = MigrationCategory(category_filter)
            classifications = [c for c in classifications if c.primary_category == cat]
        except ValueError:
            print(f"Error: unknown category '{category_filter}'", file=sys.stderr)
            print(
                "Valid categories: table_creation, column_addition, column_removal, "
                "constraint_modification, index_management, data_migration, "
                "cleanup, refactor, view_trigger_procedure, mixed",
                file=sys.stderr,
            )
            return 1

    # Filter by risk level
    risk_filter = getattr(args, "risk", None)
    if risk_filter:
        classifications = [c for c in classifications if c.risk_level == risk_filter]

    fmt = getattr(args, "format", "text")
    group_by = getattr(args, "group_by", False)

    if fmt == "json":
        output = format_json(classifications)
    else:
        output = format_text(classifications, group_by=group_by)

    write_output(output, getattr(args, "out", None))
    return 0


def cmd_safety(args: argparse.Namespace) -> int:
    """Score migrations by safety level (SAFE / MEDIUM_RISK / HIGH_RISK / DANGEROUS)."""
    from ..analysis.safety import score_migrations, format_text, format_json

    files = load_files(args.migrations_dir, args.json_input)
    dialect = getattr(args, "dialect", "oracle")

    scores = score_migrations(files, dialect=dialect)

    fmt = getattr(args, "format", "text")
    verbose = getattr(args, "verbose", False)
    output = format_json(scores) if fmt == "json" else format_text(scores, verbose=verbose)
    write_output(output, getattr(args, "out", None))

    threshold = getattr(args, "threshold", None)
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


def cmd_cost(args: argparse.Namespace) -> int:
    """Estimate migration execution cost based on SQL operations."""
    from ..analysis.cost_estimator import estimate_migrations, format_text, format_json

    dialect = getattr(args, "dialect", "oracle")

    # Respect --no-recursive: load top-level files only when requested
    if getattr(args, "no_recursive", False):
        from pathlib import Path

        p = Path(args.migrations_dir)
        if not p.is_dir():
            print(f"Error: migrations directory not found: {p}", file=sys.stderr)
            return 1
        sql_files = sorted([f for f in p.glob("*.sql") if f.is_file()])
        files = [{"filename": str(f.relative_to(p)), "sql": f.read_text(encoding="utf-8")} for f in sql_files]
        print(f"Loaded {len(files)} migration file(s) from {p} (no-recursive)", file=sys.stderr)
    else:
        files = load_files(args.migrations_dir, getattr(args, "json_input", None))

    # Load optional table stats JSON
    table_stats = None
    if getattr(args, "table_stats", None):
        stats_path = Path(getattr(args, "table_stats"))
        if not stats_path.exists():
            print(f"Error: table stats file not found: {stats_path}", file=sys.stderr)
            return 1
        try:
            raw = json.loads(stats_path.read_text(encoding="utf-8"))
            # normalize keys to lower-case
            table_stats = {str(k).lower(): v for k, v in raw.items()}
        except Exception as e:
            print(f"Error reading table stats: {e}", file=sys.stderr)
            return 1

    # Allow throughput override (MB/s) -> convert to bytes/sec
    throughput = getattr(args, "throughput", None)
    weight_profile = getattr(args, "weight_profile", "default")
    if throughput is not None:
        try:
            throughput_bps = float(throughput) * 1024.0 * 1024.0
        except Exception:
            print(f"Error: invalid --throughput value: {throughput}", file=sys.stderr)
            return 1
        results = estimate_migrations(files, dialect=dialect, table_stats=table_stats, throughput_bytes_per_sec=throughput_bps, weight_profile=weight_profile)
    else:
        results = estimate_migrations(files, dialect=dialect, table_stats=table_stats, weight_profile=weight_profile)

    fmt = getattr(args, "format", "text")
    verbose = getattr(args, "verbose", False)
    if fmt == "json":
        output = format_json(results)
    else:
        output = format_text(results, verbose=verbose, weight_profile=weight_profile)

    write_output(output, getattr(args, "out", None))
    return 0


def cmd_cache(args: argparse.Namespace) -> None:
    """Manage the file-based caching system (clear or show info)."""
    from ..cache import clear_cache, _CACHE_ROOT

    action = args.cache_action

    if action == "clear":
        clear_cache()
        print("✓ Cache cleared")
    elif action == "info":
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

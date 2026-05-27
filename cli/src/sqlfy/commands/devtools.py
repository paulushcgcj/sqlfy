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
        lint_migration, lint_directory,
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
        result = lint_migration(p.read_text(encoding="utf-8"), p.name, dialect=dialect, config_path=config_path)
        write_output(format_json(result) if fmt == "json" else format_text(result), args.out)
        if result.score < min_score:
            print(f"\nError: Score {result.score} is below minimum {min_score}", file=sys.stderr)
            sys.exit(1)
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

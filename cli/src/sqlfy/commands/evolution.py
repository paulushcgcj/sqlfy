"""Schema evolution commands: diff, rollback-analysis, simulate, drift, integrity."""

import sys
import json
from pathlib import Path

from ..domain.schema_state import SchemaStateBuilder
from ..reconstructor import reconstruct, reconstruct_at
from ..analysis.differ import SchemaDiffer, diff_files
from ._utils import load_files, write_output


def cmd_diff(
    *,
    state_a: str,
    state_b: str,
    dialect: str = "oracle",
    format: str = "text",
    out: str | None = None,
) -> None:
    """Compare two schema states or migration directories."""
    import os

    def is_json_file(p: str) -> bool:
        return os.path.isfile(p) and p.endswith(".json")

    if is_json_file(state_a) and is_json_file(state_b):
        result = diff_files(state_a, state_b)
    else:
        def load_dir(path: str):
            p = Path(path)
            if not p.is_dir():
                print(f'Error: "{path}" is not a directory or .json state file.', file=sys.stderr)
                sys.exit(1)
            sql_files = sorted(
                (f for f in p.rglob("*") if f.is_file() and f.suffix.lower() == ".sql"),
                key=lambda mp: (mp.name, str(mp.relative_to(p))),
            )
            files = [{"filename": str(f.relative_to(p)), "sql": f.read_text(encoding="utf-8")} for f in sql_files]
            print(f"Loaded {len(files)} migration(s) from {path}", file=sys.stderr)
            return SchemaStateBuilder.from_graph(reconstruct(files, dialect=dialect))

        result = SchemaDiffer.diff(load_dir(state_a), load_dir(state_b))

    fmt = (format or "text").lower()
    write_output(result.to_json() if fmt == "json" else result.to_text(), out)


def cmd_diff_versions(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    from_version: str | None = None,
    to_version: str | None = None,
    format: str = "json",
    out: str | None = None,
) -> None:
    """Compare two version snapshots from the same migration set."""
    files = load_files(migrations_dir, json_input)

    state_a = SchemaStateBuilder.from_graph(
        reconstruct_at(files, from_version, dialect=dialect) if from_version else reconstruct(files, dialect=dialect)
    )
    state_b = SchemaStateBuilder.from_graph(
        reconstruct_at(files, to_version, dialect=dialect) if to_version else reconstruct(files, dialect=dialect)
    )

    result = SchemaDiffer.diff(state_a, state_b)
    fmt = (format or "json").lower()
    write_output(result.to_json() if fmt == "json" else result.to_text(), out)


def cmd_rollback_analysis(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    at: str | None = None,
    out: str | None = None,
    format: str = "text",
    generate: bool = False,
) -> None:
    """Analyze migration rollback feasibility."""
    files = load_files(migrations_dir, json_input, use_cache=False)
    from ..analysis.rollback import analyze_migrations, format_rollback_text, format_rollback_json

    results = analyze_migrations(files)
    fmt = (format or "text").lower()
    write_output(format_rollback_json(results) if fmt == "json" else format_rollback_text(results), out)

    reversible = sum(1 for r in results if r.feasibility == "reversible")
    partial = sum(1 for r in results if r.feasibility == "partial")
    irreversible = sum(1 for r in results if r.feasibility == "irreversible")
    print(f"  {len(results)} migrations analyzed", file=sys.stderr)
    print(f"  ✓ {reversible} reversible, ⚠️  {partial} partial, ✗ {irreversible} irreversible", file=sys.stderr)


def cmd_simulate(
    *,
    migrations_dir: str | None = None,
    json_input: str | None = None,
    dialect: str = "oracle",
    at: str | None = None,
    out: str | None = None,
    sql: str | None = None,
    file: str | None = None,
    format: str = "text",
    diff: bool = False,
    strict: bool = False,
) -> None:
    """Simulate schema evolution with hypothetical SQL."""
    from ..analysis.simulator import SchemaSimulator

    files = load_files(migrations_dir, json_input)
    simulator = SchemaSimulator(files, base_version=at, dialect=dialect)

    if sql:
        result = simulator.simulate_sql(sql)
    elif file:
        result = simulator.simulate_file(file)
    else:
        print("Error: Must provide --sql or --file", file=sys.stderr)
        sys.exit(1)

    fmt = (format or "text").lower()
    write_output(result.to_json() if fmt == "json" else result.to_text(), out)

    if diff:
        print("\n" + "=" * 60 + "\nDIFF:\n" + "=" * 60)
        print(result.diff.to_text())

    if strict and not result.is_safe():
        sys.exit(1)


def cmd_integrity(
    *,
    migrations_dir: str,
    format: str = "text",
    update_manifest: bool = False,
    out: str | None = None,
    strict: bool = False,
) -> None:
    """Check migration file integrity using SHA256 hashes."""
    from ..analysis.integrity import check_integrity, update_manifest as _update_manifest

    migrations_dir_path = Path(migrations_dir)
    fmt = (format or "text").lower()

    if update_manifest:
        _update_manifest(migrations_dir_path)
        if fmt == "json":
            write_output(json.dumps({"updated": True}, indent=2), out)
        else:
            print("✓ Manifest updated")
        return

    report = check_integrity(migrations_dir_path)

    if fmt == "json":
        output = json.dumps({
            "status": report.status,
            "totalMigrations": report.total_migrations,
            "modified": report.modified,
            "missing": report.missing,
            "new": report.new,
        }, indent=2, ensure_ascii=False)
        write_output(output, out)
        if strict and report.modified:
            sys.exit(1)
        return

    if report.status == "clean":
        print(f"✓ All {report.total_migrations} migrations verified")
    else:
        if report.modified:
            print("\n⚠ Modified migrations:")
            for m in report.modified:
                print(f"  {m['filename']} (V{m['version']})")
                print(f"    Old: {m['old_hash'][:12]}...")
                print(f"    New: {m['new_hash'][:12]}...")

        if report.missing:
            print("\n⚠ Missing migrations:")
            for m in report.missing:
                print(f"  {m['filename']} (V{m['version']})")

        if report.new:
            print(f"\n✓ New migrations ({len(report.new)}):")
            for m in report.new:
                print(f"  {m['filename']} (V{m['version']})")

    if strict and report.modified:
        print("\nError: Modified migrations detected (--strict mode)")
        sys.exit(1)


def cmd_drift(
    *,
    base_migrations: str,
    target_migrations: str,
    dialect: str = "oracle",
    format: str = "text",
    generate_migration: bool = False,
    next_version: str | None = None,
    description: str = "catch_up_drift",
    out: str | None = None,
) -> None:
    """Detect schema drift between two migration folders and optionally generate repair SQL."""
    from ..analysis.drift_repair import analyze_drift, generate_repair_migration

    base_files = load_files(base_migrations, None, use_cache=False)
    base_graph = reconstruct(base_files, dialect=dialect)

    target_files = load_files(target_migrations, None, use_cache=False)
    target_graph = reconstruct(target_files, dialect=dialect)

    base_label = Path(base_migrations).name if base_migrations else "Base"
    target_label = Path(target_migrations).name if target_migrations else "Target"

    report = analyze_drift(base_graph, target_graph, base_label=base_label, target_label=target_label)
    fmt = (format or "text").lower()
    write_output(report.to_json() if fmt == "json" else report.to_text(), out)

    if generate_migration and not report.is_clean:
        if next_version:
            version = next_version
        else:
            from ..analysis.ordering import parse_migration_filename
            versions = []
            for file_dict in target_files:
                parsed = parse_migration_filename(file_dict["filename"])
                if parsed and parsed["version"]:
                    try:
                        versions.append(int(parsed["version"].split(".")[0]))
                    except (ValueError, AttributeError):
                        pass
            version = str(max(versions) + 1) if versions else "1"

        migration_content = generate_repair_migration(report, version, description)
        migration_path = Path(target_migrations) / f"V{version}__{description}.sql"
        migration_path.write_text(migration_content, encoding="utf-8")
        print(f"\n✓ Generated {migration_path}", file=sys.stderr)

    if report.is_clean:
        print("  No drift detected", file=sys.stderr)
    else:
        print(f"  {report.total_drift_count} drift finding(s)", file=sys.stderr)
        print(f"  {len(report.errors())} error(s), {len(report.warnings())} warning(s)", file=sys.stderr)

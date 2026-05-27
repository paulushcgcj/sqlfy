"""Migration naming convention enforcement (Feature #23).

Provides a small, configurable validator that enforces filename/description
patterns and filename length constraints. Returns the same ValidationReport
structure used by `analysis.ordering` so output and exit-code behavior is
consistent with other CLI validators.
"""

from __future__ import annotations

import re
from pathlib import Path

from .ordering import parse_migration_filename, ValidationIssue, ValidationReport


def validate_naming(
    migrations_dir: Path,
    pattern: str = r"^[a-z0-9_]+$",
    max_length: int = 120,
) -> ValidationReport:
    """Validate migration filename naming conventions.

    Args:
        migrations_dir: Path to directory containing `.sql` files.
        pattern: Regex applied to the migration *description* (default: lower-case, digits, underscores).
        max_length: Maximum allowed filename length in characters.

    Returns:
        ValidationReport with zero or more ValidationIssue entries.
    """
    sql_files = sorted(f for f in migrations_dir.rglob("*") if f.is_file() and f.suffix.lower() == ".sql")
    issues: list[ValidationIssue] = []

    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid --pattern regex: {exc}") from exc

    for f in sql_files:
        name = f.name
        parsed = parse_migration_filename(name)

        # If parsing failed, report (ordering.validate_migrations also reports this).
        if parsed is None:
            issues.append(ValidationIssue(
                severity="warning",
                code="INVALID_FILENAME",
                message="Non-standard migration filename (not Flyway format)",
                filename=name,
                suggestion="Use Flyway format: V<version>__<description>.sql",
            ))
            # Skip further naming checks for an unparseable filename
            continue

        description = parsed.get("description") or ""

        # Filename length
        if len(name) > max_length:
            issues.append(ValidationIssue(
                severity="warning",
                code="LONG_FILENAME",
                message=f"Filename exceeds {max_length} characters",
                filename=name,
                suggestion="Shorten the filename description or use abbreviations",
            ))

        # Description pattern
        # The parser returns the raw description (underscores preserved); match against that.
        if not compiled.match(description):
            issues.append(ValidationIssue(
                severity="warning",
                code="DESC_FORMAT",
                message=f"Description does not match required pattern: {pattern}",
                filename=name,
                suggestion="Use lower-case letters, digits and underscores (no spaces or hyphens)",
            ))

        # Leading/trailing underscore is usually accidental
        if description.startswith("_") or description.endswith("_"):
            issues.append(ValidationIssue(
                severity="warning",
                code="DESC_UNDERSCORE",
                message="Description has leading or trailing underscore",
                filename=name,
            ))

    return ValidationReport(total_migrations=len(sql_files), issues=issues)


def format_text(report: ValidationReport) -> str:
    lines: list[str] = []
    a = lines.append
    a("\n╔════════════════════════════════════════╗")
    a("║    MIGRATION NAMING VALIDATION        ║")
    a("╚════════════════════════════════════════╝\n")
    a(f"Total migrations: {report.total_migrations}")
    a("")

    if report.issues:
        a(f"⚠  {len(report.issues)} naming issue(s):\n")
        for issue in report.issues:
            a(f"  [{issue.code}] {issue.message}")
            if issue.filename:
                a(f"    File: {issue.filename}")
            if issue.suggestion:
                a(f"    → {issue.suggestion}")
            a("")
    else:
        a("✓ All filenames satisfy the naming rules")
        a("")

    return "\n".join(lines)


def format_json(report: ValidationReport) -> str:
    import json

    data = {
        "total_migrations": report.total_migrations,
        "issue_count": len(report.issues),
        "issues": [
            {
                "severity": i.severity,
                "code": i.code,
                "message": i.message,
                "filename": i.filename,
                "suggestion": i.suggestion,
            }
            for i in report.issues
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def validate_naming_files(
    files: list[dict],
    pattern: str = r"^[a-z0-9_]+$",
    max_length: int = 120,
) -> ValidationReport:
    """Validate naming rules for an in-memory list of files (as returned by `load_files`)."""
    issues: list[ValidationIssue] = []
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid --pattern regex: {exc}") from exc

    for entry in files:
        raw = entry.get("filename", "")
        # load_files stores relative paths; parse_migration_filename needs the bare name
        name = Path(raw).name
        parsed = parse_migration_filename(name)

        if parsed is None:
            issues.append(ValidationIssue(
                severity="warning",
                code="INVALID_FILENAME",
                message="Non-standard migration filename (not Flyway format)",
                filename=name,
                suggestion="Use Flyway format: V<version>__<description>.sql",
            ))
            continue

        description = parsed.get("description") or ""

        if len(name) > max_length:
            issues.append(ValidationIssue(
                severity="warning",
                code="LONG_FILENAME",
                message=f"Filename exceeds {max_length} characters",
                filename=name,
            ))

        if not compiled.match(description):
            issues.append(ValidationIssue(
                severity="warning",
                code="DESC_FORMAT",
                message=f"Description does not match required pattern: {pattern}",
                filename=name,
            ))

        if description.startswith("_") or description.endswith("_"):
            issues.append(ValidationIssue(
                severity="warning",
                code="DESC_UNDERSCORE",
                message="Description has leading or trailing underscore",
                filename=name,
            ))

    return ValidationReport(total_migrations=len(files), issues=issues)

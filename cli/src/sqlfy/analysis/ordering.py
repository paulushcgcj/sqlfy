"""
ordering.py
===========
Migration ordering validation.

Detects:
- Out-of-order migrations
- Version gaps
- Duplicate versions
- Invalid filename formats

Adapted from Feature #12 specification.
"""

import re
from pathlib import Path
from dataclasses import dataclass
from typing import Literal


@dataclass
class ValidationIssue:
    """A single validation issue (error, warning, or info)."""
    severity: Literal["error", "warning", "info"]
    code: str
    message: str
    filename: str | None = None
    version: str | None = None
    suggestion: str | None = None


@dataclass
class ValidationReport:
    """Complete validation report for a migration folder."""
    total_migrations: int
    issues: list[ValidationIssue]
    
    @property
    def errors(self) -> list[ValidationIssue]:
        """Return only error-severity issues."""
        return [i for i in self.issues if i.severity == "error"]
    
    @property
    def warnings(self) -> list[ValidationIssue]:
        """Return only warning-severity issues."""
        return [i for i in self.issues if i.severity == "warning"]
    
    @property
    def has_errors(self) -> bool:
        """Return True if any errors exist."""
        return len(self.errors) > 0
    
    @property
    def has_warnings(self) -> bool:
        """Return True if any warnings exist."""
        return len(self.warnings) > 0


def parse_migration_filename(filename: str) -> dict | None:
    """
    Parse Flyway migration filename.
    
    Supports formats:
    - V1__description.sql (simple versioned)
    - V1.2__description.sql (dotted version)
    - V1_2__description.sql (underscore version, converted to dots)
    - R__repeatable.sql (repeatable migration)
    - U1__undo.sql (undo migration)
    
    Args:
        filename: Migration filename (e.g., "V1__create_users.sql")
    
    Returns:
        Dict with parsed metadata, or None if not a valid Flyway filename.
    """
    # Versioned migration: V<version>__<description>.sql
    match = re.match(r'^V(\d+(?:[._]\d+)*)__(.+)\.sql$', filename, re.IGNORECASE)
    if match:
        version_str = match.group(1).replace('_', '.')
        description = match.group(2)
        return {
            "type": "versioned",
            "version": version_str,
            "version_numeric": _parse_version_numeric(version_str),
            "description": description,
        }
    
    # Repeatable migration: R__<description>.sql
    match = re.match(r'^R__(.+)\.sql$', filename, re.IGNORECASE)
    if match:
        return {
            "type": "repeatable",
            "version": None,
            "version_numeric": None,
            "description": match.group(1),
        }
    
    # Undo migration: U<version>__<description>.sql
    match = re.match(r'^U(\d+(?:[._]\d+)*)__(.+)\.sql$', filename, re.IGNORECASE)
    if match:
        version_str = match.group(1).replace('_', '.')
        return {
            "type": "undo",
            "version": version_str,
            "version_numeric": _parse_version_numeric(version_str),
            "description": match.group(2),
        }
    
    return None


def _parse_version_numeric(version_str: str) -> tuple[int, ...]:
    """
    Parse version string to tuple of integers for comparison.
    
    Examples:
    - "1" -> (1,)
    - "1.2" -> (1, 2)
    - "1.2.3" -> (1, 2, 3)
    
    Args:
        version_str: Version string (e.g., "1.2.3")
    
    Returns:
        Tuple of integers for comparison.
    """
    return tuple(int(p) for p in version_str.split('.'))


def validate_migrations(migrations_dir: Path) -> ValidationReport:
    """
    Validate migration folder structure and ordering.
    
    Checks:
    - Filename format (Flyway standard)
    - Duplicate versions
    - Version gaps (for simple integer sequences)
    - Out-of-order migrations (filename sort != version sort)
    
    Args:
        migrations_dir: Path to directory containing migration files.
    
    Returns:
        ValidationReport with all detected issues.
    """
    sql_files = sorted(
        f for f in migrations_dir.iterdir() 
        if f.is_file() and f.suffix.lower() == '.sql'
    )
    
    issues: list[ValidationIssue] = []
    
    # Parse all filenames
    parsed = []
    for f in sql_files:
        p = parse_migration_filename(f.name)
        if p is None:
            issues.append(ValidationIssue(
                severity="warning",
                code="INVALID_FILENAME",
                message=f"Non-standard migration filename (not Flyway format)",
                filename=f.name,
                suggestion="Use Flyway format: V<version>__<description>.sql",
            ))
        else:
            parsed.append({"file": f, **p})
    
    # Separate by type
    versioned = [p for p in parsed if p["type"] == "versioned"]
    
    # Check for duplicate versions
    version_map: dict[tuple, list] = {}
    for m in versioned:
        v = m["version_numeric"]
        version_map.setdefault(v, []).append(m)
    
    for v, migrations in version_map.items():
        if len(migrations) > 1:
            filenames = [m["file"].name for m in migrations]
            issues.append(ValidationIssue(
                severity="error",
                code="DUPLICATE_VERSION",
                message=f"Duplicate version {migrations[0]['version']} found in {len(migrations)} files",
                version=migrations[0]['version'],
                suggestion=f"Rename one of: {', '.join(filenames)}",
            ))
    
    # Check for version gaps (only for simple integer versions)
    if versioned:
        versions = sorted([m["version_numeric"] for m in versioned])
        
        # For simple integer versions (1, 2, 3), detect gaps
        if all(len(v) == 1 for v in versions):
            nums = [v[0] for v in versions]
            for i in range(len(nums) - 1):
                if nums[i + 1] - nums[i] > 1:
                    missing = list(range(nums[i] + 1, nums[i + 1]))
                    issues.append(ValidationIssue(
                        severity="warning",
                        code="VERSION_GAP",
                        message=f"Gap in version sequence: V{nums[i]} → V{nums[i + 1]}",
                        suggestion=f"Missing versions: V{', V'.join(map(str, missing))}",
                    ))
    
    # Check for out-of-order migrations (filename sort vs version sort)
    if len(versioned) > 1:
        versioned_sorted_by_name = sorted(versioned, key=lambda m: m["file"].name)
        versioned_sorted_by_version = sorted(versioned, key=lambda m: m["version_numeric"])
        
        # Compare file order
        files_by_name = [m["file"].name for m in versioned_sorted_by_name]
        files_by_version = [m["file"].name for m in versioned_sorted_by_version]
        
        if files_by_name != files_by_version:
            # Find the first out-of-order file
            for i, (name, ver_name) in enumerate(zip(files_by_name, files_by_version)):
                if name != ver_name:
                    issues.append(ValidationIssue(
                        severity="error",
                        code="OUT_OF_ORDER",
                        message=f"Migrations are not in version order by filename",
                        filename=name,
                        suggestion=f"Expected {ver_name} at position {i+1}, found {name}",
                    ))
                    break
    
    # Sort issues by severity (errors first, then warnings, then info)
    issues_sorted = sorted(
        issues, 
        key=lambda i: (("error", "warning", "info").index(i.severity), i.code)
    )
    
    return ValidationReport(
        total_migrations=len(sql_files),
        issues=issues_sorted,
    )


def suggest_renumbering(migrations_dir: Path) -> list[dict]:
    """
    Suggest a renumbering scheme to fix ordering issues.
    
    Generates sequential numbering (V1, V2, V3...) based on version order.
    
    Args:
        migrations_dir: Path to directory containing migration files.
    
    Returns:
        List of dicts with old and new filenames.
    """
    sql_files = sorted(
        f for f in migrations_dir.iterdir() 
        if f.is_file() and f.suffix.lower() == '.sql'
    )
    
    parsed = []
    for f in sql_files:
        p = parse_migration_filename(f.name)
        if p and p["type"] == "versioned":
            parsed.append({"file": f, **p})
    
    # Sort by version_numeric
    parsed_sorted = sorted(parsed, key=lambda m: m["version_numeric"])
    
    # Suggest sequential numbering
    suggestions = []
    for i, m in enumerate(parsed_sorted, start=1):
        old_name = m["file"].name
        new_name = f"V{i}__{m['description']}.sql"
        
        if old_name != new_name:
            suggestions.append({
                "old": old_name,
                "new": new_name,
                "version_old": m["version"],
                "version_new": str(i),
            })
    
    return suggestions


# ─────────────────────────────────────────────
# FORMATTERS
# ─────────────────────────────────────────────

def format_text(report: ValidationReport, show_suggestions: bool = False) -> str:
    """Format validation report as human-readable text."""
    lines = []
    a = lines.append
    
    a('\n╔══════════════════════════════════════════╗')
    a('║   MIGRATION ORDERING VALIDATION          ║')
    a('╚══════════════════════════════════════════╝\n')
    
    a(f'Total migrations: {report.total_migrations}')
    a('')
    
    # Errors
    if report.errors:
        a(f'❌ {len(report.errors)} error(s):\n')
        for issue in report.errors:
            a(f'  [{issue.code}] {issue.message}')
            if issue.filename:
                a(f'    File: {issue.filename}')
            if issue.version:
                a(f'    Version: {issue.version}')
            if show_suggestions and issue.suggestion:
                a(f'    → {issue.suggestion}')
            a('')
    
    # Warnings
    if report.warnings:
        a(f'⚠  {len(report.warnings)} warning(s):\n')
        for issue in report.warnings:
            a(f'  [{issue.code}] {issue.message}')
            if issue.filename:
                a(f'    File: {issue.filename}')
            if show_suggestions and issue.suggestion:
                a(f'    → {issue.suggestion}')
            a('')
    
    # Success
    if not report.has_errors and not report.has_warnings:
        a('✓ All migrations validated successfully')
        a('')
    
    return '\n'.join(lines)


def format_json(report: ValidationReport) -> str:
    """Format validation report as JSON."""
    import json
    
    data = {
        'total_migrations': report.total_migrations,
        'has_errors': report.has_errors,
        'has_warnings': report.has_warnings,
        'error_count': len(report.errors),
        'warning_count': len(report.warnings),
        'issues': [
            {
                'severity': i.severity,
                'code': i.code,
                'message': i.message,
                'filename': i.filename,
                'version': i.version,
                'suggestion': i.suggestion,
            }
            for i in report.issues
        ],
    }
    
    return json.dumps(data, indent=2, ensure_ascii=False)

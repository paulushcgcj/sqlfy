"""
sqlfy.analysis.linter
~~~~~~~~~~~~~~~~~~~~~

SQL quality and linting integration with sqlfluff.

Feature #38: Migration SQL Quality & Linting
"""

from dataclasses import dataclass, field
from typing import Literal
from pathlib import Path
import json

# Try importing sqlfluff - it's optional dependency
try:
    from sqlfluff.core import Linter
    from sqlfluff.core.config import FluffConfig
    SQLFLUFF_AVAILABLE = True
except ImportError:
    SQLFLUFF_AVAILABLE = False


@dataclass
class LintViolation:
    """A single linting rule violation."""
    rule_code: str          # L010, L031, etc.
    message: str
    line: int
    column: int
    severity: Literal['error', 'warning', 'info']
    fixable: bool


@dataclass
class LintResult:
    """Result of linting a single migration file."""
    filename: str
    score: int              # 0-100
    violations: list[LintViolation] = field(default_factory=list)
    dialect: str = 'oracle'
    rules_applied: int = 0
    error: str | None = None  # Error message if linting failed


def _check_sqlfluff() -> None:
    """Raise ValueError if sqlfluff is not installed."""
    if not SQLFLUFF_AVAILABLE:
        raise ValueError(
            "sqlfluff is not installed. Install with: pip install sqlfluff>=3.0.0"
        )


def lint_migration(
    sql: str,
    filename: str,
    dialect: str = 'oracle',
    config_path: str | None = None,
) -> LintResult:
    """
    Lint a single migration SQL file.
    
    Args:
        sql: SQL content to lint
        filename: Name of the file (for reporting)
        dialect: SQL dialect (oracle, postgres, mysql, sqlite)
        config_path: Path to .sqlfluff config file (optional)
    
    Returns:
        LintResult with score, violations, and metadata
    
    Raises:
        ValueError: If sqlfluff is not installed
    """
    _check_sqlfluff()
    
    try:
        # Configure sqlfluff
        config_kwargs = {
            'dialect': dialect,
            'exclude_rules': [],  # Can be customized via config file
        }
        
        if config_path:
            config = FluffConfig.from_path(config_path, overrides=config_kwargs)
        else:
            # Use default config with basic overrides
            config = FluffConfig.from_kwargs(config_kwargs)
        
        # Create linter and lint the SQL
        linter = Linter(config=config)
        result = linter.lint_string(sql, fname=filename)
        
        # Extract violations
        violations: list[LintViolation] = []
        for violation in result.violations:
            violations.append(LintViolation(
                rule_code=violation.rule_code(),
                message=violation.description,
                line=violation.line_no,
                column=violation.line_pos,
                severity='error' if violation.rule.code.startswith('PRS') else 'warning',
                fixable=violation.fixable,
            ))
        
        # Calculate score
        score = calculate_score(violations)
        
        # Count rules applied (approximate - sqlfluff has 200+ rules by default)
        rules_applied = len(config.get_section('rules') or {})
        if rules_applied == 0:
            rules_applied = 50  # Rough estimate of default rules
        
        return LintResult(
            filename=filename,
            score=score,
            violations=violations,
            dialect=dialect,
            rules_applied=rules_applied,
        )
    
    except Exception as e:
        # Return error result if linting fails
        return LintResult(
            filename=filename,
            score=0,
            violations=[],
            dialect=dialect,
            error=str(e),
        )


def lint_directory(
    path: str,
    min_score: int = 0,
    recursive: bool = True,
    dialect: str = 'oracle',
    config_path: str | None = None,
) -> list[LintResult]:
    """
    Lint all SQL files in a directory.
    
    Args:
        path: Directory path
        min_score: Minimum acceptable score (0-100)
        recursive: Recursively scan subdirectories
        dialect: SQL dialect
        config_path: Path to .sqlfluff config file
    
    Returns:
        List of LintResult objects, one per file
    
    Raises:
        ValueError: If sqlfluff is not installed
    """
    _check_sqlfluff()
    
    directory = Path(path)
    if not directory.is_dir():
        raise ValueError(f"Not a directory: {path}")
    
    # Find all SQL files
    if recursive:
        sql_files = list(directory.rglob("*.sql"))
    else:
        sql_files = list(directory.glob("*.sql"))
    
    # Lint each file
    results: list[LintResult] = []
    for sql_file in sorted(sql_files):
        try:
            sql_content = sql_file.read_text(encoding='utf-8')
            result = lint_migration(
                sql_content,
                sql_file.name,
                dialect=dialect,
                config_path=config_path,
            )
            results.append(result)
        except Exception as e:
            # Add error result if file read fails
            results.append(LintResult(
                filename=sql_file.name,
                score=0,
                violations=[],
                dialect=dialect,
                error=f"Failed to read file: {e}",
            ))
    
    return results


def calculate_score(violations: list[LintViolation]) -> int:
    """
    Calculate quality score from violations.
    
    Scoring algorithm:
      - Start with 100
      - Subtract 10 per error
      - Subtract 5 per warning
      - Subtract 1 per info
      - Min score is 0
    
    Args:
        violations: List of violations
    
    Returns:
        Score (0-100)
    """
    score = 100
    
    for violation in violations:
        if violation.severity == 'error':
            score -= 10
        elif violation.severity == 'warning':
            score -= 5
        elif violation.severity == 'info':
            score -= 1
    
    return max(0, score)


# ─────────────────────────────────────────────
# Output Formatters
# ─────────────────────────────────────────────

def format_text(result: LintResult) -> str:
    """Format lint result as human-readable text."""
    lines: list[str] = []
    a = lines.append
    
    a(f"\nLinting: {result.filename}")
    a("=" * 60)
    
    if result.error:
        a(f"\n✗ Error: {result.error}")
        a(f"\nScore: {result.score}/100")
        return "\n".join(lines)
    
    if not result.violations:
        a("\n✓ No violations found")
        a(f"\nScore: {result.score}/100 (perfect!)")
        return "\n".join(lines)
    
    # Group violations by severity
    errors = [v for v in result.violations if v.severity == 'error']
    warnings = [v for v in result.violations if v.severity == 'warning']
    infos = [v for v in result.violations if v.severity == 'info']
    
    if errors:
        a(f"\n✗ Errors ({len(errors)}):")
        for v in errors:
            fixable = " [fixable]" if v.fixable else ""
            a(f"  {v.rule_code} | Line {v.line}, Col {v.column}: {v.message}{fixable}")
    
    if warnings:
        a(f"\n⚠ Warnings ({len(warnings)}):")
        for v in warnings:
            fixable = " [fixable]" if v.fixable else ""
            a(f"  {v.rule_code} | Line {v.line}, Col {v.column}: {v.message}{fixable}")
    
    if infos:
        a(f"\nℹ Info ({len(infos)}):")
        for v in infos:
            fixable = " [fixable]" if v.fixable else ""
            a(f"  {v.rule_code} | Line {v.line}, Col {v.column}: {v.message}{fixable}")
    
    a(f"\nScore: {result.score}/100")
    a(f"Dialect: {result.dialect}")
    a(f"Rules applied: {result.rules_applied}")
    
    return "\n".join(lines)


def format_json(result: LintResult) -> str:
    """Format lint result as JSON."""
    data = {
        'filename': result.filename,
        'score': result.score,
        'violations': [
            {
                'rule_code': v.rule_code,
                'message': v.message,
                'line': v.line,
                'column': v.column,
                'severity': v.severity,
                'fixable': v.fixable,
            }
            for v in result.violations
        ],
        'dialect': result.dialect,
        'rules_applied': result.rules_applied,
    }
    
    if result.error:
        data['error'] = result.error
    
    return json.dumps(data, indent=2, ensure_ascii=False)


def format_directory_text(results: list[LintResult]) -> str:
    """Format multiple lint results as summary report."""
    lines: list[str] = []
    a = lines.append
    
    a("\n╔══════════════════════════════════════════════════════╗")
    a("║         SQL Migration Linting Report                ║")
    a("╚══════════════════════════════════════════════════════╝\n")
    
    # Summary stats
    total = len(results)
    passed = sum(1 for r in results if r.score >= 80)
    failed = sum(1 for r in results if r.score < 80)
    avg_score = sum(r.score for r in results) / total if total > 0 else 0
    
    a(f"  Total files: {total}")
    a(f"  Passed (≥80): {passed}")
    a(f"  Failed (<80): {failed}")
    a(f"  Average score: {avg_score:.1f}/100\n")
    
    # Individual file results
    a("  File Results:")
    a("  " + "-" * 54)
    
    for result in sorted(results, key=lambda r: r.score):
        status = "✓" if result.score >= 80 else "✗"
        error_count = sum(1 for v in result.violations if v.severity == 'error')
        warning_count = sum(1 for v in result.violations if v.severity == 'warning')
        
        if result.error:
            a(f"  ✗ {result.filename:<40} ERROR")
        else:
            violations_str = f"({error_count}E, {warning_count}W)" if result.violations else ""
            a(f"  {status} {result.filename:<40} {result.score:>3}/100  {violations_str}")
    
    a("")
    return "\n".join(lines)


def format_directory_json(results: list[LintResult]) -> str:
    """Format multiple lint results as JSON array."""
    data = [
        {
            'filename': r.filename,
            'score': r.score,
            'violations': [
                {
                    'rule_code': v.rule_code,
                    'message': v.message,
                    'line': v.line,
                    'column': v.column,
                    'severity': v.severity,
                    'fixable': v.fixable,
                }
                for v in r.violations
            ],
            'dialect': r.dialect,
            'rules_applied': r.rules_applied,
            'error': r.error,
        }
        for r in results
    ]
    
    return json.dumps(data, indent=2, ensure_ascii=False)

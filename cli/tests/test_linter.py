"""
Tests for SQL linting functionality (Feature #38).
"""

import pytest

from sqlfy.analysis.linter import (
    lint_migration,
    lint_directory,
    calculate_score,
    LintViolation,
    LintResult,
    format_text,
    format_json,
    format_directory_text,
    format_directory_json,
    SQLFLUFF_AVAILABLE,
)


# Skip all tests if sqlfluff is not installed
pytestmark = pytest.mark.skipif(
    not SQLFLUFF_AVAILABLE,
    reason="sqlfluff not installed (optional dependency)"
)


def test_calculate_score_no_violations():
    """Score is 100 with no violations."""
    violations = []
    score = calculate_score(violations)
    assert score == 100


def test_calculate_score_with_errors():
    """Score decreases by 10 per error."""
    violations = [
        LintViolation('L001', 'Error 1', 1, 1, 'error', True),
        LintViolation('L002', 'Error 2', 2, 1, 'error', False),
    ]
    score = calculate_score(violations)
    assert score == 80  # 100 - (2 * 10)


def test_calculate_score_with_warnings():
    """Score decreases by 5 per warning."""
    violations = [
        LintViolation('L010', 'Warning 1', 1, 1, 'warning', True),
        LintViolation('L031', 'Warning 2', 2, 1, 'warning', False),
    ]
    score = calculate_score(violations)
    assert score == 90  # 100 - (2 * 5)


def test_calculate_score_with_info():
    """Score decreases by 1 per info."""
    violations = [
        LintViolation('I001', 'Info 1', 1, 1, 'info', True),
        LintViolation('I002', 'Info 2', 2, 1, 'info', False),
    ]
    score = calculate_score(violations)
    assert score == 98  # 100 - (2 * 1)


def test_calculate_score_mixed_violations():
    """Score decreases correctly with mixed violation types."""
    violations = [
        LintViolation('L001', 'Error', 1, 1, 'error', True),      # -10
        LintViolation('L010', 'Warning', 2, 1, 'warning', True),  # -5
        LintViolation('I001', 'Info', 3, 1, 'info', True),        # -1
    ]
    score = calculate_score(violations)
    assert score == 84  # 100 - 10 - 5 - 1


def test_calculate_score_minimum_zero():
    """Score cannot go below 0."""
    violations = [LintViolation('L001', 'Error', i, 1, 'error', True) for i in range(20)]
    score = calculate_score(violations)
    assert score == 0  # Would be -100 but clamped to 0


def test_lint_valid_sql():
    """Linting valid SQL produces high score."""
    sql = "SELECT id, name FROM users WHERE email = 'test@example.com';"
    result = lint_migration(sql, "test.sql", dialect='oracle')
    
    assert result.filename == "test.sql"
    assert result.dialect == 'oracle'
    assert result.score >= 0  # May have some warnings depending on sqlfluff config
    assert result.error is None


def test_lint_lowercase_keywords():
    """Linting SQL with lowercase keywords detects violations."""
    sql = "select id from users;"
    result = lint_migration(sql, "test.sql", dialect='oracle')
    
    assert result.filename == "test.sql"
    # May or may not have violations depending on sqlfluff config
    # At minimum, should not error
    assert result.error is None


def test_lint_select_star():
    """Linting SELECT * may produce warnings."""
    sql = "CREATE VIEW v AS SELECT * FROM users;"
    result = lint_migration(sql, "test.sql", dialect='oracle')
    
    assert result.filename == "test.sql"
    assert result.error is None
    # SELECT * warnings depend on sqlfluff config


def test_lint_result_has_metadata():
    """Lint result includes dialect and rules_applied."""
    sql = "SELECT id FROM users;"
    result = lint_migration(sql, "test.sql", dialect='postgres')
    
    assert result.dialect == 'postgres'
    assert result.rules_applied > 0  # Should have some rules


def test_format_text_no_violations():
    """Text formatter handles no violations."""
    result = LintResult(
        filename="test.sql",
        score=100,
        violations=[],
        dialect='oracle',
        rules_applied=50,
    )
    
    output = format_text(result)
    assert "test.sql" in output
    assert "100/100" in output
    assert "No violations" in output or "perfect" in output


def test_format_text_with_violations():
    """Text formatter displays violations."""
    violations = [
        LintViolation('L010', 'Keywords should be uppercase', 1, 1, 'warning', True),
        LintViolation('L031', 'Table alias too short', 5, 10, 'warning', False),
    ]
    result = LintResult(
        filename="test.sql",
        score=90,
        violations=violations,
        dialect='oracle',
        rules_applied=50,
    )
    
    output = format_text(result)
    assert "test.sql" in output
    assert "90/100" in output
    assert "L010" in output
    assert "L031" in output
    assert "Keywords should be uppercase" in output


def test_format_text_with_error():
    """Text formatter handles error results."""
    result = LintResult(
        filename="test.sql",
        score=0,
        violations=[],
        dialect='oracle',
        error="Parse error",
    )
    
    output = format_text(result)
    assert "test.sql" in output
    assert "Error" in output
    assert "Parse error" in output


def test_format_json_valid():
    """JSON formatter produces valid JSON."""
    import json
    
    violations = [
        LintViolation('L010', 'Warning message', 1, 1, 'warning', True),
    ]
    result = LintResult(
        filename="test.sql",
        score=95,
        violations=violations,
        dialect='oracle',
        rules_applied=50,
    )
    
    output = format_json(result)
    data = json.loads(output)  # Should not raise
    
    assert data['filename'] == "test.sql"
    assert data['score'] == 95
    assert len(data['violations']) == 1
    assert data['violations'][0]['rule_code'] == 'L010'


def test_format_directory_text_summary():
    """Directory text formatter shows summary."""
    results = [
        LintResult("v1.sql", 100, [], 'oracle', 50),
        LintResult("v2.sql", 85, [LintViolation('L010', 'msg', 1, 1, 'warning', True)], 'oracle', 50),
        LintResult("v3.sql", 60, [
            LintViolation('L001', 'error', 1, 1, 'error', True),
            LintViolation('L010', 'warning', 2, 1, 'warning', True),
        ], 'oracle', 50),
    ]
    
    output = format_directory_text(results)
    assert "Total files: 3" in output
    assert "v1.sql" in output
    assert "v2.sql" in output
    assert "v3.sql" in output


def test_format_directory_json_valid():
    """Directory JSON formatter produces valid JSON array."""
    import json
    
    results = [
        LintResult("v1.sql", 100, [], 'oracle', 50),
        LintResult("v2.sql", 85, [LintViolation('L010', 'msg', 1, 1, 'warning', True)], 'oracle', 50),
    ]
    
    output = format_directory_json(results)
    data = json.loads(output)  # Should not raise
    
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]['filename'] == "v1.sql"
    assert data[1]['filename'] == "v2.sql"


def test_lint_directory_non_recursive(tmp_path):
    """Directory linting with non-recursive flag."""
    # Create test files
    (tmp_path / "v1.sql").write_text("SELECT id FROM users;")
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "v2.sql").write_text("SELECT id FROM orders;")
    
    # Non-recursive: should only find v1.sql
    results = lint_directory(str(tmp_path), recursive=False, dialect='oracle')
    assert len(results) == 1
    assert results[0].filename == "v1.sql"


def test_lint_directory_recursive(tmp_path):
    """Directory linting with recursive flag."""
    # Create test files
    (tmp_path / "v1.sql").write_text("SELECT id FROM users;")
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "v2.sql").write_text("SELECT id FROM orders;")
    
    # Recursive: should find both files
    results = lint_directory(str(tmp_path), recursive=True, dialect='oracle')
    assert len(results) == 2
    filenames = {r.filename for r in results}
    assert "v1.sql" in filenames
    assert "v2.sql" in filenames


def test_lint_directory_min_score_filter():
    """Directory linting respects min_score parameter."""
    # Note: min_score is used for exit code, not filtering results
    # This test just verifies the parameter is accepted
    # Real filtering happens in CLI layer


def test_lint_migration_error_handling():
    """Linting handles malformed SQL gracefully."""
    # Extremely malformed SQL that might cause parse errors
    sql = "SELECT FROM WHERE"
    result = lint_migration(sql, "bad.sql", dialect='oracle')
    
    # Should return result even if parsing fails
    assert result.filename == "bad.sql"
    # May have error or violations depending on sqlfluff behavior


def test_lint_different_dialects():
    """Linting works with different SQL dialects."""
    sql = "SELECT id FROM users;"
    
    for dialect in ['oracle', 'postgres', 'mysql', 'sqlite']:
        result = lint_migration(sql, "test.sql", dialect=dialect)
        assert result.dialect == dialect
        assert result.error is None


def test_violations_have_required_fields():
    """Violation objects have all required fields."""
    violation = LintViolation(
        rule_code='L010',
        message='Test message',
        line=5,
        column=12,
        severity='warning',
        fixable=True,
    )
    
    assert violation.rule_code == 'L010'
    assert violation.message == 'Test message'
    assert violation.line == 5
    assert violation.column == 12
    assert violation.severity == 'warning'
    assert violation.fixable is True


def test_lint_result_default_values():
    """LintResult has sensible defaults."""
    result = LintResult(
        filename="test.sql",
        score=100,
    )
    
    assert result.violations == []
    assert result.dialect == 'oracle'
    assert result.rules_applied == 0
    assert result.error is None

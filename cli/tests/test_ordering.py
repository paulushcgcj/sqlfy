"""
test_ordering.py
================
Test migration ordering validation.
"""

import tempfile
from pathlib import Path

import pytest

from sqlfy.analysis.ordering import (
    parse_migration_filename,
    validate_migrations,
    suggest_renumbering,
    format_text,
    format_json,
)


# ─────────────────────────────────────────────
# FILENAME PARSING TESTS
# ─────────────────────────────────────────────

def test_parse_versioned_migration():
    """Test Flyway versioned migration filename parsing."""
    p = parse_migration_filename("V1__create_tables.sql")
    assert p is not None
    assert p["type"] == "versioned"
    assert p["version"] == "1"
    assert p["version_numeric"] == (1,)
    assert p["description"] == "create_tables"


def test_parse_dotted_version():
    """Test dotted version numbers."""
    p = parse_migration_filename("V1.2.3__update.sql")
    assert p is not None
    assert p["type"] == "versioned"
    assert p["version"] == "1.2.3"
    assert p["version_numeric"] == (1, 2, 3)
    assert p["description"] == "update"


def test_parse_underscore_version():
    """Test underscore version numbers (converted to dots)."""
    p = parse_migration_filename("V1_2_3__update.sql")
    assert p is not None
    assert p["version"] == "1.2.3"
    assert p["version_numeric"] == (1, 2, 3)


def test_parse_repeatable_migration():
    """Test repeatable migration parsing."""
    p = parse_migration_filename("R__seed_data.sql")
    assert p is not None
    assert p["type"] == "repeatable"
    assert p["version"] is None
    assert p["version_numeric"] is None
    assert p["description"] == "seed_data"


def test_parse_undo_migration():
    """Test undo migration parsing."""
    p = parse_migration_filename("U1__undo_tables.sql")
    assert p is not None
    assert p["type"] == "undo"
    assert p["version"] == "1"
    assert p["version_numeric"] == (1,)
    assert p["description"] == "undo_tables"


def test_parse_invalid_filename():
    """Test invalid filename returns None."""
    assert parse_migration_filename("not_a_migration.sql") is None
    assert parse_migration_filename("V__missing_version.sql") is None
    assert parse_migration_filename("V1_missing_separator.sql") is None


def test_parse_case_insensitive():
    """Test case-insensitive parsing."""
    p1 = parse_migration_filename("V1__test.sql")
    p2 = parse_migration_filename("v1__test.sql")
    assert p1 == p2


# ─────────────────────────────────────────────
# VALIDATION TESTS
# ─────────────────────────────────────────────

def test_validate_empty_directory():
    """Test validation with no migration files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        migrations_dir = Path(tmpdir)
        report = validate_migrations(migrations_dir)
        
        assert report.total_migrations == 0
        assert len(report.issues) == 0
        assert not report.has_errors
        assert not report.has_warnings


def test_validate_single_migration():
    """Test validation with a single migration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        migrations_dir = Path(tmpdir)
        (migrations_dir / "V1__initial.sql").write_text("SELECT 1")
        
        report = validate_migrations(migrations_dir)
        
        assert report.total_migrations == 1
        assert len(report.issues) == 0


def test_validate_multiple_migrations_correct_order():
    """Test validation with correctly ordered migrations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        migrations_dir = Path(tmpdir)
        (migrations_dir / "V1__first.sql").write_text("SELECT 1")
        (migrations_dir / "V2__second.sql").write_text("SELECT 2")
        (migrations_dir / "V3__third.sql").write_text("SELECT 3")
        
        report = validate_migrations(migrations_dir)
        
        assert report.total_migrations == 3
        assert len(report.issues) == 0


def test_detect_duplicate_versions():
    """Test detection of duplicate version numbers."""
    with tempfile.TemporaryDirectory() as tmpdir:
        migrations_dir = Path(tmpdir)
        (migrations_dir / "V1__first.sql").write_text("SELECT 1")
        (migrations_dir / "V1__duplicate.sql").write_text("SELECT 1")
        
        report = validate_migrations(migrations_dir)
        
        assert report.has_errors
        error = next(i for i in report.errors if i.code == "DUPLICATE_VERSION")
        assert error.version == "1"
        assert "2 files" in error.message


def test_detect_version_gaps():
    """Test detection of gaps in version sequence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        migrations_dir = Path(tmpdir)
        (migrations_dir / "V1__first.sql").write_text("SELECT 1")
        (migrations_dir / "V2__second.sql").write_text("SELECT 2")
        (migrations_dir / "V5__fifth.sql").write_text("SELECT 5")
        
        report = validate_migrations(migrations_dir)
        
        assert report.has_warnings
        warning = next(i for i in report.warnings if i.code == "VERSION_GAP")
        assert "V2 → V5" in warning.message
        assert "V3, V4" in warning.suggestion


def test_detect_out_of_order():
    """Test detection of out-of-order migrations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        migrations_dir = Path(tmpdir)
        # Create files where filename sort != version sort
        # By filename: V10__aaa sorts before V2__zzz alphabetically
        # But by version: V2 should come before V10
        (migrations_dir / "V10__later.sql").write_text("SELECT 10")
        (migrations_dir / "V2__earlier.sql").write_text("SELECT 2")
        
        report = validate_migrations(migrations_dir)
        
        assert report.has_errors
        error = next(i for i in report.errors if i.code == "OUT_OF_ORDER")
        assert "not in version order" in error.message


def test_detect_invalid_filename():
    """Test detection of invalid filename format."""
    with tempfile.TemporaryDirectory() as tmpdir:
        migrations_dir = Path(tmpdir)
        (migrations_dir / "V1__valid.sql").write_text("SELECT 1")
        (migrations_dir / "invalid_migration.sql").write_text("SELECT 2")
        
        report = validate_migrations(migrations_dir)
        
        assert report.has_warnings
        warning = next(i for i in report.warnings if i.code == "INVALID_FILENAME")
        assert "invalid_migration.sql" in warning.filename


def test_ignore_non_sql_files():
    """Test that non-SQL files are ignored."""
    with tempfile.TemporaryDirectory() as tmpdir:
        migrations_dir = Path(tmpdir)
        (migrations_dir / "V1__valid.sql").write_text("SELECT 1")
        (migrations_dir / "README.md").write_text("# Migrations")
        (migrations_dir / "config.json").write_text("{}")
        
        report = validate_migrations(migrations_dir)
        
        assert report.total_migrations == 1
        assert len(report.issues) == 0


def test_handle_dotted_versions():
    """Test handling of dotted version numbers."""
    with tempfile.TemporaryDirectory() as tmpdir:
        migrations_dir = Path(tmpdir)
        (migrations_dir / "V1.0__first.sql").write_text("SELECT 1")
        (migrations_dir / "V1.1__second.sql").write_text("SELECT 2")
        (migrations_dir / "V2.0__third.sql").write_text("SELECT 3")
        
        report = validate_migrations(migrations_dir)
        
        # Dotted versions should not trigger gap warnings
        assert not report.has_warnings
        assert not report.has_errors


def test_multiple_issues_sorted_by_severity():
    """Test that issues are sorted by severity (errors first)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        migrations_dir = Path(tmpdir)
        (migrations_dir / "V1__first.sql").write_text("SELECT 1")
        (migrations_dir / "V1__duplicate.sql").write_text("SELECT 1")  # ERROR
        (migrations_dir / "invalid.sql").write_text("SELECT 2")  # WARNING
        
        report = validate_migrations(migrations_dir)
        
        # First issue should be the error
        assert report.issues[0].severity == "error"
        assert report.issues[1].severity == "warning"


# ─────────────────────────────────────────────
# RENUMBERING TESTS
# ─────────────────────────────────────────────

def test_suggest_renumbering_no_changes():
    """Test renumbering when no changes are needed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        migrations_dir = Path(tmpdir)
        (migrations_dir / "V1__first.sql").write_text("")
        (migrations_dir / "V2__second.sql").write_text("")
        (migrations_dir / "V3__third.sql").write_text("")
        
        suggestions = suggest_renumbering(migrations_dir)
        
        assert len(suggestions) == 0


def test_suggest_renumbering_with_gaps():
    """Test renumbering suggestions with gaps."""
    with tempfile.TemporaryDirectory() as tmpdir:
        migrations_dir = Path(tmpdir)
        (migrations_dir / "V1__first.sql").write_text("")
        (migrations_dir / "V5__second.sql").write_text("")
        (migrations_dir / "V10__third.sql").write_text("")
        
        suggestions = suggest_renumbering(migrations_dir)
        
        assert len(suggestions) == 2
        assert suggestions[0]["old"] == "V5__second.sql"
        assert suggestions[0]["new"] == "V2__second.sql"
        assert suggestions[0]["version_new"] == "2"
        
        assert suggestions[1]["old"] == "V10__third.sql"
        assert suggestions[1]["new"] == "V3__third.sql"
        assert suggestions[1]["version_new"] == "3"


def test_suggest_renumbering_out_of_order():
    """Test renumbering suggestions when migrations are out of order."""
    with tempfile.TemporaryDirectory() as tmpdir:
        migrations_dir = Path(tmpdir)
        # Create files where version order doesn't match sequential numbering
        (migrations_dir / "V10__first.sql").write_text("")  # Should be V1
        (migrations_dir / "V20__second.sql").write_text("")  # Should be V2
        (migrations_dir / "V30__third.sql").write_text("")  # Should be V3
        
        suggestions = suggest_renumbering(migrations_dir)
        
        # All should be renumbered to sequential order
        assert len(suggestions) == 3
        assert suggestions[0]["version_new"] == "1"
        assert suggestions[1]["version_new"] == "2"
        assert suggestions[2]["version_new"] == "3"


def test_renumbering_ignores_repeatable():
    """Test that repeatable migrations are ignored in renumbering."""
    with tempfile.TemporaryDirectory() as tmpdir:
        migrations_dir = Path(tmpdir)
        (migrations_dir / "V1__first.sql").write_text("")
        (migrations_dir / "R__repeatable.sql").write_text("")
        (migrations_dir / "V5__second.sql").write_text("")
        
        suggestions = suggest_renumbering(migrations_dir)
        
        # Only versioned migrations should be included
        assert len(suggestions) == 1
        assert suggestions[0]["old"] == "V5__second.sql"


# ─────────────────────────────────────────────
# FORMATTER TESTS
# ─────────────────────────────────────────────

def test_format_text_no_issues():
    """Test text formatting with no issues."""
    with tempfile.TemporaryDirectory() as tmpdir:
        migrations_dir = Path(tmpdir)
        (migrations_dir / "V1__first.sql").write_text("")
        
        report = validate_migrations(migrations_dir)
        output = format_text(report)
        
        assert "Total migrations: 1" in output
        assert "✓ All migrations validated" in output


def test_format_text_with_errors():
    """Test text formatting with errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        migrations_dir = Path(tmpdir)
        (migrations_dir / "V1__first.sql").write_text("")
        (migrations_dir / "V1__duplicate.sql").write_text("")
        
        report = validate_migrations(migrations_dir)
        output = format_text(report, show_suggestions=True)
        
        assert "❌ 1 error(s):" in output
        assert "[DUPLICATE_VERSION]" in output
        assert "→" in output  # Suggestion marker


def test_format_text_with_warnings():
    """Test text formatting with warnings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        migrations_dir = Path(tmpdir)
        (migrations_dir / "V1__first.sql").write_text("")
        (migrations_dir / "V2__second.sql").write_text("")
        (migrations_dir / "V5__fifth.sql").write_text("")
        
        report = validate_migrations(migrations_dir)
        output = format_text(report, show_suggestions=True)
        
        assert "⚠  1 warning(s):" in output
        assert "[VERSION_GAP]" in output


def test_format_json():
    """Test JSON formatting."""
    import json
    
    with tempfile.TemporaryDirectory() as tmpdir:
        migrations_dir = Path(tmpdir)
        (migrations_dir / "V1__first.sql").write_text("")
        (migrations_dir / "V1__duplicate.sql").write_text("")
        
        report = validate_migrations(migrations_dir)
        output = format_json(report)
        
        data = json.loads(output)
        assert data["total_migrations"] == 2
        assert data["has_errors"] is True
        assert data["error_count"] == 1
        assert len(data["issues"]) == 1
        assert data["issues"][0]["code"] == "DUPLICATE_VERSION"


def test_format_json_no_issues():
    """Test JSON formatting with no issues."""
    import json
    
    with tempfile.TemporaryDirectory() as tmpdir:
        migrations_dir = Path(tmpdir)
        (migrations_dir / "V1__first.sql").write_text("")
        
        report = validate_migrations(migrations_dir)
        output = format_json(report)
        
        data = json.loads(output)
        assert data["has_errors"] is False
        assert data["has_warnings"] is False
        assert data["error_count"] == 0
        assert data["warning_count"] == 0
        assert len(data["issues"]) == 0


# ─────────────────────────────────────────────
# EDGE CASES
# ─────────────────────────────────────────────

def test_version_gap_not_detected_for_dotted_versions():
    """Test that version gaps are not detected for non-simple versions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        migrations_dir = Path(tmpdir)
        (migrations_dir / "V1.0__first.sql").write_text("")
        (migrations_dir / "V1.5__second.sql").write_text("")
        
        report = validate_migrations(migrations_dir)
        
        # Should not trigger gap warning for dotted versions
        assert not report.has_warnings


def test_single_migration_no_order_check():
    """Test that a single migration doesn't trigger order checks."""
    with tempfile.TemporaryDirectory() as tmpdir:
        migrations_dir = Path(tmpdir)
        (migrations_dir / "V99__only.sql").write_text("")
        
        report = validate_migrations(migrations_dir)
        
        assert not report.has_errors
        assert not report.has_warnings


def test_subdirectories_ignored():
    """Test that subdirectories are ignored during validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        migrations_dir = Path(tmpdir)
        (migrations_dir / "V1__first.sql").write_text("")
        
        # Create a subdirectory with migrations (should be ignored)
        subdir = migrations_dir / "archive"
        subdir.mkdir()
        (subdir / "V2__old.sql").write_text("")
        
        report = validate_migrations(migrations_dir)
        
        # Should only count the one file in the root
        assert report.total_migrations == 1

"""Tests for naming convention enforcement (Feature #23)."""

import tempfile
import pytest
from pathlib import Path

from sqlfy.analysis.naming import validate_naming, validate_naming_files


# ─── validate_naming (on-disk) ───────────────────────────────────────────────

def test_valid_names():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir)
        (p / "V1__create_users.sql").write_text("SELECT 1")
        (p / "V2__add_orders.sql").write_text("SELECT 1")

        report = validate_naming(p)
        assert report.total_migrations == 2
        assert not report.has_errors
        assert not report.has_warnings


def test_invalid_description_format():
    """Descriptions with hyphens or uppercase should fail the default pattern."""
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir)
        (p / "V1__Create-Users.sql").write_text("SELECT 1")

        report = validate_naming(p)
        assert report.total_migrations == 1
        assert not report.has_errors
        assert report.has_warnings
        codes = [i.code for i in report.warnings]
        assert "DESC_FORMAT" in codes


def test_long_filename():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir)
        longdesc = "a" * 200
        fname = f"V1__{longdesc}.sql"
        (p / fname).write_text("SELECT 1")

        report = validate_naming(p, max_length=120)
        assert report.total_migrations == 1
        assert report.has_warnings
        codes = [i.code for i in report.warnings]
        assert "LONG_FILENAME" in codes


def test_non_flyway_filename():
    """Files that don't match the Flyway pattern produce INVALID_FILENAME."""
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir)
        (p / "create_users.sql").write_text("SELECT 1")

        report = validate_naming(p)
        assert report.total_migrations == 1
        assert report.has_warnings
        codes = [i.code for i in report.warnings]
        assert "INVALID_FILENAME" in codes


def test_leading_underscore_description():
    """Descriptions that start with an underscore emit DESC_UNDERSCORE."""
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir)
        (p / "V1___create_users.sql").write_text("SELECT 1")  # extra leading _

        report = validate_naming(p)
        assert report.has_warnings
        codes = [i.code for i in report.warnings]
        assert "DESC_UNDERSCORE" in codes


def test_trailing_underscore_description():
    """Descriptions that end with an underscore emit DESC_UNDERSCORE."""
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir)
        (p / "V1__create_users_.sql").write_text("SELECT 1")

        report = validate_naming(p)
        assert report.has_warnings
        codes = [i.code for i in report.warnings]
        assert "DESC_UNDERSCORE" in codes


def test_custom_pattern_accepted():
    """Custom pattern that explicitly allows hyphens should pass."""
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir)
        (p / "V1__create-users.sql").write_text("SELECT 1")

        report = validate_naming(p, pattern=r"^[a-z0-9_-]+$")
        assert not report.has_warnings


def test_custom_pattern_rejected():
    """Custom pattern that forbids underscores should fail for a name with underscores."""
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir)
        (p / "V1__create_users.sql").write_text("SELECT 1")

        report = validate_naming(p, pattern=r"^[a-z0-9]+$")
        assert report.has_warnings
        codes = [i.code for i in report.warnings]
        assert "DESC_FORMAT" in codes


def test_invalid_regex_raises():
    """An invalid regex passed as pattern raises ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir)
        (p / "V1__create_users.sql").write_text("SELECT 1")

        with pytest.raises(ValueError, match="Invalid --pattern regex"):
            validate_naming(p, pattern=r"[invalid(regex")


def test_repeatable_migration_valid():
    """Repeatable migrations (R__) should be accepted by the validator."""
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir)
        (p / "R__create_views.sql").write_text("SELECT 1")

        report = validate_naming(p)
        assert report.total_migrations == 1
        assert not report.has_warnings


def test_subdirectory_files_counted():
    """Files nested in subdirectories are still discovered and counted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir)
        sub = p / "sub"
        sub.mkdir()
        (sub / "V1__create_users.sql").write_text("SELECT 1")

        report = validate_naming(p)
        assert report.total_migrations == 1
        assert not report.has_warnings


# ─── validate_naming_files (in-memory) ───────────────────────────────────────

def test_validate_naming_files_valid():
    """In-memory validator accepts well-formed flat filenames."""
    files = [
        {"filename": "V1__create_users.sql", "sql": ""},
        {"filename": "V2__add_orders.sql", "sql": ""},
    ]
    report = validate_naming_files(files)
    assert report.total_migrations == 2
    assert not report.has_warnings


def test_validate_naming_files_relative_path():
    """In-memory validator strips directory portion before parsing (bug fix #2)."""
    files = [
        {"filename": "subdir/V1__create_users.sql", "sql": ""},
    ]
    report = validate_naming_files(files)
    assert report.total_migrations == 1
    # Should resolve to V1__create_users.sql, not fail as INVALID_FILENAME
    assert not report.has_warnings


def test_validate_naming_files_invalid_format():
    """In-memory validator reports INVALID_FILENAME for non-Flyway names."""
    files = [{"filename": "create_users.sql", "sql": ""}]
    report = validate_naming_files(files)
    assert report.has_warnings
    assert report.warnings[0].code == "INVALID_FILENAME"


def test_validate_naming_files_invalid_regex_raises():
    """validate_naming_files raises ValueError for an invalid regex."""
    files = [{"filename": "V1__create_users.sql", "sql": ""}]
    with pytest.raises(ValueError, match="Invalid --pattern regex"):
        validate_naming_files(files, pattern=r"[invalid(regex")

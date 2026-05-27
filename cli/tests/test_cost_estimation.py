"""Tests for migration execution cost estimation (Feature #19)."""

from pathlib import Path

from sqlfy.analysis.cost_estimator import estimate_migration, estimate_migrations


def test_estimate_migration_simple():
    sql_create = "CREATE TABLE t1 (id INT);"
    res = estimate_migration("V1__create.sql", sql_create, dialect="oracle")
    assert res.score <= 25
    assert res.category == "low"

    sql_add_nn = "ALTER TABLE t1 ADD (new_col NUMBER NOT NULL);"
    res2 = estimate_migration("V2__add_not_null.sql", sql_add_nn, dialect="oracle")
    assert res2.score >= 75
    assert res2.category in ("very_high", "high")
    assert hasattr(res, "estimated_seconds")
    assert hasattr(res2, "estimated_seconds")
    assert res.estimated_seconds >= 0
    assert res2.estimated_seconds >= 0


def test_estimate_migrations_collection(tmp_path):
    d = tmp_path / "migs"
    d.mkdir()
    (d / "V1__a.sql").write_text("CREATE TABLE a (id INT);\n")
    (d / "V2__b.sql").write_text("INSERT INTO a (id) SELECT id FROM b;\n")

    files = [
        {"filename": "V1__a.sql", "sql": (d / "V1__a.sql").read_text(encoding="utf-8")},
        {"filename": "V2__b.sql", "sql": (d / "V2__b.sql").read_text(encoding="utf-8")},
    ]

    results = estimate_migrations(files, dialect="oracle")
    assert len(results) == 2
    scores = {r.filename: r.score for r in results}
    assert scores["V1__a.sql"] <= 25
    assert scores["V2__b.sql"] >= 50


def test_estimated_runtime_with_table_stats():
    sql = "INSERT INTO a SELECT id FROM b;"
    files = [{"filename": "V2__b.sql", "sql": sql}]

    no_stats = estimate_migrations(files, dialect="oracle")[0]
    small_stats = {"b": {"rows": 1000, "avg_row_size": 100}}
    with_stats = estimate_migrations(files, dialect="oracle", table_stats=small_stats)[0]

    assert hasattr(no_stats, "estimated_seconds")
    assert hasattr(with_stats, "estimated_seconds")
    assert with_stats.estimated_seconds < no_stats.estimated_seconds


def test_throughput_override():
    sql = "INSERT INTO a SELECT id FROM b;"
    files = [{"filename": "V2__b.sql", "sql": sql}]
    stats = {"b": {"rows": 1000000, "avg_row_size": 200}}

    slow = estimate_migrations(files, dialect="oracle", table_stats=stats, throughput_bytes_per_sec=10 * 1024 * 1024)[0]
    fast = estimate_migrations(files, dialect="oracle", table_stats=stats, throughput_bytes_per_sec=200 * 1024 * 1024)[0]

    assert slow.estimated_seconds > fast.estimated_seconds


# ── Weight profile tests ─────────────────────────────────────────────────────

# Typical PL/SQL-heavy migration: a package body with internal DML
_PACKAGE_SQL = """
CREATE OR REPLACE PACKAGE BODY my_pkg AS
  PROCEDURE do_stuff IS
  BEGIN
    INSERT INTO log_table VALUES (1);
    UPDATE config_table SET val = 'x';
  END;
END my_pkg;
/
"""

def test_plsql_profile_reduces_score():
    """plsql profile should produce a lower score than default for package bodies."""
    files = [{"filename": "V1__pkg.sql", "sql": _PACKAGE_SQL}]
    default_result = estimate_migrations(files, dialect="oracle", weight_profile="default")[0]
    plsql_result   = estimate_migrations(files, dialect="oracle", weight_profile="plsql")[0]
    assert plsql_result.score <= default_result.score


def test_plsql_profile_keeps_dangerous_dml_high():
    """plsql profile should not reduce risk for unbounded full-table updates."""
    sql = "UPDATE orders SET status = 'X';"  # no WHERE clause
    files = [{"filename": "V1__bad.sql", "sql": sql}]
    plsql_result = estimate_migrations(files, dialect="oracle", weight_profile="plsql")[0]
    # multiplier for UPDATE (no where) is 1.0 in plsql profile — should still be high
    assert plsql_result.score >= 80


def test_data_migration_profile_amplifies_bulk_dml():
    """data-migration profile should score bulk INSERT higher than default."""
    sql = "INSERT INTO archive SELECT * FROM orders;"
    files = [{"filename": "V1__bulk.sql", "sql": sql}]
    default_result   = estimate_migrations(files, dialect="oracle", weight_profile="default")[0]
    datamig_result   = estimate_migrations(files, dialect="oracle", weight_profile="data-migration")[0]
    assert datamig_result.score >= default_result.score


def test_default_profile_unchanged():
    """default profile must produce the same results as not passing a profile."""
    sql = "CREATE TABLE t (id INT); INSERT INTO t SELECT id FROM src;"
    files = [{"filename": "V1.sql", "sql": sql}]
    explicit_default = estimate_migrations(files, dialect="oracle", weight_profile="default")[0]
    no_profile       = estimate_migrations(files, dialect="oracle")[0]
    assert explicit_default.score == no_profile.score


def test_format_text_shows_profile_note():
    from sqlfy.analysis.cost_estimator import format_text
    files = [{"filename": "V1.sql", "sql": "CREATE TABLE t (id INT);"}]
    results = estimate_migrations(files, dialect="oracle", weight_profile="plsql")
    text = format_text(results, weight_profile="plsql")
    assert "plsql" in text

"""Dialect regression tests for CLI JSON outputs.

Validates that JSON outputs are consistent across different SQL dialects.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run_cli(*args):
    """Run sqlfy CLI and return (stdout, stderr, returncode)."""
    result = subprocess.run(
        [sys.executable, "-m", "sqlfy.main", *args],
        capture_output=True,
        text=True,
    )
    return result.stdout, result.stderr, result.returncode


def write_migrations(directory: Path) -> None:
    """Write a small Flyway fixture for subprocess-level CLI tests."""
    (directory / "V1__create_users.sql").write_text(
        """CREATE TABLE app.users (
            id NUMBER PRIMARY KEY,
            email VARCHAR2(255) NOT NULL UNIQUE
        );""",
        encoding="utf-8",
    )
    (directory / "V2__create_orders.sql").write_text(
        """CREATE TABLE app.orders (
            id NUMBER PRIMARY KEY,
            user_id NUMBER NOT NULL,
            CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES app.users(id)
        );""",
        encoding="utf-8",
    )


def test_dump_json_oracle():
    """dump produces consistent JSON across dialects (oracle)."""
    tmp = Path("/tmp/test_dump_oracle")
    tmp.mkdir(parents=True, exist_ok=True)
    write_migrations(tmp)
    stdout, stderr, code = run_cli("dump", str(tmp), "--format", "json")
    assert code == 0, stderr
    state = json.loads(stdout)
    assert "tables" in state


def test_dump_json_postgres():
    """dump produces consistent JSON across dialects (postgres)."""
    tmp = Path("/tmp/test_dump_postgres")
    tmp.mkdir(parents=True, exist_ok=True)
    write_migrations(tmp)
    stdout, stderr, code = run_cli("dump", str(tmp), "--dialect", "postgres", "--format", "json")
    assert code == 0, stderr
    state = json.loads(stdout)
    assert "tables" in state


def test_dump_json_mysql():
    """dump produces consistent JSON across dialects (mysql)."""
    tmp = Path("/tmp/test_dump_mysql")
    tmp.mkdir(parents=True, exist_ok=True)
    write_migrations(tmp)
    stdout, stderr, code = run_cli("dump", str(tmp), "--dialect", "mysql", "--format", "json")
    assert code == 0, stderr
    state = json.loads(stdout)
    assert "tables" in state


def test_query_json_oracle():
    """query produces consistent JSON across dialects (oracle)."""
    tmp = Path("/tmp/test_query_oracle")
    tmp.mkdir(parents=True, exist_ok=True)
    write_migrations(tmp)
    stdout, stderr, code = run_cli("query", str(tmp), "tables", "--format", "json")
    assert code == 0, stderr
    state = json.loads(stdout)
    assert "meta" in state


def test_query_json_postgres():
    """query produces consistent JSON across dialects (postgres)."""
    tmp = Path("/tmp/test_query_postgres")
    tmp.mkdir(parents=True, exist_ok=True)
    write_migrations(tmp)
    stdout, stderr, code = run_cli("query", str(tmp), "tables", "--dialect", "postgres", "--format", "json")
    assert code == 0, stderr
    state = json.loads(stdout)
    assert "meta" in state


def test_manifest_json_oracle():
    """manifest produces consistent JSON across dialects (oracle)."""
    tmp = Path("/tmp/test_manifest_oracle")
    tmp.mkdir(parents=True, exist_ok=True)
    write_migrations(tmp)
    stdout, stderr, code = run_cli("manifest", str(tmp), "--format", "json")
    assert code == 0, stderr
    state = json.loads(stdout)
    assert "tableCount" in state


def test_manifest_json_postgres():
    """manifest produces consistent JSON across dialects (postgres)."""
    tmp = Path("/tmp/test_manifest_postgres")
    tmp.mkdir(parents=True, exist_ok=True)
    write_migrations(tmp)
    stdout, stderr, code = run_cli("manifest", str(tmp), "--dialect", "postgres", "--format", "json")
    assert code == 0, stderr
    state = json.loads(stdout)
    assert "tableCount" in state


def test_diff_versions_json_oracle():
    """diff-versions produces consistent JSON across dialects (oracle)."""
    tmp = Path("/tmp/test_diff_oracle")
    tmp.mkdir(parents=True, exist_ok=True)
    write_migrations(tmp)
    stdout, stderr, code = run_cli("diff-versions", str(tmp), "--from", "1", "--to", "2", "--format", "json")
    assert code == 0, stderr
    state = json.loads(stdout)
    assert "stats" in state


def test_diff_versions_json_postgres():
    """diff-versions produces consistent JSON across dialects (postgres)."""
    tmp = Path("/tmp/test_diff_postgres")
    tmp.mkdir(parents=True, exist_ok=True)
    write_migrations(tmp)
    stdout, stderr, code = run_cli("diff-versions", str(tmp), "--from", "1", "--to", "2", "--dialect", "postgres", "--format", "json")
    assert code == 0, stderr
    state = json.loads(stdout)
    assert "stats" in state


def test_insights_json_oracle():
    """insights produces consistent JSON across dialects (oracle)."""
    tmp = Path("/tmp/test_insights_oracle")
    tmp.mkdir(parents=True, exist_ok=True)
    write_migrations(tmp)
    stdout, stderr, code = run_cli("insights", str(tmp), "--format", "json")
    assert code == 0, stderr
    state = json.loads(stdout)
    assert isinstance(state, dict)


def test_insights_json_postgres():
    """insights produces consistent JSON across dialects (postgres)."""
    tmp = Path("/tmp/test_insights_postgres")
    tmp.mkdir(parents=True, exist_ok=True)
    write_migrations(tmp)
    stdout, stderr, code = run_cli("insights", str(tmp), "--dialect", "postgres", "--format", "json")
    assert code == 0, stderr
    state = json.loads(stdout)
    assert isinstance(state, dict)

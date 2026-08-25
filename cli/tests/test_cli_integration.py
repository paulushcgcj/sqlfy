"""Integration tests for CLI command modules."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sqlfy.version import get_version


def run_cli(*args):
    """Run sqlfy CLI and return (stdout, stderr, returncode)."""
    result = subprocess.run(
        [sys.executable, "-m", "sqlfy.main", *args],
        capture_output=True,
        text=True,
    )
    return result.stdout, result.stderr, result.returncode


def run_legacy_ng(*args):
    """Run the installed compatibility script beside the active interpreter."""
    result = subprocess.run(
        [str(Path(sys.executable).with_name("sqlfy-ng")), *args],
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


def test_dump_help():
    """dump --help works."""
    stdout, stderr, code = run_cli("dump", "--help")
    assert code == 0
    assert "dump" in stdout.lower() or "--format" in stdout


def test_chunks_help():
    """chunks --help works."""
    stdout, stderr, code = run_cli("chunks", "--help")
    assert code == 0
    assert "LLM vector chunks" in stdout or "chunks" in stdout


def test_graph_help():
    """graph --help works."""
    stdout, stderr, code = run_cli("graph", "--help")
    assert code == 0
    assert "graph" in stdout.lower() or "graph" in stderr.lower()


def test_insights_help():
    """insights --help works."""
    stdout, stderr, code = run_cli("insights", "--help")
    assert code == 0
    assert "insights" in stdout.lower() or "insights" in stderr.lower()


def test_query_help():
    """query --help works."""
    stdout, stderr, code = run_cli("query", "--help")
    assert code == 0
    assert "query" in stdout.lower()


def test_validate_help():
    """validate --help works."""
    stdout, stderr, code = run_cli("validate", "--help")
    assert code == 0
    assert "validate" in stdout.lower() or "ordering" in stdout.lower()


def test_lint_help():
    """lint --help works."""
    stdout, stderr, code = run_cli("lint", "--help")
    assert code == 0
    assert "lint" in stdout.lower() or "quality" in stdout.lower()


def test_cache_info():
    """cache info works."""
    stdout, stderr, code = run_cli("cache", "info")
    assert code == 0
    # Should output cache status
    assert "Cache" in stdout or "Cache" in stderr or "empty" in stdout.lower()


def test_legacy_mode_no_args():
    """No-argument invocation guides users to the canonical command surface."""
    stdout, stderr, code = run_cli()
    assert code == 2
    assert "usage: sqlfy" in stderr
    assert "diff-versions" in stderr


def test_version_reports_installed_package_version():
    """The CLI version must agree with the version in generated metadata."""
    stdout, stderr, code = run_cli("--version")

    assert code == 0, stderr
    assert stdout.strip() == f"sqlfy {get_version()}"


def test_sqlfy_ng_is_a_deprecated_alias_for_the_canonical_cli():
    """The compatibility command must not maintain a second command tree."""
    stdout, stderr, code = run_legacy_ng("--help")

    assert code == 0
    assert "Warning: 'sqlfy-ng' is deprecated" in stderr
    assert "diff-versions" in stdout
    assert "intelligence" not in stdout


def test_dump_json_executes_full_cli_pipeline(tmp_path):
    """dump must execute parsing/reconstruction and emit machine-readable JSON."""
    write_migrations(tmp_path)

    stdout, stderr, code = run_cli("dump", str(tmp_path), "--format", "json")

    assert code == 0, stderr
    state = json.loads(stdout)
    assert set(state["tables"]) == {"APP.USERS", "APP.ORDERS"}
    assert state["stats"]["table_count"] == 2


def test_manifest_and_query_execute_full_cli_pipeline(tmp_path):
    """Core discovery commands must work through the public parser entry point."""
    write_migrations(tmp_path)

    stdout, stderr, code = run_cli("manifest", str(tmp_path), "--format", "json")
    assert code == 0, stderr
    assert json.loads(stdout)["tableCount"] == 2

    stdout, stderr, code = run_cli(
        "query", str(tmp_path), "fk-path", "--from-table", "APP.ORDERS",
        "--to-table", "APP.USERS", "--format", "json",
    )
    assert code == 0, stderr
    assert json.loads(stdout)["meta"]["length"] == 1


def test_diff_versions_executes_full_cli_pipeline(tmp_path):
    """Version comparison must use the same public CLI path as users."""
    write_migrations(tmp_path)

    stdout, stderr, code = run_cli(
        "diff-versions", str(tmp_path), "--from", "1", "--to", "2", "--format", "json",
    )

    assert code == 0, stderr
    diff = json.loads(stdout)
    assert diff["stats"]["tablesAdded"] == 1
    assert diff["tableChanges"][0]["fullName"] == "APP.ORDERS"

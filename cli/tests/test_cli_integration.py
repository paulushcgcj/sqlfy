"""Integration tests for CLI command modules."""

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
    """Legacy mode with no args shows error."""
    stdout, stderr, code = run_cli()
    # Should fail with missing migrations_dir
    assert code != 0

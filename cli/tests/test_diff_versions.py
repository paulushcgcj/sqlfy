"""Tests for cmd_diff_versions (diff-versions subcommand) added to evolution.py."""

import json
import tempfile
from pathlib import Path

import pytest

from sqlfy.commands.evolution import cmd_diff_versions


# ── minimal migration fixtures ────────────────────────────────────────────────

_MIGRATION_V1 = "CREATE TABLE users (id NUMBER PRIMARY KEY, name VARCHAR2(100));"
_MIGRATION_V2 = "CREATE TABLE orders (id NUMBER PRIMARY KEY, user_id NUMBER REFERENCES users(id));"
_MIGRATION_V3 = "ALTER TABLE users ADD (email VARCHAR2(255));"


def _make_args(**kwargs):
    """Build a minimal argparse.Namespace for cmd_diff_versions."""
    import argparse
    defaults = {
        "migrations_dir": None,
        "json_input": None,
        "dialect": "oracle",
        "from_version": None,
        "to_version": None,
        "format": "json",
        "out": None,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _write_migrations(tmp: Path, migrations: dict[str, str]) -> list[dict]:
    """Write migration files and return the load_files-style list."""
    for fname, sql in migrations.items():
        (tmp / fname).write_text(sql)
    return [{"filename": fname, "sql": sql} for fname, sql in sorted(migrations.items())]


# ── tests ─────────────────────────────────────────────────────────────────────

def test_diff_versions_v1_to_v2_adds_table(tmp_path, capsys):
    """V1→V2 diff should detect the new 'orders' table as added."""
    _write_migrations(tmp_path, {
        "V1__create_users.sql": _MIGRATION_V1,
        "V2__create_orders.sql": _MIGRATION_V2,
        "V3__alter_users.sql": _MIGRATION_V3,
    })

    args = _make_args(migrations_dir=str(tmp_path), from_version="1", to_version="2")
    cmd_diff_versions(**vars(args))

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data.get("stats", {}).get("tablesAdded", 0) > 0 or len(data.get("tableChanges", [])) > 0


def test_diff_versions_text_output(tmp_path, capsys):
    """Text format should contain the diff header."""
    _write_migrations(tmp_path, {
        "V1__create_users.sql": _MIGRATION_V1,
        "V2__create_orders.sql": _MIGRATION_V2,
    })

    args = _make_args(migrations_dir=str(tmp_path), from_version="1", to_version="2", format="text")
    cmd_diff_versions(**vars(args))

    captured = capsys.readouterr()
    assert "SCHEMA STATE DIFF" in captured.out or "tablesAdded" in captured.out.lower() or "ORDERS" in captured.out


def test_diff_versions_same_version_produces_no_changes(tmp_path, capsys):
    """When from and to are the same version, the diff should be empty."""
    _write_migrations(tmp_path, {
        "V1__create_users.sql": _MIGRATION_V1,
        "V2__create_orders.sql": _MIGRATION_V2,
    })

    args = _make_args(migrations_dir=str(tmp_path), from_version="2", to_version="2")
    cmd_diff_versions(**vars(args))

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data.get("stats", {}).get("tablesAdded", 0) == 0
    assert data.get("stats", {}).get("tablesRemoved", 0) == 0


def test_diff_versions_no_versions_uses_latest(tmp_path, capsys):
    """Omitting both versions should produce a diff of final state vs final state (empty)."""
    _write_migrations(tmp_path, {
        "V1__create_users.sql": _MIGRATION_V1,
    })

    args = _make_args(migrations_dir=str(tmp_path), from_version=None, to_version=None)
    cmd_diff_versions(**vars(args))

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    # Both sides are the same final state → nothing changed
    total_changes = sum(v for v in data.get("stats", {}).values() if isinstance(v, int))
    assert total_changes == 0


def test_diff_versions_from_only_compares_partial_to_full(tmp_path, capsys):
    """Specifying only --from should compare that version snapshot to the full state."""
    _write_migrations(tmp_path, {
        "V1__create_users.sql": _MIGRATION_V1,
        "V2__create_orders.sql": _MIGRATION_V2,
    })

    # from_version=1 means state_a is V1 (users only), state_b is latest (users + orders)
    args = _make_args(migrations_dir=str(tmp_path), from_version="1", to_version=None)
    cmd_diff_versions(**vars(args))

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data.get("stats", {}).get("tablesAdded", 0) >= 1


def test_diff_versions_to_only_compares_full_to_partial(tmp_path, capsys):
    """Specifying only --to should compare the full state to that version snapshot."""
    _write_migrations(tmp_path, {
        "V1__create_users.sql": _MIGRATION_V1,
        "V2__create_orders.sql": _MIGRATION_V2,
    })

    # from_version=None means state_a is latest, to_version=1 means state_b is V1
    args = _make_args(migrations_dir=str(tmp_path), from_version=None, to_version="1")
    cmd_diff_versions(**vars(args))

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    # Going from full (orders exist) to V1 (no orders) should show tables removed
    assert data.get("stats", {}).get("tablesRemoved", 0) >= 1

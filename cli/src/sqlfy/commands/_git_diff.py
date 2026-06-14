"""Git diff utility for --from-diff flag."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import sqlglot
import sqlglot.expressions as exp


def resolve_git_root(path: str) -> str:
    """Walk upward from *path* looking for a ``.git/`` directory.

    Returns the absolute path to the repository root.
    Raises ``RuntimeError`` if no ``.git/`` is found.
    """
    current = Path(path).resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists() or (parent / ".git").is_dir():
            return str(parent)
    raise RuntimeError(
        f"Could not find a git repository (no .git/ directory found) "
        f"starting from {path}"
    )


def run_git_diff(
    git_root: str,
    ref: str | None = None,
) -> list[str]:
    """Run ``git diff --name-only`` and return the list of changed file paths.

    When *ref* is ``None`` the staged changes (``--cached``) are used.
    Raises ``RuntimeError`` when git is not available or the command fails.
    """
    cmd = ["git", "-C", git_root, "diff", "--name-only"]
    if ref is None:
        cmd.append("--cached")
    else:
        cmd.append(ref)
        cmd.append("HEAD")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "Could not run git diff: git executable not found. "
            "Ensure git is installed and available on PATH."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            "Could not run git diff: the command timed out."
        )

    if result.returncode != 0:
        raise RuntimeError(
            f"Could not run git diff: git exited with code {result.returncode}.\n"
            f"stderr: {result.stderr.strip()}"
        )

    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def filter_sql_files(changed_files: list[str], migrations_dir: str) -> list[str]:
    """Filter *changed_files* to only ``.sql`` files under *migrations_dir*.

    Returns a list of absolute paths.
    """
    migrations_path = Path(migrations_dir).resolve()
    result: list[str] = []
    for rel_path in changed_files:
        abs_path = (migrations_path / rel_path).resolve()
        try:
            abs_path.relative_to(migrations_path)
        except ValueError:
            continue
        if abs_path.suffix.lower() == ".sql" and abs_path.exists():
            result.append(str(abs_path))
    return result


def get_diff_files(migrations_dir: str, ref: str | None = None) -> list[str]:
    """High-level helper: resolve git root, diff, filter to ``.sql`` files.

    Returns absolute paths of changed ``.sql`` files under *migrations_dir*.
    """
    git_root = resolve_git_root(migrations_dir)
    changed = run_git_diff(git_root, ref=ref)
    return filter_sql_files(changed, migrations_dir)


def extract_tables_from_sql(file_path: str, dialect: str = "oracle") -> set[str]:
    """Parse a SQL file and extract table names from DDL statements.

    Recognised DDL types:
    - ``CREATE TABLE`` (not CREATE OR REPLACE or other CREATE variants)
    - ``ALTER TABLE``
    - ``DROP TABLE``

    Returns a set of upper-cased table names.
    """
    tables: set[str] = set()

    try:
        raw = Path(file_path).read_text(encoding="utf-8", errors="replace")
        parsed = sqlglot.parse(raw, dialect=dialect, error_level=sqlglot.ErrorLevel.IGNORE)
    except FileNotFoundError:
        return tables
    except Exception:
        return tables

    if not parsed:
        return tables

    for statement in parsed:
        if statement is None:
            continue

        if isinstance(statement, exp.Create):
            if isinstance(statement.this, exp.Schema):
                table_node = statement.this.this
            elif isinstance(statement.this, exp.Table):
                table_node = statement.this
            else:
                continue
            if table_node:
                tables.add(table_node.sql(dialect=dialect).upper())

        elif isinstance(statement, exp.Alter):
            if isinstance(statement.this, exp.Table):
                tables.add(statement.this.sql(dialect=dialect).upper())

        elif isinstance(statement, exp.Drop):
            if isinstance(statement.this, exp.Table):
                tables.add(statement.this.sql(dialect=dialect).upper())

    return tables


def extract_tables_from_diff(
    sql_files: list[str],
    dialect: str = "oracle",
) -> dict[str, set[str]]:
    """Extract table names from each SQL file in *sql_files*.

    Returns a dict mapping file path -> set of table names.
    """
    result: dict[str, set[str]] = {}
    for f in sql_files:
        tables = extract_tables_from_sql(f, dialect=dialect)
        if tables:
            result[f] = tables
    return result

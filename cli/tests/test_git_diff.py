"""Tests for the git diff utility module (``_git_diff.py``)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest import mock

import pytest

from sqlfy.commands._git_diff import (
    extract_tables_from_diff,
    extract_tables_from_sql,
    filter_sql_files,
    get_diff_files,
    resolve_git_root,
    run_git_diff,
)


# ── resolve_git_root ────────────────────────────────────────────────────

class TestResolveGitRoot:
    def test_finds_git_dir_in_current(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        assert resolve_git_root(str(tmp_path)) == str(tmp_path.resolve())

    def test_finds_git_dir_in_parent(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        child = tmp_path / "a" / "b"
        child.mkdir(parents=True)
        assert resolve_git_root(str(child)) == str(tmp_path.resolve())

    def test_raises_when_no_git_dir(self, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError, match="Could not find a git repository"):
            resolve_git_root(str(tmp_path))

    def test_git_dir_is_file_gitmodules(self, tmp_path: Path) -> None:
        (tmp_path / ".git").write_text("gitdir: ../.git/modules/foo\n")
        assert resolve_git_root(str(tmp_path)) == str(tmp_path.resolve())


# ── run_git_diff ────────────────────────────────────────────────────────

class TestRunGitDiff:
    def test_happy_path(self, tmp_path: Path) -> None:
        with mock.patch("sqlfy.commands._git_diff.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["git", "diff"],
                returncode=0,
                stdout="V2__add_index.sql\nV3__add_table.sql\n",
                stderr="",
            )
            result = run_git_diff(str(tmp_path), ref="HEAD~1")

        assert result == ["V2__add_index.sql", "V3__add_table.sql"]
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "--name-only" in args
        assert "--cached" not in args
        assert "HEAD~1" in args

    def test_staged_changes(self, tmp_path: Path) -> None:
        with mock.patch("sqlfy.commands._git_diff.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["git", "diff"],
                returncode=0,
                stdout="staged.sql\n",
                stderr="",
            )
            result = run_git_diff(str(tmp_path), ref=None)

        assert result == ["staged.sql"]
        args = mock_run.call_args[0][0]
        assert "--cached" in args

    def test_empty_diff(self, tmp_path: Path) -> None:
        with mock.patch("sqlfy.commands._git_diff.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["git", "diff"],
                returncode=0,
                stdout="",
                stderr="",
            )
            result = run_git_diff(str(tmp_path), ref="HEAD~1")
        assert result == []

    def test_git_not_found(self, tmp_path: Path) -> None:
        with mock.patch("sqlfy.commands._git_diff.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            with pytest.raises(RuntimeError, match="git executable not found"):
                run_git_diff(str(tmp_path), ref="HEAD~1")

    def test_git_timeout(self, tmp_path: Path) -> None:
        with mock.patch("sqlfy.commands._git_diff.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=30)
            with pytest.raises(RuntimeError, match="timed out"):
                run_git_diff(str(tmp_path), ref="HEAD~1")

    def test_git_exit_nonzero(self, tmp_path: Path) -> None:
        with mock.patch("sqlfy.commands._git_diff.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["git", "diff"],
                returncode=128,
                stdout="",
                stderr="fatal: bad revision",
            )
            with pytest.raises(RuntimeError, match="exited with code 128"):
                run_git_diff(str(tmp_path), ref="HEAD~1")


# ── filter_sql_files ────────────────────────────────────────────────────

class TestFilterSqlFiles:
    def test_keeps_sql_files_under_migrations_dir(self, tmp_path: Path) -> None:
        migrations = tmp_path / "migrations"
        migrations.mkdir()
        (migrations / "V1__create.sql").write_text("")
        (migrations / "V2__alter.sql").write_text("")

        result = filter_sql_files(
            ["V1__create.sql", "V2__alter.sql"],
            str(migrations),
        )
        assert len(result) == 2
        assert all(Path(p).suffix == ".sql" for p in result)

    def test_filters_out_non_sql_files(self, tmp_path: Path) -> None:
        migrations = tmp_path / "migrations"
        migrations.mkdir()
        (migrations / "V1__create.sql").write_text("")
        (migrations / "README.md").write_text("")

        result = filter_sql_files(
            ["V1__create.sql", "README.md", "config.yml"],
            str(migrations),
        )
        assert result == [str((migrations / "V1__create.sql").resolve())]

    def test_filters_out_files_outside_migrations_dir(self, tmp_path: Path) -> None:
        migrations = tmp_path / "migrations"
        migrations.mkdir()
        outside = tmp_path / "outside.sql"
        outside.write_text("")

        result = filter_sql_files(
            ["../outside.sql"],
            str(migrations),
        )
        assert result == []

    def test_ignores_nonexistent_files(self, tmp_path: Path) -> None:
        migrations = tmp_path / "migrations"
        migrations.mkdir()
        (migrations / "V1__real.sql").write_text("")

        result = filter_sql_files(
            ["V1__real.sql", "V2__missing.sql"],
            str(migrations),
        )
        assert len(result) == 1
        assert "V2__missing.sql" not in result[0]

    def test_case_insensitive_sql_extension(self, tmp_path: Path) -> None:
        migrations = tmp_path / "migrations"
        migrations.mkdir()
        (migrations / "V1__data.SQL").write_text("")
        (migrations / "V2__data.Sql").write_text("")

        result = filter_sql_files(
            ["V1__data.SQL", "V2__data.Sql"],
            str(migrations),
        )
        assert len(result) == 2

    def test_empty_changed_files(self, tmp_path: Path) -> None:
        migrations = tmp_path / "migrations"
        migrations.mkdir()
        result = filter_sql_files([], str(migrations))
        assert result == []

    def test_path_traversal_attempt(self, tmp_path: Path) -> None:
        migrations = tmp_path / "migrations"
        migrations.mkdir()
        (tmp_path / "evil.sql").write_text("")

        result = filter_sql_files(
            ["../../evil.sql"],
            str(migrations),
        )
        assert result == []


# ── get_diff_files ──────────────────────────────────────────────────────

class TestGetDiffFiles:
    def test_integration_happy_path(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        migrations = tmp_path / "migrations"
        migrations.mkdir()
        (migrations / "V1__create.sql").write_text("create table foo (id int);")

        with mock.patch("sqlfy.commands._git_diff.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["git", "diff"],
                returncode=0,
                stdout="V1__create.sql\n",
                stderr="",
            )
            result = get_diff_files(str(migrations), ref="HEAD~1")

        expected = str((migrations / "V1__create.sql").resolve())
        assert result == [expected]

    def test_no_git_dir_raises(self, tmp_path: Path) -> None:
        migrations = tmp_path / "migrations"
        migrations.mkdir()

        with pytest.raises(RuntimeError, match="Could not find a git repository"):
            get_diff_files(str(migrations), ref="HEAD~1")

    def test_no_sql_files_in_diff(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        migrations = tmp_path / "migrations"
        migrations.mkdir()

        with mock.patch("sqlfy.commands._git_diff.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["git", "diff"],
                returncode=0,
                stdout="README.md\nconfig.yml\n",
                stderr="",
            )
            result = get_diff_files(str(migrations), ref="HEAD~1")
        assert result == []

    def test_staged_mode(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        migrations = tmp_path / "migrations"
        migrations.mkdir()
        (migrations / "V1__staged.sql").write_text("create table bar (id int);")

        with mock.patch("sqlfy.commands._git_diff.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["git", "diff"],
                returncode=0,
                stdout="V1__staged.sql\n",
                stderr="",
            )
            result = get_diff_files(str(migrations), ref=None)

        assert len(result) == 1
        assert "V1__staged.sql" in result[0]
        args = mock_run.call_args[0][0]
        assert "--cached" in args


# ── extract_tables_from_sql ─────────────────────────────────────────────

CREATE_SQL = "create table foo (id int);"
ALTER_SQL = "alter table bar add (name varchar2(100));"
DROP_SQL = "drop table baz;"
CREATE_IF_NOT_EXISTS = "create table if not exists qux (id int);"
MULTI_STMT = """
create table orders (id int primary key);
alter table line_items add (order_id int);
drop table old_archive;
"""
NON_DDL = "select * from users;"
SCHEMA_PREFIXED = "create table app.users (id int);"


class TestExtractTablesFromSql:
    def test_create_table(self, tmp_path: Path) -> None:
        f = tmp_path / "test.sql"
        f.write_text(CREATE_SQL)
        assert extract_tables_from_sql(str(f), dialect="oracle") == {"FOO"}

    def test_alter_table(self, tmp_path: Path) -> None:
        f = tmp_path / "test.sql"
        f.write_text(ALTER_SQL)
        assert extract_tables_from_sql(str(f), dialect="oracle") == {"BAR"}

    def test_drop_table(self, tmp_path: Path) -> None:
        f = tmp_path / "test.sql"
        f.write_text(DROP_SQL)
        assert extract_tables_from_sql(str(f), dialect="oracle") == {"BAZ"}

    def test_create_if_not_exists(self, tmp_path: Path) -> None:
        f = tmp_path / "test.sql"
        f.write_text(CREATE_IF_NOT_EXISTS)
        assert extract_tables_from_sql(str(f), dialect="oracle") == {"QUX"}

    def test_multi_statement(self, tmp_path: Path) -> None:
        f = tmp_path / "test.sql"
        f.write_text(MULTI_STMT)
        assert extract_tables_from_sql(str(f), dialect="oracle") == {"ORDERS", "LINE_ITEMS", "OLD_ARCHIVE"}

    def test_non_ddl_ignored(self, tmp_path: Path) -> None:
        f = tmp_path / "test.sql"
        f.write_text(NON_DDL)
        assert extract_tables_from_sql(str(f), dialect="oracle") == set()

    def test_schema_prefixed(self, tmp_path: Path) -> None:
        f = tmp_path / "test.sql"
        f.write_text(SCHEMA_PREFIXED)
        assert extract_tables_from_sql(str(f), dialect="oracle") == {"APP.USERS"}

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.sql"
        f.write_text("")
        assert extract_tables_from_sql(str(f), dialect="oracle") == set()

    def test_sql_with_comments(self, tmp_path: Path) -> None:
        f = tmp_path / "test.sql"
        f.write_text("-- comment\ncreate table comments_test (id int);")
        assert extract_tables_from_sql(str(f), dialect="oracle") == {"COMMENTS_TEST"}

    def test_invalid_sql_does_not_crash(self, tmp_path: Path) -> None:
        f = tmp_path / "test.sql"
        f.write_text("this is not valid sql {{{ }}")
        assert extract_tables_from_sql(str(f), dialect="oracle") == set()

    def test_file_not_found(self) -> None:
        assert extract_tables_from_sql("/nonexistent/path.sql", dialect="oracle") == set()


# ── extract_tables_from_diff ────────────────────────────────────────────

class TestExtractTablesFromDiff:
    def test_returns_table_per_file(self, tmp_path: Path) -> None:
        f1 = tmp_path / "V1__a.sql"
        f1.write_text("create table a (id int);")
        f2 = tmp_path / "V2__b.sql"
        f2.write_text("alter table b add (x int);")

        result = extract_tables_from_diff([str(f1), str(f2)], dialect="oracle")
        assert result == {str(f1): {"A"}, str(f2): {"B"}}

    def test_skips_files_with_no_ddl(self, tmp_path: Path) -> None:
        f = tmp_path / "V1__select.sql"
        f.write_text("select 1 from dual;")
        result = extract_tables_from_diff([str(f)], dialect="oracle")
        assert result == {}

    def test_empty_file_list(self) -> None:
        assert extract_tables_from_diff([], dialect="oracle") == {}

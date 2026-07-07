"""Tests for git hook management commands."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from sqlfy.commands.hooks import (
    MARKER_END,
    MARKER_START,
    cmd_hooks_install,
    cmd_hooks_status,
    cmd_hooks_uninstall,
)


class TestHooksInstall:
    """Tests for sqlfy hooks install command."""

    def test_install_creates_hook_with_markers(self, tmp_path: Path) -> None:
        """Verify install creates pre-commit hook with marker strings."""
        git_dir = tmp_path / ".git" / "hooks"
        git_dir.mkdir(parents=True)

        result = cmd_hooks_install(path=str(tmp_path))

        assert result == 0
        hook_file = tmp_path / ".git" / "hooks" / "pre-commit"
        assert hook_file.exists()
        content = hook_file.read_text()
        assert MARKER_START in content
        assert MARKER_END in content

    def test_install_is_idempotent(self, tmp_path: Path) -> None:
        """Verify running install twice does not duplicate the hook block."""
        git_dir = tmp_path / ".git" / "hooks"
        git_dir.mkdir(parents=True)

        # First install
        result1 = cmd_hooks_install(path=str(tmp_path))
        assert result1 == 0

        # Second install
        result2 = cmd_hooks_install(path=str(tmp_path))
        assert result2 == 0

        hook_file = tmp_path / ".git" / "hooks" / "pre-commit"
        content = hook_file.read_text()
        # Marker should appear exactly once
        assert content.count(MARKER_START) == 1
        assert content.count(MARKER_END) == 1

    def test_install_preserves_existing_hook_content(self, tmp_path: Path) -> None:
        """Verify install appends to existing hook without overwriting."""
        git_dir = tmp_path / ".git" / "hooks"
        git_dir.mkdir(parents=True)

        hook_file = git_dir / "pre-commit"
        existing_content = "#!/bin/bash\necho 'Existing hook'\n"
        hook_file.write_text(existing_content)

        result = cmd_hooks_install(path=str(tmp_path))
        assert result == 0

        content = hook_file.read_text()
        assert existing_content in content
        assert MARKER_START in content

    def test_install_raises_error_when_no_git_directory(self, tmp_path: Path) -> None:
        """Verify install returns error code when no .git directory exists."""
        # Create a directory without .git
        nogit_dir = tmp_path / "nogit"
        nogit_dir.mkdir()

        result = cmd_hooks_install(path=str(nogit_dir))
        assert result == 1


class TestHooksUninstall:
    """Tests for sqlfy hooks uninstall command."""

    def test_uninstall_removes_hook_block(self, tmp_path: Path) -> None:
        """Verify uninstall removes the sqlfy marker block."""
        git_dir = tmp_path / ".git" / "hooks"
        git_dir.mkdir(parents=True)

        # First install
        cmd_hooks_install(path=str(tmp_path))

        # Then uninstall
        result = cmd_hooks_uninstall(path=str(tmp_path))
        assert result == 0

        hook_file = tmp_path / ".git" / "hooks" / "pre-commit"
        if hook_file.exists():
            content = hook_file.read_text()
            assert MARKER_START not in content
            assert MARKER_END not in content

    def test_uninstall_is_idempotent(self, tmp_path: Path) -> None:
        """Verify running uninstall twice succeeds without error."""
        git_dir = tmp_path / ".git" / "hooks"
        git_dir.mkdir(parents=True)

        # First uninstall (nothing installed)
        result1 = cmd_hooks_uninstall(path=str(tmp_path))
        assert result1 == 0

        # Second uninstall
        result2 = cmd_hooks_uninstall(path=str(tmp_path))
        assert result2 == 0

    def test_uninstall_preserves_surrounding_content(self, tmp_path: Path) -> None:
        """Verify uninstall preserves content outside the marker block."""
        git_dir = tmp_path / ".git" / "hooks"
        git_dir.mkdir(parents=True)

        hook_file = git_dir / "pre-commit"
        before_marker = "#!/bin/bash\necho 'Before'\n"
        after_marker = "echo 'After'\n"
        initial_content = f"{before_marker}{MARKER_START}\nhook body\n{MARKER_END}\n{after_marker}"
        hook_file.write_text(initial_content)

        result = cmd_hooks_uninstall(path=str(tmp_path))
        assert result == 0

        content = hook_file.read_text()
        assert before_marker in content
        assert after_marker in content
        assert MARKER_START not in content
        assert MARKER_END not in content


class TestHooksStatus:
    """Tests for sqlfy hooks status command."""

    def test_status_reports_installed(self, tmp_path: Path) -> None:
        """Verify status reports hook as installed after install."""
        git_dir = tmp_path / ".git" / "hooks"
        git_dir.mkdir(parents=True)

        cmd_hooks_install(path=str(tmp_path))
        result = cmd_hooks_status(path=str(tmp_path))

        assert result == 0

    def test_status_reports_not_installed(self, tmp_path: Path) -> None:
        """Verify status reports hook as not installed when absent."""
        git_dir = tmp_path / ".git" / "hooks"
        git_dir.mkdir(parents=True)

        result = cmd_hooks_status(path=str(tmp_path))
        assert result == 0

    def test_status_reports_not_installed_when_file_missing(self, tmp_path: Path) -> None:
        """Verify status handles missing hook file gracefully."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir(parents=True)
        # Don't create hooks directory

        result = cmd_hooks_status(path=str(tmp_path))
        assert result == 0

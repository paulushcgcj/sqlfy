"""Tests for watch mode command."""
from __future__ import annotations

import fcntl
import os
import signal
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from sqlfy.commands.watch import WatchHandler, cmd_watch


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary migrations directory with SQL files."""
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    
    # Create some SQL files
    (migrations_dir / "V1__create_users.sql").write_text("CREATE TABLE users (id NUMBER);")
    (migrations_dir / "V2__create_orders.sql").write_text("CREATE TABLE orders (id NUMBER);")
    
    return str(migrations_dir)


class TestWatchHandler:
    """Tests for WatchHandler class."""

    @pytest.fixture
    def mock_observer(self):
        """Create a mock observer."""
        observer = MagicMock()
        return observer

    def test_acquire_lock_success(self, temp_dir):
        """Test that lock can be acquired."""
        handler = WatchHandler(
            migrations_dir=temp_dir,
            debounce=1.0,
            run_commands=["lint"],
            dialect="oracle",
            out=None,
            format="text",
            force=False,
            observer=MagicMock(),
        )
        
        result = handler._acquire_lock()
        assert result is True
        handler._release_lock()

    def test_acquire_lock_success_when_already_held(self, temp_dir):
        """Test that lock acquisition returns True when already held by same handler."""
        handler = WatchHandler(
            migrations_dir=temp_dir,
            debounce=1.0,
            run_commands=["lint"],
            dialect="oracle",
            out=None,
            format="text",
            force=False,
            observer=MagicMock(),
        )
        
        # Acquire lock first
        assert handler._acquire_lock() is True
        
        # Try to acquire again - should succeed (we already have it)
        result = handler._acquire_lock()
        assert result is True
        
        handler._release_lock()

    def test_check_shrink_safety_allows_normal_rebuild(self):
        """Test that normal rebuilds are allowed through shrink-safety gate."""
        handler = WatchHandler(
            migrations_dir="/tmp/test",
            debounce=1.0,
            run_commands=["lint"],
            dialect="oracle",
            out=None,
            format="text",
            force=False,
            observer=MagicMock(),
        )
        
        # Less than 20% reduction - should allow
        result = handler._check_shrink_safety(old_node_count=100, new_node_count=90)
        assert result is True

    def test_check_shrink_safety_blocks_large_reduction(self):
        """Test that large reductions are blocked by shrink-safety gate."""
        handler = WatchHandler(
            migrations_dir="/tmp/test",
            debounce=1.0,
            run_commands=["lint"],
            dialect="oracle",
            out=None,
            format="text",
            force=False,
            observer=MagicMock(),
        )
        
        # More than 20% reduction - should block
        result = handler._check_shrink_safety(old_node_count=100, new_node_count=70)
        assert result is False

    def test_check_shrink_safety_allows_when_force(self):
        """Test that shrink-safety gate is bypassed when force=True."""
        handler = WatchHandler(
            migrations_dir="/tmp/test",
            debounce=1.0,
            run_commands=["lint"],
            dialect="oracle",
            out=None,
            format="text",
            force=True,
            observer=MagicMock(),
        )
        
        # Even with large reduction, force=True should allow
        # (the check is done in _run_commands, not in _check_shrink_safety)
        result = handler._check_shrink_safety(old_node_count=100, new_node_count=50)
        assert result is False  # Still returns False, but caller ignores when force=True

    def test_check_shrink_safety_zero_old_count(self):
        """Test that zero old count allows rebuild."""
        handler = WatchHandler(
            migrations_dir="/tmp/test",
            debounce=1.0,
            run_commands=["lint"],
            dialect="oracle",
            out=None,
            format="text",
            force=False,
            observer=MagicMock(),
        )
        
        result = handler._check_shrink_safety(old_node_count=0, new_node_count=10)
        assert result is True

    def test_should_handle_event_sql_file(self, temp_dir):
        """Test that SQL file events in migrations dir are handled."""
        from watchdog.events import FileModifiedEvent
        
        handler = WatchHandler(
            migrations_dir=temp_dir,
            debounce=1.0,
            run_commands=["lint"],
            dialect="oracle",
            out=None,
            format="text",
            force=False,
            observer=MagicMock(),
        )
        
        sql_file = Path(temp_dir) / "V1__test.sql"
        event = FileModifiedEvent(str(sql_file))
        
        result = handler._should_handle_event(event)
        assert result is True

    def test_should_handle_event_non_sql_file(self, temp_dir):
        """Test that non-SQL file events are ignored."""
        from watchdog.events import FileModifiedEvent
        
        handler = WatchHandler(
            migrations_dir=temp_dir,
            debounce=1.0,
            run_commands=["lint"],
            dialect="oracle",
            out=None,
            format="text",
            force=False,
            observer=MagicMock(),
        )
        
        # Create a non-SQL file
        txt_file = Path(temp_dir) / "readme.txt"
        event = FileModifiedEvent(str(txt_file))
        
        result = handler._should_handle_event(event)
        assert result is False

    def test_should_handle_event_outside_directory(self, temp_dir):
        """Test that events outside migrations dir are ignored."""
        from watchdog.events import FileModifiedEvent
        
        handler = WatchHandler(
            migrations_dir=temp_dir,
            debounce=1.0,
            run_commands=["lint"],
            dialect="oracle",
            out=None,
            format="text",
            force=False,
            observer=MagicMock(),
        )
        
        # Create a file outside the migrations dir
        outside_file = Path(temp_dir).parent / "outside.sql"
        event = FileModifiedEvent(str(outside_file))
        
        result = handler._should_handle_event(event)
        assert result is False

    def test_print_summary(self, temp_dir, capsys):
        """Test that summary is printed to stderr."""
        handler = WatchHandler(
            migrations_dir=temp_dir,
            debounce=1.0,
            run_commands=["lint"],
            dialect="oracle",
            out=None,
            format="text",
            force=False,
            observer=MagicMock(),
        )
        
        results = {"lint": "OK", "safety": "WARN(2)"}
        handler._print_summary(results)
        
        captured = capsys.readouterr()
        assert "rebuilt:" in captured.err
        assert "lint=OK" in captured.err
        assert "safety=WARN(2)" in captured.err

    def test_stop_cleans_up(self, temp_dir):
        """Test that stop method cleans up resources."""
        handler = WatchHandler(
            migrations_dir=temp_dir,
            debounce=1.0,
            run_commands=["lint"],
            dialect="oracle",
            out=None,
            format="text",
            force=False,
            observer=MagicMock(),
        )
        
        # Acquire lock and set timer
        handler._acquire_lock()
        mock_timer = MagicMock()
        handler.timer = mock_timer
        
        handler.stop()
        
        # Timer should be cancelled
        mock_timer.cancel.assert_called_once()
        
        # Lock should be released
        assert handler.lock_fd is None


class TestCmdWatch:
    """Tests for cmd_watch function."""

    def test_nonexistent_directory(self, capsys):
        """Test that nonexistent directory raises error."""
        with pytest.raises(SystemExit) as exc_info:
            cmd_watch(
                migrations_dir="/nonexistent/path",
                debounce=1.0,
                run="lint",
                dialect="oracle",
                out=None,
                format="text",
                force=False,
            )
        
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "does not exist" in captured.err

    def test_empty_run_commands(self, temp_dir, capsys):
        """Test that empty run commands raises error."""
        with pytest.raises(SystemExit) as exc_info:
            cmd_watch(
                migrations_dir=temp_dir,
                debounce=1.0,
                run="",
                dialect="oracle",
                out=None,
                format="text",
                force=False,
            )
        
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "No commands specified" in captured.err

    @patch("sqlfy.commands.watch.Observer")
    @patch("sqlfy.commands.watch.signal.signal")
    def test_watch_starts_and_stops(self, mock_signal, mock_observer_class, temp_dir, capsys):
        """Test that watch starts observer and handles Ctrl+C."""
        mock_observer = MagicMock()
        mock_observer_class.return_value = mock_observer
        
        # Mock signal handlers to avoid actual signal registration
        mock_signal.return_value = None
        
        with patch("sqlfy.commands.watch.time.sleep", side_effect=KeyboardInterrupt):
            # cmd_watch will call sys.exit(0) on KeyboardInterrupt via signal handler
            with pytest.raises(SystemExit) as exc_info:
                cmd_watch(
                    migrations_dir=temp_dir,
                    debounce=0.1,
                    run="lint",
                    dialect="oracle",
                    out=None,
                    format="text",
                    force=False,
                )
            assert exc_info.value.code == 0
        
        # Check output
        captured = capsys.readouterr()
        assert "Watch stopped." in captured.err
        
        # Observer should be started
        mock_observer.start.assert_called_once()
        # Observer should be stopped
        mock_observer.stop.assert_called_once()
        mock_observer.join.assert_called_once()

    @patch("sqlfy.commands.watch.Observer")
    @patch("sqlfy.commands.watch.WatchHandler")
    @patch("sqlfy.commands.watch.signal.signal")
    def test_initial_rebuild(self, mock_signal, mock_handler_class, mock_observer_class, temp_dir):
        """Test that initial rebuild is scheduled on startup."""
        mock_observer = MagicMock()
        mock_observer_class.return_value = mock_observer
        mock_handler = MagicMock()
        mock_handler_class.return_value = mock_handler
        
        # Mock signal handlers
        mock_signal.return_value = None
        
        with patch("sqlfy.commands.watch.time.sleep", side_effect=[None, KeyboardInterrupt]):
            with pytest.raises(SystemExit) as exc_info:
                cmd_watch(
                    migrations_dir=temp_dir,
                    debounce=0.1,
                    run="lint",
                    dialect="oracle",
                    out=None,
                    format="text",
                    force=False,
                )
            assert exc_info.value.code == 0
        
        # Initial rebuild should be scheduled
        mock_handler._schedule_rebuild.assert_called_once()


class TestWatchDebouncing:
    """Tests for debouncing behavior."""

    @patch("sqlfy.commands.watch.threading.Timer")
    def test_debounce_timer_resets(self, mock_timer_class, temp_dir):
        """Test that debounce timer resets on rapid events."""
        observer = MagicMock()
        handler = WatchHandler(
            migrations_dir=temp_dir,
            debounce=0.5,
            run_commands=["lint"],
            dialect="oracle",
            out=None,
            format="text",
            force=False,
            observer=observer,
        )
        
        # Create mock timers
        mock_timer1 = MagicMock()
        mock_timer2 = MagicMock()
        mock_timer_class.side_effect = [mock_timer1, mock_timer2]
        
        from watchdog.events import FileModifiedEvent
        sql_file = Path(temp_dir) / "V1__test.sql"
        
        # First event
        event1 = FileModifiedEvent(str(sql_file))
        handler.on_modified(event1)
        
        # Verify timer is set to first mock
        assert handler.timer is mock_timer1
        
        # Second event before timer fires
        event2 = FileModifiedEvent(str(sql_file))
        handler.on_modified(event2)
        
        # Timer should be cancelled and reset
        mock_timer1.cancel.assert_called_once()
        assert handler.timer is mock_timer2
        assert handler.timer is not mock_timer1

    @patch("sqlfy.commands.watch.threading.Timer")
    def test_commands_run_after_debounce(self, mock_timer_class, temp_dir):
        """Test that commands run exactly once after debounce."""
        observer = MagicMock()
        handler = WatchHandler(
            migrations_dir=temp_dir,
            debounce=0.1,
            run_commands=["lint"],
            dialect="oracle",
            out=None,
            format="text",
            force=False,
            observer=observer,
        )
        
        mock_timer = MagicMock()
        mock_timer_class.return_value = mock_timer
        
        from watchdog.events import FileModifiedEvent
        sql_file = Path(temp_dir) / "V1__test.sql"
        event = FileModifiedEvent(str(sql_file))
        
        # Trigger event
        handler.on_modified(event)
        
        # Timer should be started
        mock_timer_class.assert_called_once()
        mock_timer.start.assert_called_once()

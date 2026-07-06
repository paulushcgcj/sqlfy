"""Watch mode command: auto-rebuild analysis on migration file changes."""
from __future__ import annotations

import fcntl
import signal
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer


class WatchHandler(FileSystemEventHandler):
    """File system event handler for watch mode."""

    def __init__(
        self,
        migrations_dir: str,
        debounce: float,
        run_commands: list[str],
        dialect: str,
        out: str | None,
        format: str,
        force: bool,
        observer: Observer,
    ):
        self.migrations_dir = migrations_dir
        self.debounce = debounce
        self.run_commands = run_commands
        self.dialect = dialect
        self.out = out
        self.format = format
        self.force = force
        self.observer = observer
        self.timer: threading.Timer | None = None
        self.lock_fd = None
        self.lock_path = Path(migrations_dir) / ".sqlfy.watch.lock"
        self._stop_event = threading.Event()

    def _acquire_lock(self) -> bool:
        """Acquire advisory lock. Returns True if acquired, False if already locked."""
        # If we already have the lock, return True
        if self.lock_fd is not None:
            return True
        
        try:
            self.lock_fd = open(self.lock_path, "w")
            fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (IOError, OSError):
            self.lock_fd = None
            return False

    def _release_lock(self) -> None:
        """Release advisory lock."""
        if self.lock_fd is not None:
            try:
                fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_UN)
                self.lock_fd.close()
            except (IOError, OSError):
                pass
            finally:
                self.lock_fd = None

    def _check_shrink_safety(self, old_node_count: int, new_node_count: int) -> bool:
        """Check if shrink-safety gate should abort rebuild."""
        if old_node_count <= 0:
            return True  # No previous data, allow rebuild
        if new_node_count < (old_node_count * 0.80):
            reduction_percent = ((old_node_count - new_node_count) / old_node_count) * 100
            print(
                f"Warning: Shrink-safety gate triggered! Graph would shrink by "
                f"{reduction_percent:.1f}% ({old_node_count} -> {new_node_count} nodes). "
                f"Use --force to override.",
                file=sys.stderr,
            )
            return False
        return True

    def _get_node_count(self, migrations_dir: str, dialect: str) -> int:
        """Get the number of nodes in the schema graph."""
        try:
            from ..reconstructor import reconstruct

            state = reconstruct(str(Path(migrations_dir)))
            return len(state.graph.tables) + len(state.graph.sequences)
        except Exception:
            return 0

    def _run_commands(self) -> dict[str, str]:
        """Run all configured commands and return their status."""
        results = {}
        migrations_dir_path = Path(self.migrations_dir)

        # Get old node count for shrink-safety check
        old_node_count = 0
        try:
            old_node_count = self._get_node_count(self.migrations_dir, self.dialect)
        except Exception:
            pass

        for cmd_name in self.run_commands:
            try:
                status = self._execute_command(cmd_name)
                results[cmd_name] = status
            except Exception as e:
                results[cmd_name] = f"ERROR({str(e)})"

        # Check shrink-safety after rebuild
        new_node_count = self._get_node_count(self.migrations_dir, self.dialect)
        if not self.force and not self._check_shrink_safety(old_node_count, new_node_count):
            # Rollback: restore old artifacts if possible
            results["shrink_safety"] = "ABORTED"

        return results

    def _execute_command(self, cmd_name: str) -> str:
        """Execute a single command and return its status."""
        from . import (
            cmd_insights,
            cmd_lint,
            cmd_safety,
        )

        command_map = {
            "lint": cmd_lint,
            "safety": cmd_safety,
            "insights": cmd_insights,
        }

        if cmd_name not in command_map:
            return f"UNKNOWN({cmd_name})"

        cmd_func = command_map[cmd_name]

        try:
            # Execute the command - capture stdout/stderr
            # We need to redirect to prevent double output
            import io
            from contextlib import redirect_stdout, redirect_stderr

            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()

            # Build kwargs for the command
            # lint uses 'path' parameter, others use 'migrations_dir'
            if cmd_name == "lint":
                kwargs = {
                    "path": self.migrations_dir,
                    "dialect": self.dialect,
                    "format": self.format,
                }
            else:
                kwargs = {
                    "migrations_dir": self.migrations_dir,
                    "dialect": self.dialect,
                    "format": self.format,
                }

            if self.out:
                kwargs["out"] = self.out

            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                cmd_func(**kwargs)

            # Command succeeded if it didn't raise an exception
            return "OK"

        except SystemExit as e:
            # Command exited with a code - check if it was an error
            if e.code != 0:
                return f"FAIL({e.code})"
            return "OK"
        except Exception as e:
            return f"ERROR({str(e)})"

    def _print_summary(self, results: dict[str, str]) -> None:
        """Print timestamped summary to stderr."""
        now = datetime.now().strftime("%H:%M:%S")
        summary_parts = [f"{k}={v}" for k, v in results.items()]
        summary = ", ".join(summary_parts)
        print(f"[{now}] rebuilt: {summary}", file=sys.stderr)

    def _schedule_rebuild(self) -> None:
        """Schedule a rebuild after debounce period."""
        if self.timer is not None:
            self.timer.cancel()

        def rebuild() -> None:
            if self._stop_event.is_set():
                return

            # Check if lock is available
            if not self._acquire_lock():
                print(
                    f"Warning: Rebuild already in progress, skipping.",
                    file=sys.stderr,
                )
                return

            try:
                results = self._run_commands()
                self._print_summary(results)
            finally:
                self._release_lock()

        self.timer = threading.Timer(self.debounce, rebuild)
        self.timer.start()

    def on_modified(self, event: FileModifiedEvent) -> None:
        """Handle file modification events."""
        if self._should_handle_event(event):
            self._schedule_rebuild()

    def on_created(self, event: FileCreatedEvent) -> None:
        """Handle file creation events."""
        if self._should_handle_event(event):
            self._schedule_rebuild()

    def on_moved(self, event: FileMovedEvent) -> None:
        """Handle file move events."""
        if self._should_handle_event(event):
            self._schedule_rebuild()

    def on_deleted(self, event: FileDeletedEvent) -> None:
        """Handle file deletion events."""
        if self._should_handle_event(event):
            self._schedule_rebuild()

    def _should_handle_event(self, event: FileSystemEventHandler) -> bool:
        """Check if event should trigger a rebuild."""
        if not event.is_directory:
            path = Path(event.src_path)
            if path.suffix.lower() == ".sql":
                # Check if the file is in our migrations directory
                migrations_path = Path(self.migrations_dir)
                try:
                    path.relative_to(migrations_path)
                    return True
                except ValueError:
                    pass
        return False

    def stop(self) -> None:
        """Stop the watch handler."""
        self._stop_event.set()
        if self.timer is not None:
            self.timer.cancel()
        self._release_lock()


def cmd_watch(
    migrations_dir: str,
    debounce: float = 2.0,
    run: str = "lint,safety,insights",
    dialect: str = "oracle",
    out: str | None = None,
    format: str = "text",
    force: bool = False,
    json_input: str | None = None,
    at: str | None = None,
) -> None:
    """Watch migration files and auto-rebuild analysis on changes.
    
    Args:
        migrations_dir: Path to directory containing migration files
        debounce: Debounce time in seconds (default: 2.0)
        run: Comma-separated list of commands to run (default: "lint,safety,insights")
        dialect: SQL dialect (oracle, postgres, mysql, sqlite)
        out: Optional output directory for artifacts
        format: Output format (text, json)
        force: Force rebuild even if shrink-safety gate is triggered
    """
    import os

    # Resolve migrations_dir to absolute path
    migrations_dir = os.path.abspath(migrations_dir)

    # Validate migrations_dir exists
    if not os.path.isdir(migrations_dir):
        print(f"Error: Migrations directory does not exist: {migrations_dir}", file=sys.stderr)
        sys.exit(1)

    # Parse run commands
    run_commands = [cmd.strip() for cmd in run.split(",") if cmd.strip()]
    if not run_commands:
        print("Error: No commands specified to run", file=sys.stderr)
        sys.exit(1)

    # Set up signal handlers
    stop_event = threading.Event()

    def signal_handler(signum, frame) -> None:
        print("Watch stopped.", file=sys.stderr)
        stop_event.set()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create observer
    observer = Observer()

    # Create and configure handler
    handler = WatchHandler(
        migrations_dir=migrations_dir,
        debounce=debounce,
        run_commands=run_commands,
        dialect=dialect,
        out=out,
        format=format,
        force=force,
        observer=observer,
    )

    # Schedule initial rebuild
    observer.schedule(handler, path=migrations_dir, recursive=False)
    observer.start()

    print(f"Watching {migrations_dir} for .sql file changes...", file=sys.stderr)
    print("Press Ctrl+C to stop.", file=sys.stderr)

    # Run initial rebuild
    handler._schedule_rebuild()

    try:
        while not stop_event.is_set():
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Watch stopped.", file=sys.stderr)
        sys.exit(0)
    finally:
        handler.stop()
        observer.stop()
        observer.join()
        print("Watch stopped.", file=sys.stderr)

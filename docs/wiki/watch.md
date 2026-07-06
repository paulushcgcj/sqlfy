# Watch Mode

`sqlfy watch` is a command that monitors migration files for changes and automatically re-runs analysis commands, providing instant feedback on schema health, lint violations, and safety issues.

## Features

- **Automatic rebuilds**: Automatically detects changes to `.sql` files and re-runs configured commands
- **Debouncing**: Configurable debounce period to prevent rapid rebuilds on multiple file changes
- **Concurrent rebuild protection**: Advisory locking prevents overlapping rebuilds
- **Shrink-safety gate**: Protects against accidental large schema reductions (>20% node loss)
- **Timestamped output**: Clear timestamped summaries of rebuild results
- **Graceful shutdown**: Handles Ctrl+C cleanly with proper cleanup

## Installation

The watch command is included in the sqlfy CLI package. Ensure you have sqlfy installed with watchdog:

```bash
# From the repository root
cd cli
pip install -e ".[dev]"

# Or install globally
pip install sqlfy
```

> **Note**: The watch command requires the `watchdog` package, which is included as a dependency in sqlfy.

## Usage

### Basic Usage

```bash
# Watch a migrations directory and run default commands (lint, safety, insights)
sqlfy watch ./migrations/

# Watch with custom debounce time
sqlfy watch ./migrations/ --debounce 1.0

# Watch with specific commands
sqlfy watch ./migrations/ --run lint,safety

# Watch with all commands
sqlfy watch ./migrations/ --run lint,safety,insights,health,validate
```

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--debounce SECONDS` | Debounce time in seconds before rebuild | `2.0` |
| `--run COMMANDS` | Comma-separated list of commands to run | `lint,safety,insights` |
| `--dialect DIALECT` | SQL dialect (oracle, postgres, mysql, sqlite) | `oracle` |
| `--out FILE` | Output file for command results | `None` (stdout) |
| `--format FORMAT` | Output format (text, json) | `text` |
| `--force` | Force rebuild even if shrink-safety gate is triggered | `False` |

### Available Commands

The following commands can be specified with `--run`:

- `lint` - Lint migration SQL files for quality and style
- `safety` - Score migrations by safety level
- `insights` - Analyse schema and report insights
- `health` - Generate migration folder health report
- `validate` - Validate migration ordering and detect issues
- `deps` - Analyze migration dependencies
- `stability` - Calculate schema stability metrics

### Examples

```bash
# Run lint and safety commands with short debounce
sqlfy watch ./migrations/ --run lint,safety --debounce 0.5

# Run insights with JSON output
sqlfy watch ./migrations/ --run insights --format json

# Force rebuild even with shrink-safety warnings
sqlfy watch ./migrations/ --run lint,safety,insights --force

# Use with PostgreSQL dialect
sqlfy watch ./migrations/ --dialect postgres --run lint,safety
```

## How It Works

### Algorithm

1. **Resolve Path**: Migrations directory is resolved to an absolute path
2. **Validate**: Check that the directory exists
3. **Setup Watcher**: Create file system observer using watchdog
4. **Register Handlers**: Watch for file events on `.sql` files
5. **Start Observer**: Begin monitoring the directory
6. **Initial Rebuild**: Run commands immediately on startup
7. **Event Loop**: Wait for file changes...
8. **On Event**: Schedule rebuild after debounce period
9. **Rebuild**: Acquire lock, run commands, print summary, release lock
10. **Cleanup**: Stop observer on SIGINT/SIGTERM

### File Events

The watcher responds to the following file system events:

- `FileModifiedEvent` - File content changed
- `FileCreatedEvent` - New file created
- `FileMovedEvent` - File moved/renamed
- `FileDeletedEvent` - File deleted

Only `.sql` files within the migrations directory trigger rebuilds.

### Debouncing

To prevent excessive rebuilds when multiple files change rapidly, the watcher uses a debounce mechanism:

```
Event 1 ---[0.1s]---> Event 2 ---[0.1s]---> Event 3 ---[debounce=2.0s]---> Rebuild
                                                                  ^
                                                                  |
                                                                  +-- Commands run once after debounce period
```

If events arrive within the debounce window, the timer is reset.

### Advisory Locking

To prevent overlapping rebuilds (e.g., if the watcher is running in multiple terminals), the command uses file-based advisory locking:

- Lock file: `<migrations_dir>/.sqlfy.watch.lock`
- Uses `fcntl.flock` with `LOCK_EX | LOCK_NB`
- If lock is held, new rebuilds are skipped with a warning message

### Shrink-Safety Gate

The shrink-safety gate protects against accidental large schema reductions (e.g., a `DROP TABLE` statement that removes many tables):

- Compares node count before and after rebuild
- If new graph has >20% fewer nodes than old graph, rebuild is aborted
- Warning is printed to stderr
- Use `--force` to override this protection

## Output Format

### Timestamped Summary

After each rebuild, a summary is printed to stderr:

```
[14:30:45] rebuilt: lint=OK safety=OK insights=WARN(2)
```

Each command status is shown as:
- `OK` - Command completed successfully
- `FAIL(N)` - Command failed with exit code N
- `ERROR(msg)` - Command raised an exception
- `ABORTED` - Shrink-safety gate triggered

### Command Output

Each command's output is written to stdout (or to the file specified by `--out`). The format depends on the command and the `--format` flag.

## Graceful Shutdown

The watcher handles the following signals:

- **SIGINT** (Ctrl+C) - Print "Watch stopped." and exit 0
- **SIGTERM** - Print "Watch stopped." and exit 0

Cleanup includes:
- Cancelling any pending rebuild timers
- Releasing advisory locks
- Stopping the file system observer
- Joining observer threads

## Best Practices

### Development Workflow

```bash
# In one terminal: watch for changes
sqlfy watch ./migrations/ --run lint,safety,insights

# In another terminal: edit migration files
# Rebuild happens automatically within 2 seconds of saving
```

### CI/CD Integration

The watch command is primarily designed for local development. For CI/CD pipelines, consider using individual commands:

```bash
# In CI, run commands explicitly
sqlfy lint ./migrations/
sqlfy safety ./migrations/
sqlfy insights ./migrations/
```

### Performance Considerations

- Use `--debounce` to balance responsiveness vs. resource usage
- Longer debounce times reduce CPU usage but delay feedback
- Shorter debounce times provide faster feedback but may cause more rebuilds
- Default 2.0 seconds is a good balance for most use cases

### Debugging

If the watcher is not detecting file changes:

1. Verify the directory path is correct
2. Check that files are `.sql` files
3. Ensure files are within the migrations directory (not subdirectories)
4. Check for permission issues
5. Try increasing the debounce time

## Troubleshooting

### "Watch stopped." appears immediately

This usually indicates that the watcher received a signal (SIGINT/SIGTERM). Check for:
- Accidental Ctrl+C
- Terminal closing
- System shutdown

### Rebuilds not triggering

Check that:
- Files are `.sql` files
- Files are in the correct directory
- Watchdog has permission to monitor the directory
- The debounce period hasn't been exceeded

### Lock warnings

If you see "Warning: Rebuild already in progress, skipping." messages:
- This means a rebuild is already running
- The lock file is at `<migrations_dir>/.sqlfy.watch.lock`
- This is normal behavior to prevent overlapping rebuilds

### Shrink-safety gate warnings

If you see "Shrink-safety gate triggered!" messages:
- A rebuild would reduce the schema graph by >20%
- This could indicate accidental `DROP TABLE` statements
- Use `--force` to override if intentional
- Check your migration files for unintended schema changes

## See Also

- [Main CLI Reference](https://github.com/paulushcgcj/sqlfy#cli-reference)
- [Lint Command](https://github.com/paulushcgcj/sqlfy/wiki) - For SQL quality checking
- [Safety Command](https://github.com/paulushcgcj/sqlfy/wiki) - For migration safety analysis
- [Insights Command](https://github.com/paulushcgcj/sqlfy/wiki) - For schema insights
- [Health Command](https://github.com/paulushcgcj/sqlfy/wiki) - For migration health reports
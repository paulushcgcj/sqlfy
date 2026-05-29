"""
sqlfy.migrations.loader
=======================
Migration file discovery and loading.

Loads Flyway-style SQL migration files from a directory or a pre-parsed
JSON input file. Integrates with the file cache for fast repeated runs.
"""

from __future__ import annotations

import sys
import json
from pathlib import Path


def load_files(
    migrations_dir: str | None,
    json_input: str | None,
    use_cache: bool = True,
) -> list[dict]:
    """Load migration files from a directory or a JSON input file.

    Args:
        migrations_dir: Path to a directory containing .sql migration files.
        json_input: Path to a JSON file containing pre-loaded migration records.
        use_cache: Whether to use the on-disk file cache for repeated loads.

    Returns:
        List of dicts with 'filename' and 'sql' keys.

    Raises:
        SystemExit: On missing path or no SQL files found.
    """
    if json_input:
        p = Path(json_input)
        if not p.is_file():
            print(f"Error: --json-input file not found: {p}", file=sys.stderr)
            sys.exit(1)
        files = json.loads(p.read_text(encoding="utf-8"))
        print(f"Loaded {len(files)} migration(s) from JSON input", file=sys.stderr)
        return files

    if migrations_dir:
        p = Path(migrations_dir)
        if not p.is_dir():
            print(f'Error: "{p}" is not a directory.', file=sys.stderr)
            sys.exit(1)
        sql_files = sorted(
            (f for f in p.rglob("*") if f.is_file() and f.suffix.lower() == ".sql"),
            key=lambda path: (path.name, str(path.relative_to(p))),
        )
        if not sql_files:
            print(f"No .sql files found in {p}", file=sys.stderr)
            sys.exit(1)

        if use_cache:
            from ..cache import load_cached, save_cached
            files = []
            cache_hits = 0
            for f in sql_files:
                cached = load_cached(f)
                if cached:
                    files.append(cached)
                    cache_hits += 1
                else:
                    sql_content = f.read_text(encoding="utf-8")
                    result = {"filename": str(f.relative_to(p)), "sql": sql_content}
                    save_cached(f, result)
                    files.append(result)
            if cache_hits > 0:
                print(f"Cache: {cache_hits}/{len(sql_files)} hits", file=sys.stderr)
        else:
            files = [
                {"filename": str(f.relative_to(p)), "sql": f.read_text(encoding="utf-8")}
                for f in sql_files
            ]

        print(f"Loaded {len(files)} migration file(s) from {p}", file=sys.stderr)
        return files

    print("Error: provide either migrations_dir or --json-input FILE", file=sys.stderr)
    sys.exit(1)

"""
sqlfy.migrations.parser
=======================
Flyway migration filename parsing utilities.

Parses V{version}__{description}.sql filenames into structured metadata
used for ordering and labeling migration history.
"""

from __future__ import annotations

import os
import re


def parse_flyway_ver(filename: str) -> dict:
    """Parse a Flyway migration filename into version metadata.

    The filename may be a bare name ('V1__create_users.sql') or a path
    ending in one ('db/migrations/V1__create_users.sql'); only the basename
    is inspected so files discovered recursively inside subdirectories
    still parse correctly.

    Args:
        filename: Flyway-style filename like 'V1__create_users.sql'.

    Returns:
        Dict with 'version' (str), 'description' (str), and 'order' (int)
        keys. Rollback (U-prefixed) files are also tagged with
        'kind': 'rollback' so forward reconstruction can skip them.
        Falls back to version '0' and order 0 if the filename does not match.
    """
    name = os.path.basename(filename)

    # Versioned forward migration: V<version>__<description>.sql
    m = re.match(r"^V([\d.]+)__(.+?)\.sql$", name, re.I)
    if m:
        parts = [int(p) for p in m.group(1).split(".")]
        order = sum(n * (1000 ** (3 - i)) for i, n in enumerate(parts))
        return {
            "version": m.group(1),
            "description": m.group(2).replace("_", " "),
            "order": order,
            "kind": "versioned",
        }

    # Rollback migration: U<version>__<description>.sql — never applied forward.
    mu = re.match(r"^U([\d.]+)__(.+?)\.sql$", name, re.I)
    if mu:
        return {
            "version": mu.group(1),
            "description": mu.group(2).replace("_", " "),
            "order": -1,
            "kind": "rollback",
        }

    # Flyway callback script (beforeMigrate.sql, afterEachMigrate.sql, ...) —
    # hooks run around migrations, never applied as a migration itself.
    if re.match(
        r"^(?:before|after|beforeEach|afterEach|beforeEachMigrateError|afterEachMigrateError)"
        r"(?:Migrate|Validate|Baseline|Repair|Info|Undo|Versioned|Repeatable|MigrateError)?\.sql$",
        name,
        re.I,
    ):
        return {
            "version": "0",
            "description": name,
            "order": 0,
            "kind": "callback",
        }

    return {"version": "0", "description": filename, "order": 0, "kind": "unknown"}

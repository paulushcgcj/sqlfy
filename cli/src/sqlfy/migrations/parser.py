"""
sqlfy.migrations.parser
=======================
Flyway migration filename parsing utilities.

Parses V{version}__{description}.sql filenames into structured metadata
used for ordering and labeling migration history.
"""

from __future__ import annotations

import re


def parse_flyway_ver(filename: str) -> dict:
    """Parse a Flyway migration filename into version metadata.

    Args:
        filename: Flyway-style filename like 'V1__create_users.sql'.

    Returns:
        Dict with 'version' (str), 'description' (str), and 'order' (int) keys.
        Falls back to version '0' and order 0 if the filename does not match.
    """
    m = re.match(r"^V([\d.]+)__(.+?)\.sql$", filename, re.I)
    if not m:
        return {"version": "0", "description": filename, "order": 0}
    parts = [int(p) for p in m.group(1).split(".")]
    order = sum(n * (1000 ** (3 - i)) for i, n in enumerate(parts))
    return {
        "version": m.group(1),
        "description": m.group(2).replace("_", " "),
        "order": order,
    }

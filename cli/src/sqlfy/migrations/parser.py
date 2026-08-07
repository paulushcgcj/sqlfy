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
    """Parse a Flyway migration filename or relative path into version metadata.

    Supports formats:
    - V1__description.sql (simple versioned)
    - V1.2.3__description.sql (multi-dot sub-versioned)
    - V1_2_3__description.sql (underscore sub-versioned)
    - R__description.sql (repeatable migration)

    Args:
        filename: Flyway-style filename or relative path like 'dir/V1.1.1__create_users.sql'.

    Returns:
        Dict with 'version' (str), 'description' (str), 'order' (tuple), and 'is_flyway' (bool) keys.
    """
    from pathlib import Path

    basename = Path(filename).name

    # Versioned migration: V<version>__<description>.sql
    m = re.match(r"^V(\d+(?:[._]\d+)*)__(.+?)\.sql$", basename, re.I)
    if m:
        ver_str = m.group(1).replace("_", ".")
        parts = [int(p) for p in ver_str.split(".")]
        return {
            "version": ver_str,
            "description": m.group(2).replace("_", " "),
            "order": (0, tuple(parts)),
            "is_flyway": True,
        }

    # Repeatable migration: R__<description>.sql
    m_r = re.match(r"^R__(.+?)\.sql$", basename, re.I)
    if m_r:
        desc = m_r.group(1).replace("_", " ")
        return {
            "version": f"R__{m_r.group(1)}",
            "description": desc,
            "order": (1, desc),
            "is_flyway": True,
        }

    # Fallback for non-Flyway filenames
    return {
        "version": filename,
        "description": filename,
        "order": (2, filename),
        "is_flyway": False,
    }


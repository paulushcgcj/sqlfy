#!/usr/bin/env python3
"""
schema/codegen.py
=================
Regenerates ``cli/src/sqlfy/models.py`` from ``schema/types.json``
using ``datamodel-codegen`` (listed in pyproject.toml dev deps).

Source of truth: schema/types.json
Generated file:  cli/src/sqlfy/models.py

Usage
-----
    # From repo root or any directory:
    python3 schema/codegen.py

    # Or via Makefile:
    make codegen-py

Requirements
------------
    pip install datamodel-code-generator  (or: uv sync --all-extras)

The generated file must NOT be hand-edited. All type changes go in
schema/types.json, then re-run this script.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_FILE = REPO_ROOT / "schema" / "types.json"
OUT_FILE = REPO_ROOT / "cli" / "src" / "sqlfy" / "models.py"

BANNER = """\
# AUTO-GENERATED — do not edit by hand.
# Source of truth: schema/types.json
# Regenerate:      python3 schema/codegen.py
#                  (or: make codegen-py)

"""


def main() -> None:
    if not SCHEMA_FILE.exists():
        print(f"ERROR: schema file not found: {SCHEMA_FILE}", file=sys.stderr)
        sys.exit(1)

    print(f"  Generating: {OUT_FILE.relative_to(REPO_ROOT)}")
    print(f"  From:       {SCHEMA_FILE.relative_to(REPO_ROOT)}")

    result = subprocess.run(
        [
            sys.executable, "-m", "datamodel_code_generator",
            "--input", str(SCHEMA_FILE),
            "--input-file-type", "jsonschema",
            "--output", str(OUT_FILE),
            "--output-model-type", "pydantic_v2.BaseModel",
            "--use-schema-description",
            "--field-constraints",
            "--snake-case-field",
            "--reuse-model",
            "--target-python-version", "3.11",
            "--disable-timestamp",
            "--allow-population-by-field-name",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("ERROR: datamodel-codegen failed:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)

    # Post-process: ensure populate_by_name=True is in every ConfigDict so
    # callers can construct models using snake_case field names OR camelCase aliases.
    import re
    content = OUT_FILE.read_text(encoding="utf-8")
    content = re.sub(
        r"ConfigDict\(\s*extra='forbid'\s*\)",
        "ConfigDict(extra='forbid', populate_by_name=True)",
        content,
    )
    content = content.replace(
        "model_config = ConfigDict(\n        extra='forbid',\n    )",
        "model_config = ConfigDict(\n        extra='forbid',\n        populate_by_name=True,\n    )",
    )
    OUT_FILE.write_text(content, encoding="utf-8")

    # Prepend banner to the generated file
    content = OUT_FILE.read_text(encoding="utf-8")
    if not content.startswith("# AUTO-GENERATED"):
        OUT_FILE.write_text(BANNER + content, encoding="utf-8")

    print(f"  Done — {OUT_FILE.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()

"""
sqlfy.contract_gen.generate_contracts
======================================
Build-time contract schema generator.

This module is invoked automatically when running ``python setup.py build``
(via the ``CustomBuildPy`` command in ``cli/setup.py``).  It can also be
run directly:

.. code-block:: bash

    cd cli
    python -m sqlfy.contract_gen.generate_contracts
    python -m sqlfy.contract_gen.generate_contracts --out path/to/artifacts

Output structure
----------------
::

    <output_dir>/
    ├── schemas/
    │   ├── insights-v1.json
    │   ├── health-v1.json
    │   ├── impact-v1.json
    │   ├── diff-v1.json
    │   ├── simulate-v1.json
    │   ├── rollback-v1.json
    │   └── manifest-v1.json
    ├── index.json
    └── manifest.json

All output is deterministic: the same registry always produces the
same JSON files.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


# Default output directory — ``cli/build/contracts/``.
# __file__ = cli/src/sqlfy/contract_gen/generate_contracts.py
# 4× .parent  → cli/
_DEFAULT_OUT = Path(__file__).resolve().parent.parent.parent.parent / "build" / "contracts"


def _schema_filename(name: str, version: str) -> str:
    """Return the filename for a contract schema, e.g. ``"insights-v1.json"``."""
    return f"{name}-{version}.json"


def generate_all(output_dir: Path | None = None) -> Path:
    """Generate JSON Schema files for all registered contracts.

    Parameters
    ----------
    output_dir:
        Directory to write artifacts into.  Defaults to ``cli/build/contracts/``.
        Created (with parents) if it does not exist.

    Returns
    -------
    Path
        The resolved output directory.

    Raises
    ------
    RuntimeError
        If schema generation fails for any contract.
    """
    from sqlfy.contracts.registry import all_contracts
    from sqlfy.contracts.common.metadata import BuildInfo

    if output_dir is None:
        output_dir = _DEFAULT_OUT

    output_dir = Path(output_dir).resolve()
    schemas_dir = output_dir / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)

    entries = all_contracts()
    generated_keys: list[str] = []
    index_entries: list[dict] = []
    errors: list[str] = []

    print(f"[contracts] Generating {len(entries)} schema(s) → {output_dir}", file=sys.stderr)

    for entry in entries:
        schema_filename = _schema_filename(entry.name, entry.version)
        schema_path = schemas_dir / schema_filename

        try:
            schema = entry.generate_schema()
        except Exception as exc:
            msg = f"  FAILED  {entry.key}: {exc}"
            print(msg, file=sys.stderr)
            errors.append(msg)
            continue

        # Inject $schema and $id for interoperability.
        schema.setdefault("$schema", "https://json-schema.org/draft-07/schema")
        schema.setdefault(
            "$id", f"https://sqlfy.dev/contracts/{entry.name}/{entry.version}"
        )

        schema_path.write_text(
            json.dumps(schema, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        status = "deprecated" if entry.deprecated else "stable"
        generated_keys.append(entry.key)
        index_entries.append(
            {
                "name": entry.name,
                "version": entry.version,
                "command": entry.command,
                "description": entry.description,
                "schema_path": f"schemas/{schema_filename}",
                "status": status,
            }
        )

        flag = " [deprecated]" if entry.deprecated else ""
        print(f"  OK      {entry.key}{flag} → {schema_filename}", file=sys.stderr)

    if errors:
        raise RuntimeError(
            f"Contract generation failed for {len(errors)} contract(s):\n"
            + "\n".join(errors)
        )

    # ── index.json ────────────────────────────────────────────────────────
    index = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contracts": index_entries,
    }
    index_path = output_dir / "index.json"
    index_path.write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"  OK      index.json ({len(index_entries)} entries)", file=sys.stderr)

    # ── manifest.json ─────────────────────────────────────────────────────
    build_info = BuildInfo.capture(generated_keys)
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(build_info.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"  OK      manifest.json", file=sys.stderr)
    print(
        f"[contracts] Done — {len(generated_keys)} schema(s) written to {output_dir}",
        file=sys.stderr,
    )

    return output_dir


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m sqlfy.contract_gen.generate_contracts",
        description="Generate JSON Schema artifacts for all registered SQLFY contracts.",
    )
    parser.add_argument(
        "--out",
        metavar="DIR",
        default=None,
        help=(
            "Output directory for generated artifacts.  "
            f"Default: cli/build/contracts/"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Entry point for ``python -m sqlfy.contract_gen.generate_contracts``."""
    args = _parse_args(argv)
    out = Path(args.out) if args.out else None
    generate_all(out)


if __name__ == "__main__":
    main()

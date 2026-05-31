"""
cli/setup.py
============
Setuptools build script for the sqlfy package.

Extends the standard ``build_py`` command to generate JSON Schema contract
artifacts automatically whenever the package is built.  The generated files
are written to ``build/contracts/`` and are NOT included in the installed
Python package (they are standalone build artifacts).

Usage
-----
    python setup.py build           # build + generate contracts
    pip install -e .                # editable install also triggers build_py

The contract generation step is intentionally cheap: it only imports
``sqlfy.contracts.registry`` and calls Pydantic's ``model_json_schema()``.
No SQL parsing, no disk I/O beyond writing a handful of JSON files.

Build-environment note
----------------------
Contract generation only needs ``pydantic`` (already a project dependency).
To avoid triggering the heavy ``sqlfy/__init__.py`` (which imports sqlglot,
networkx, etc.) in an isolated build environment, ``CustomBuildPy.run()``
pre-registers a minimal stub for the ``sqlfy`` package so that only the
contracts sub-package and ``sqlfy.models`` are imported.  The normal
``build_py`` step then compiles and copies the *real* package as usual.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py


def _bootstrap_contracts_import(src_path: str) -> None:
    """Prepare sys.modules so that ``sqlfy.contracts`` can be imported
    without running the heavy ``sqlfy/__init__.py``.

    We register a lightweight stub for the top-level ``sqlfy`` package
    whose ``__path__`` still points at the real source tree.  All
    sub-packages (``sqlfy.contracts``, ``sqlfy.build``, ``sqlfy.models``)
    are discovered and loaded normally through that path; only the
    ``__init__.py`` of the root package is skipped.
    """
    if "sqlfy" not in sys.modules:
        stub = types.ModuleType("sqlfy")
        stub.__path__ = [str(Path(src_path) / "sqlfy")]  # type: ignore[attr-defined]
        stub.__package__ = "sqlfy"
        stub.__spec__ = None  # type: ignore[assignment]
        sys.modules["sqlfy"] = stub


class CustomBuildPy(build_py):
    """Subclass of ``build_py`` that generates contract schemas before packaging."""

    def run(self) -> None:
        # Ensure the src/ layout is on sys.path so the import works even
        # when running setup.py before an editable install is complete.
        src_path = str(Path(__file__).resolve().parent / "src")
        if src_path not in sys.path:
            sys.path.insert(0, src_path)

        # Bypass sqlfy/__init__.py to avoid importing sqlglot/networkx in the
        # isolated build environment — only pydantic is required for schema gen.
        _bootstrap_contracts_import(src_path)

        try:
            from sqlfy.build.generate_contracts import generate_all  # type: ignore[import]

            generate_all()
        except Exception as exc:
            # Contract generation failure is a build error.
            raise SystemExit(f"[contracts] Build step failed: {exc}") from exc

        # Delegate to the standard build_py logic.
        super().run()


setup(cmdclass={"build_py": CustomBuildPy})

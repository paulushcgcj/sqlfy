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
    python setup.py build_py        # same

Contract generation is skipped silently when the package is being installed
in editable mode (``uv sync`` / ``pip install -e .``).  In that context the
source tree is already live, no artifact publishing occurs, and the project
dependencies (sqlglot, networkx, etc.) are not present in the isolated build
environment that setuptools uses for PEP 517 editable wheels.

For CI or release pipelines that need the schema artifacts, run the generator
as an explicit step AFTER installation:

    uv run python -m sqlfy.contract_gen.generate_contracts
    # or
    make contracts
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py


def _is_editable_build(dist) -> bool:
    """Return True when setuptools is building an editable wheel.

    During ``uv sync`` / ``pip install -e .``, setuptools invokes
    ``build_editable`` which internally calls ``build_py``.  Contract
    generation is not useful in that context and will fail because the
    project's runtime dependencies are absent from the isolated build env.
    """
    return "editable_wheel" in (dist.command_obj or {})


def _bootstrap_contracts_import(src_path: str) -> None:
    """Prepare sys.modules so that ``sqlfy.contracts`` can be imported
    without running the heavy ``sqlfy/__init__.py``.

    We register a lightweight stub for the top-level ``sqlfy`` package
    whose ``__path__`` still points at the real source tree.  All
    sub-packages (``sqlfy.contracts``, ``sqlfy.contract_gen``, ``sqlfy.models``)
    are discovered and loaded normally through that path; only the
    ``__init__.py`` of the root package is skipped.
    """
    if "sqlfy" not in sys.modules:
        import importlib.machinery

        sqlfy_src = str(Path(src_path) / "sqlfy")
        stub = types.ModuleType("sqlfy")
        stub.__path__ = [sqlfy_src]  # type: ignore[attr-defined]
        stub.__package__ = "sqlfy"
        # Provide a minimal ModuleSpec so Python 3.14's import machinery
        # can resolve sub-packages correctly.
        spec = importlib.machinery.ModuleSpec(
            "sqlfy",
            loader=None,
            origin=str(Path(sqlfy_src) / "__init__.py"),
            is_package=True,
        )
        spec.submodule_search_locations = [sqlfy_src]
        stub.__spec__ = spec  # type: ignore[assignment]
        sys.modules["sqlfy"] = stub


class CustomBuildPy(build_py):
    """Subclass of ``build_py`` that generates contract schemas before packaging."""

    def run(self) -> None:
        # Skip during editable installs — artifacts are not produced and
        # project deps are absent from the isolated PEP 517 build env.
        if _is_editable_build(self.distribution):
            print(
                "[contracts] Skipping schema generation (editable install).",
                file=sys.stderr,
            )
            super().run()
            return

        src_path = str(Path(__file__).resolve().parent / "src")
        if src_path not in sys.path:
            sys.path.insert(0, src_path)

        _bootstrap_contracts_import(src_path)

        try:
            from sqlfy.contract_gen.generate_contracts import generate_all  # type: ignore[import]

            generate_all()
        except Exception as exc:
            # Contract generation failure is a build error for full builds.
            raise SystemExit(f"[contracts] Build step failed: {exc}") from exc

        super().run()


setup(cmdclass={"build_py": CustomBuildPy})

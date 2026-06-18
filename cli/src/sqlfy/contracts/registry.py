"""
sqlfy.contracts.registry
=========================
Central registry of all public SQLFY contracts.

This module is the **single source of truth** for every JSON output shape
that SQLFY exposes publicly.  The build generator reads :data:`CONTRACTS`
to discover which schemas to emit.

Adding a new contract
---------------------
1. Define the contract class in ``contracts/<domain>/v<N>.py``.
2. Import it below and add a :class:`ContractEntry` to :data:`CONTRACTS`.
3. Run ``make contracts`` or ``python setup.py build``.

Registry key convention
-----------------------
Keys follow ``"<name>@<version>"``, e.g. ``"insights@v1"``.  This
makes it unambiguous to address a specific version while allowing the
same name to appear at multiple versions simultaneously.
"""

from __future__ import annotations

import pkgutil
import importlib
from dataclasses import dataclass, field
from typing import Iterator, Type

from pydantic import BaseModel

from .analysis.v1 import HealthV1, InsightsV1
from .analysis.pii_v1 import PiiScanV1
from .evolution.v1 import DiffV1, RollbackV1, SimulateV1
from .graph.v1 import GraphManifestV1
from .impact.v1 import ImpactV1


# ─────────────────────────────────────────────────────────────────────────────
# ContractEntry
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ContractEntry:
    """Registry record describing one public contract.

    Instances are immutable after construction (``frozen=True``).
    """

    name: str
    """Stable contract identifier, e.g. ``"insights"``.  Immutable once published."""

    version: str
    """Slot version string, e.g. ``"v1"`` or ``"v2"``."""

    command: str
    """Name of the CLI command that produces this output, e.g. ``"insights"``."""

    description: str
    """Human-readable purpose of this contract."""

    model_class: Type[BaseModel]
    """The Pydantic contract class.  Must be importable and schema-able."""

    deprecated: bool = False
    """``True`` if this version has been superseded and is pending removal."""

    @property
    def key(self) -> str:
        """Return the canonical registry key ``"<name>@<version>"``."""
        return f"{self.name}@{self.version}"

    def generate_schema(self) -> dict:
        """Return the JSON Schema dict for this contract.

        Delegates to :meth:`pydantic.BaseModel.model_json_schema`.
        """
        return self.model_class.model_json_schema()


# ─────────────────────────────────────────────────────────────────────────────
# CONTRACTS registry
# ─────────────────────────────────────────────────────────────────────────────

_RAW: list[ContractEntry] = [
    # ── Analysis ──────────────────────────────────────────────────────────
    ContractEntry(
        name="insights",
        version="v1",
        command="insights",
        description=(
            "Schema quality findings produced by the insights command. "
            "Grouped by severity with aggregated counts and a state fingerprint."
        ),
        model_class=InsightsV1,
    ),
    ContractEntry(
        name="health",
        version="v1",
        command="health",
        description=(
            "Migration folder health report produced by the health command. "
            "Includes a 0–100 health score, qualitative grade, and per-file status."
        ),
        model_class=HealthV1,
    ),
    ContractEntry(
        name="pii-scan",
        version="v1",
        command="pii-scan",
        description=(
            "PII column scan result produced by the pii-scan command. "
            "Lists columns matching PII patterns with confidence scores."
        ),
        model_class=PiiScanV1,
    ),
    # ── Impact ────────────────────────────────────────────────────────────
    ContractEntry(
        name="impact",
        version="v1",
        command="impact",
        description=(
            "Transitive impact analysis produced by the impact command. "
            "Reports direct and transitive dependencies with depth and type grouping."
        ),
        model_class=ImpactV1,
    ),
    # ── Evolution ─────────────────────────────────────────────────────────
    ContractEntry(
        name="diff",
        version="v1",
        command="diff-versions",
        description=(
            "Schema diff between two version snapshots produced by the diff-versions command. "
            "Includes table, column, sequence, and relationship changes."
        ),
        model_class=DiffV1,
    ),
    ContractEntry(
        name="simulate",
        version="v1",
        command="simulate",
        description=(
            "DDL simulation result produced by the simulate command. "
            "Reports whether the DDL applies cleanly and what structural changes it introduces."
        ),
        model_class=SimulateV1,
    ),
    ContractEntry(
        name="rollback",
        version="v1",
        command="rollback-analysis",
        description=(
            "Rollback feasibility analysis produced by the rollback-analysis command. "
            "Per-migration reversibility scoring with suggested rollback SQL snippets."
        ),
        model_class=RollbackV1,
    ),
    # ── Graph ─────────────────────────────────────────────────────────────
    ContractEntry(
        name="manifest",
        version="v1",
        command="manifest",
        description=(
            "High-level schema graph metadata produced by the manifest command. "
            "Includes node/edge counts, table/column counts, and graph fingerprint."
        ),
        model_class=GraphManifestV1,
    ),
]

# Build the dict with duplicate-key guard applied at import time.
CONTRACTS: dict[str, ContractEntry] = {}
for _entry in _RAW:
    if _entry.key in CONTRACTS:
        raise ValueError(
            f"Duplicate contract key '{_entry.key}' detected in registry.  "
            "Each name@version combination must be unique."
        )
    CONTRACTS[_entry.key] = _entry


# ─────────────────────────────────────────────────────────────────────────────
# Discovery helpers
# ─────────────────────────────────────────────────────────────────────────────


def all_contracts() -> list[ContractEntry]:
    """Return all registered :class:`ContractEntry` instances in insertion order."""
    return list(CONTRACTS.values())


def get_contract(key: str) -> ContractEntry:
    """Return the entry for *key* (e.g. ``"insights@v1"``).

    Raises :class:`KeyError` if the key is not registered.
    """
    return CONTRACTS[key]


def latest_contracts() -> list[ContractEntry]:
    """Return the highest-version entry for each unique contract name.

    Version comparison is lexicographic on the version string (``"v1" < "v2"``).
    Non-deprecated entries are preferred over deprecated ones.
    """
    best: dict[str, ContractEntry] = {}
    for entry in CONTRACTS.values():
        current = best.get(entry.name)
        if current is None:
            best[entry.name] = entry
        else:
            # Prefer non-deprecated; break ties by lexicographic version order.
            if (not entry.deprecated and current.deprecated) or (
                entry.deprecated == current.deprecated
                and entry.version > current.version
            ):
                best[entry.name] = entry
    return list(best.values())


def contracts_for_command(command: str) -> list[ContractEntry]:
    """Return all contracts produced by the given CLI *command* name."""
    return [e for e in CONTRACTS.values() if e.command == command]


def discover() -> list[ContractEntry]:
    """Auto-discover contracts by walking the ``contracts`` sub-packages.

    Finds every class that inherits from :class:`~sqlfy.contracts.common.base.ContractBase`
    and has a non-empty ``CONTRACT_NAME``, then returns a list of synthetic
    :class:`ContractEntry` instances.  Does **not** mutate :data:`CONTRACTS`.

    Useful for linting or for large contract sets where explicit registration
    becomes impractical.
    """
    from .common.base import ContractBase

    found: list[ContractEntry] = []
    import sqlfy.contracts as _pkg

    pkg_path = _pkg.__path__
    pkg_prefix = _pkg.__name__ + "."

    for _importer, modname, _ispkg in pkgutil.walk_packages(pkg_path, pkg_prefix):
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name, None)
            if (
                isinstance(obj, type)
                and issubclass(obj, ContractBase)
                and obj is not ContractBase
                and obj.CONTRACT_NAME
            ):
                found.append(
                    ContractEntry(
                        name=obj.CONTRACT_NAME,
                        version=obj.CONTRACT_VERSION,
                        command=obj.CONTRACT_COMMAND,
                        description=obj.CONTRACT_DESCRIPTION,
                        model_class=obj,
                        deprecated=obj.CONTRACT_DEPRECATED,
                    )
                )
    return found

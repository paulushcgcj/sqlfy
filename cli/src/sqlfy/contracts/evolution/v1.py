"""
sqlfy.contracts.evolution.v1
==============================
Version-1 public contracts for schema evolution commands.

Covered commands
----------------
* ``sqlfy diff-versions --format json``    →  :class:`DiffV1`
* ``sqlfy simulate     --format json``    →  :class:`SimulateV1`
* ``sqlfy rollback-analysis --format json`` →  :class:`RollbackV1`
"""

from __future__ import annotations

from typing import ClassVar

from ...models import DiffResult, RollbackResult, SimulateResult
from ..common.base import ContractBase


class DiffV1(ContractBase, DiffResult):
    """Public contract for ``sqlfy diff-versions --format json``, version 1.

    Describes all structural differences between two schema version snapshots:
    added/removed/modified tables, columns, sequences, and FK relationships,
    with a breaking-change flag and change-count summary.
    """

    CONTRACT_NAME: ClassVar[str] = "diff"
    CONTRACT_VERSION: ClassVar[str] = "v1"
    CONTRACT_DESCRIPTION: ClassVar[str] = (
        "Schema diff between two version snapshots produced by the diff-versions command. "
        "Includes table, column, sequence, and relationship changes with a breaking-change flag."
    )
    CONTRACT_COMMAND: ClassVar[str] = "diff-versions"


class SimulateV1(ContractBase, SimulateResult):
    """Public contract for ``sqlfy simulate --format json``, version 1.

    Dry-runs a DDL statement against a schema state and reports success,
    safety, breaking-change detection, a structural diff, and a health snapshot.
    """

    CONTRACT_NAME: ClassVar[str] = "simulate"
    CONTRACT_VERSION: ClassVar[str] = "v1"
    CONTRACT_DESCRIPTION: ClassVar[str] = (
        "DDL simulation result produced by the simulate command. "
        "Reports whether the DDL applies cleanly, is safe, and what structural changes it introduces."
    )
    CONTRACT_COMMAND: ClassVar[str] = "simulate"


class RollbackV1(ContractBase, RollbackResult):
    """Public contract for ``sqlfy rollback-analysis --format json``, version 1.

    Assesses rollback feasibility for each migration in a folder: reversible,
    partial, or irreversible, with difficulty score and suggested rollback SQL.
    """

    CONTRACT_NAME: ClassVar[str] = "rollback"
    CONTRACT_VERSION: ClassVar[str] = "v1"
    CONTRACT_DESCRIPTION: ClassVar[str] = (
        "Rollback feasibility analysis produced by the rollback-analysis command. "
        "Per-migration reversibility scoring with suggested rollback SQL snippets."
    )
    CONTRACT_COMMAND: ClassVar[str] = "rollback-analysis"

"""
sqlfy.contracts.impact.v1
==========================
Version-1 public contract for the impact analysis command.

Covered commands
----------------
* ``sqlfy impact --format json``  →  :class:`ImpactV1`
"""

from __future__ import annotations

from typing import ClassVar

from ...models import ImpactResult
from ..common.base import ContractBase


class ImpactV1(ContractBase, ImpactResult):
    """Public contract for ``sqlfy impact --format json``, version 1.

    Reports the transitive impact of a schema object change: directly and
    transitively affected objects, depth map, objects grouped by type, and
    critical dependency paths.
    """

    CONTRACT_NAME: ClassVar[str] = "impact"
    CONTRACT_VERSION: ClassVar[str] = "v1"
    CONTRACT_DESCRIPTION: ClassVar[str] = (
        "Transitive impact analysis produced by the impact command. "
        "Reports direct and transitive dependencies with depth and type grouping."
    )
    CONTRACT_COMMAND: ClassVar[str] = "impact"

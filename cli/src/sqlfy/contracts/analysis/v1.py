"""
sqlfy.contracts.analysis.v1
=============================
Version-1 public contracts for the analysis commands.

Covered commands
----------------
* ``sqlfy insights --format json``  →  :class:`InsightsV1`
* ``sqlfy health   --format json``  →  :class:`HealthV1`

These classes inherit all Pydantic fields from the corresponding
auto-generated models in ``sqlfy.models`` without modification.  The
only additions are the four ``CONTRACT_*`` class variables used by the
registry and the build generator.

The serialised JSON shape is therefore identical to what the commands
currently produce.
"""

from __future__ import annotations

from typing import ClassVar

from ...models import HealthResult, InsightsResult
from ..common.base import ContractBase


class InsightsV1(ContractBase, InsightsResult):
    """Public contract for ``sqlfy insights --format json``, version 1.

    Carries schema quality findings grouped by severity (error, warning, info)
    together with aggregated counts and a state fingerprint.
    """

    CONTRACT_NAME: ClassVar[str] = "insights"
    CONTRACT_VERSION: ClassVar[str] = "v1"
    CONTRACT_DESCRIPTION: ClassVar[str] = (
        "Schema quality findings produced by the insights command. "
        "Grouped by severity with aggregated counts and a state fingerprint."
    )
    CONTRACT_COMMAND: ClassVar[str] = "insights"


class HealthV1(ContractBase, HealthResult):
    """Public contract for ``sqlfy health --format json``, version 1.

    Reports migration folder health: safe/unsafe/irreversible migration counts,
    a numeric health score (0–100), qualitative grade, and per-file status rows.
    """

    CONTRACT_NAME: ClassVar[str] = "health"
    CONTRACT_VERSION: ClassVar[str] = "v1"
    CONTRACT_DESCRIPTION: ClassVar[str] = (
        "Migration folder health report produced by the health command. "
        "Includes a 0–100 health score, qualitative grade, and per-file status."
    )
    CONTRACT_COMMAND: ClassVar[str] = "health"

"""
sqlfy.contracts
================
Public contract layer for SQLFY.

This package contains all public response contracts as explicit, versioned
Pydantic models.  It is the single source of truth for the JSON shapes
that SQLFY commands expose externally.

Typical usage::

    from sqlfy.contracts import InsightsV1, HealthV1
    from sqlfy.contracts.registry import CONTRACTS, get_contract, all_contracts

Quick imports
-------------
All top-level contract classes are re-exported from this package for
convenience.  Domain sub-packages are also importable directly:

    from sqlfy.contracts.analysis.v1 import InsightsV1
    from sqlfy.contracts.impact.v1   import ImpactV1
"""

from .analysis.v1 import HealthV1, InsightsV1
from .common.base import ContractBase
from .common.envelope import ResponseEnvelope
from .common.metadata import BuildInfo
from .evolution.v1 import DiffV1, RollbackV1, SimulateV1
from .graph.v1 import GraphManifestV1
from .impact.v1 import ImpactV1
from .registry import (
    CONTRACTS,
    ContractEntry,
    all_contracts,
    contracts_for_command,
    discover,
    get_contract,
    latest_contracts,
)

__all__ = [
    # Base
    "ContractBase",
    "ResponseEnvelope",
    "BuildInfo",
    # Analysis
    "InsightsV1",
    "HealthV1",
    # Impact
    "ImpactV1",
    # Evolution
    "DiffV1",
    "SimulateV1",
    "RollbackV1",
    # Graph
    "GraphManifestV1",
    # Registry
    "CONTRACTS",
    "ContractEntry",
    "all_contracts",
    "get_contract",
    "latest_contracts",
    "contracts_for_command",
    "discover",
]

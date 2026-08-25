"""
sqlfy.contracts.graph.v1
=======================
Version-1 public contracts for the graph commands.

Covered commands
----------------
* ``sqlfy manifest --format json``  →  :class:`GraphManifestV1`
* ``sqlfy graph --format json``  →  :class:`GraphOutputV1`
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from ...models import SchemaManifest
from ..common.base import ContractBase


class GraphManifestV1(ContractBase, SchemaManifest):
    """Public contract for ``sqlfy manifest --format json``, version 1.

    Provides high-level metadata about the schema graph: version, fingerprint,
    dialect, object counts, and generation timestamp.
    """

    CONTRACT_NAME: ClassVar[str] = "manifest"
    CONTRACT_VERSION: ClassVar[str] = "v1"
    CONTRACT_DESCRIPTION: ClassVar[str] = (
        "High-level schema graph metadata produced by the manifest command. "
        "Includes node/edge counts, table/column counts, and graph fingerprint."
    )
    CONTRACT_COMMAND: ClassVar[str] = "manifest"


class GraphOutputV1(ContractBase, BaseModel):
    """Public contract for ``sqlfy graph --format json``, version 1.

    Complete schema graph structure including nodes, edges, communities,
    and optional visualisation data.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    version: str = Field(..., description="Graph schema version.")
    generated_at: str = Field(
        ..., alias="generatedAt", description="ISO-8601 generation timestamp."
    )
    fingerprint: str = Field(..., description="Graph fingerprint.")
    dialect: str = Field(..., description="SQL dialect.")
    nodes: dict[str, Any] = Field(..., description="Graph nodes keyed by identifier.")
    edges: list[dict[str, Any]] = Field(..., description="Graph edges.")
    communities: list[dict[str, Any]] = Field(
        default_factory=list, description="Community detection results."
    )
    god_nodes: list[dict[str, Any]] = Field(
        default_factory=list, alias="godNodes", description="High-degree nodes."
    )
    meta: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata."
    )

    CONTRACT_NAME: ClassVar[str] = "graph_output"
    CONTRACT_VERSION: ClassVar[str] = "v1"
    CONTRACT_DESCRIPTION: ClassVar[str] = (
        "Complete schema graph structure produced by the graph command. "
        "Includes nodes, edges, communities, god nodes, and metadata."
    )
    CONTRACT_COMMAND: ClassVar[str] = "graph"

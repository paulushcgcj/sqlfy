"""
sqlfy.contracts.graph.v1
=========================
Version-1 public contract for the graph manifest command.

Covered commands
----------------
* ``sqlfy manifest --format json``  →  :class:`GraphManifestV1`
"""

from __future__ import annotations

from typing import ClassVar

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

"""
sqlfy.contracts.schema.v1
==========================
Version-1 public contracts for the schema commands.

Covered commands
----------------
* ``sqlfy dump --format json``  →  :class:`SchemaStateV1`

These classes inherit all Pydantic fields from the corresponding
auto-generated models in ``sqlfy.models`` without modification.  The
only additions are the four ``CONTRACT_*`` class variables used by the
registry and the build generator.

The serialised JSON shape is therefore identical to what the commands
currently produce.
"""

from __future__ import annotations

from typing import ClassVar

from ...models import SchemaState
from ..common.base import ContractBase


class SchemaStateV1(ContractBase, SchemaState):
    """Public contract for ``sqlfy dump --format json``, version 1.

    Complete schema state dictionary including tables, sequences, relationships,
    migration history, and summary statistics.
    """

    CONTRACT_NAME: ClassVar[str] = "schema_state"
    CONTRACT_VERSION: ClassVar[str] = "v1"
    CONTRACT_DESCRIPTION: ClassVar[str] = (
        "Complete schema state dictionary produced by the dump command. "
        "Includes tables, sequences, relationships, migration history, and stats."
    )
    CONTRACT_COMMAND: ClassVar[str] = "dump"

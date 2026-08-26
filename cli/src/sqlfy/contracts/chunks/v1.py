"""
sqlfy.contracts.chunks.v1
==========================
Version-1 public contracts for the chunks command.

Covered commands
----------------
* ``sqlfy chunks --format json``  →  :class:`ChunksV1`

These classes inherit all Pydantic fields from the corresponding
auto-generated models in ``sqlfy.models`` without modification.  The
only additions are the four ``CONTRACT_*`` class variables used by the
registry and the build generator.

The serialised JSON shape is therefore identical to what the commands
currently produce.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from ...models import VectorChunk
from ..common.base import ContractBase


class ChunksV1(ContractBase, BaseModel):
    """Public contract for ``sqlfy chunks --format json``, version 1.

    List of LLM vector chunks with metadata for RAG retrieval.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    chunks: list[VectorChunk] = Field(..., description="List of vector chunks.")
    count: int = Field(..., description="Total number of chunks.")
    meta: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata."
    )

    CONTRACT_NAME: ClassVar[str] = "chunks"
    CONTRACT_VERSION: ClassVar[str] = "v1"
    CONTRACT_DESCRIPTION: ClassVar[str] = (
        "LLM vector chunks produced by the chunks command. "
        "Includes chunk content, metadata, and retrieval hints."
    )
    CONTRACT_COMMAND: ClassVar[str] = "chunks"

"""
sqlfy.contracts.query.v1
=========================
Version-1 public contracts for the query command.

Covered commands
----------------
* ``sqlfy query --format json``  →  :class:`QueryResultV1`

These classes inherit all Pydantic fields from the corresponding
domain models. The query command supports multiple query types,
each with its own result structure.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from ..common.base import ContractBase


class QueryResultV1(ContractBase, BaseModel):
    """Public contract for ``sqlfy query --format json``, version 1.

    Structured deterministic schema query results. The exact shape varies
    by query type but always includes the query description, row count,
    column headers, rows, and metadata.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    query: str = Field(..., description="Human-readable query description.")
    count: int = Field(..., description="Number of result rows.")
    columns: list[str] = Field(..., description="Column headers for tabular display.")
    rows: list[dict[str, Any]] = Field(..., description="Result rows as dictionaries.")
    meta: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata."
    )

    CONTRACT_NAME: ClassVar[str] = "query_result"
    CONTRACT_VERSION: ClassVar[str] = "v1"
    CONTRACT_DESCRIPTION: ClassVar[str] = (
        "Deterministic graph query results produced by the query command. "
        "Includes query description, row count, columns, rows, and metadata."
    )
    CONTRACT_COMMAND: ClassVar[str] = "query"

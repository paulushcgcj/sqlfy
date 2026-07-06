"""
sqlfy.contracts.analysis.pii_v1
===============================
Version-1 public contract for the PII scan command.

Covered commands
----------------
* ``sqlfy pii-scan --format json``  →  :class:`PiiScanV1`

This defines the JSON output shape for PII scanning results.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from ..common.base import ContractBase


class PiiColumnFindingV1(BaseModel):
    """A single PII column finding."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    table_name: str = Field(
        ...,
        description="Name of the table containing the PII column",
        serialization_alias="tableName",
    )
    column_name: str = Field(
        ...,
        description="Name of the column identified as PII",
        serialization_alias="columnName",
    )
    column_type: str = Field(
        ...,
        description="Data type of the column",
        serialization_alias="columnType",
    )
    pii_categories: list[str] = Field(
        ...,
        description="List of PII categories that matched (e.g., ['email', 'name'])",
        serialization_alias="piiCategories",
    )
    confidence: float = Field(
        ...,
        description="Confidence score from 0.0 to 1.0",
    )
    evidence: str = Field(
        ...,
        description="The regex pattern that matched",
    )


class PiiScanV1(ContractBase):
    """Public contract for ``sqlfy pii-scan --format json``, version 1.

    Carries PII scanning results including findings, counts, and metadata.
    """

    CONTRACT_NAME: ClassVar[str] = "pii_scan"
    CONTRACT_VERSION: ClassVar[str] = "v1"
    CONTRACT_DESCRIPTION: ClassVar[str] = (
        "PII scan results produced by the pii-scan command. "
        "Includes findings, table/column counts, and confidence-scored PII column identifications."
    )
    CONTRACT_COMMAND: ClassVar[str] = "pii-scan"

    tables_scanned: int = Field(
        ...,
        description="Total number of tables scanned",
        serialization_alias="tablesScanned",
    )
    columns_scanned: int = Field(
        ...,
        description="Total number of columns scanned",
        serialization_alias="columnsScanned",
    )
    pii_table_count: int = Field(
        ...,
        description="Number of tables containing PII columns",
        serialization_alias="piiTableCount",
    )
    pii_column_count: int = Field(
        ...,
        description="Number of PII columns found",
        serialization_alias="piiColumnCount",
    )
    findings: list[PiiColumnFindingV1] = Field(
        ...,
        description="List of PII column findings",
    )

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

from typing import ClassVar, List

from pydantic import BaseModel, Field
from ..common.base import ContractBase


class PiiColumnFindingV1(BaseModel):
    """A single PII column finding."""
    
    model_config = ContractBase.model_config
    
    tableName: str = Field(..., description="Name of the table containing the PII column")
    columnName: str = Field(..., description="Name of the column identified as PII")
    columnType: str = Field(..., description="Data type of the column")
    piiCategories: List[str] = Field(..., description="List of PII categories that matched (e.g., ['email', 'name'])")
    confidence: float = Field(..., description="Confidence score from 0.0 to 1.0")
    evidence: str = Field(..., description="The regex pattern that matched")


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

    tablesScanned: int = Field(..., description="Total number of tables scanned")
    columnsScanned: int = Field(..., description="Total number of columns scanned")
    piiTableCount: int = Field(..., description="Number of tables containing PII columns")
    piiColumnCount: int = Field(..., description="Number of PII columns found")
    findings: List[PiiColumnFindingV1] = Field(..., description="List of PII column findings")
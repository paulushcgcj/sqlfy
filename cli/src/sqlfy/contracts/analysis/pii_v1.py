"""
sqlfy.contracts.analysis.pii_v1
===============================
Version-1 public contract for the ``pii-scan`` command.
"""

from __future__ import annotations

from typing import ClassVar

from ...models import PiiScanResult
from ..common.base import ContractBase


class PiiScanV1(ContractBase, PiiScanResult):
    """Public contract for ``sqlfy pii-scan --format json``, version 1.

    Reports PII column findings with confidence scores, per-column
    categories, and summary counts.
    """

    CONTRACT_NAME: ClassVar[str] = "pii-scan"
    CONTRACT_VERSION: ClassVar[str] = "v1"
    CONTRACT_DESCRIPTION: ClassVar[str] = (
        "PII column scan result produced by the pii-scan command. "
        "Lists columns that match PII patterns with confidence scores, "
        "categories, and aggregate counts."
    )
    CONTRACT_COMMAND: ClassVar[str] = "pii-scan"

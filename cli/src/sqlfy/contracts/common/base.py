"""
sqlfy.contracts.common.base
============================
Base class and metadata primitives shared by all public SQLFY contracts.

Every public contract class must inherit from ``ContractBase`` alongside
the appropriate domain model from ``sqlfy.models``.  The four ``ClassVar``
attributes are the only additions; they carry no Pydantic field data and
therefore have zero effect on the serialised JSON shape.

Example::

    from sqlfy.contracts.common.base import ContractBase
    from sqlfy.models import InsightsResult

    class InsightsV1(ContractBase, InsightsResult):
        CONTRACT_NAME: ClassVar[str] = "insights"
        CONTRACT_VERSION: ClassVar[str] = "v1"
        CONTRACT_DESCRIPTION: ClassVar[str] = "Schema quality findings"
        CONTRACT_COMMAND: ClassVar[str] = "insights"
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class ContractBase(BaseModel):
    """Mixin base for all SQLFY public contract models.

    Subclasses must set the four ``CONTRACT_*`` class variables.
    No Pydantic fields are defined here; the mixin purely carries
    metadata consumed by the registry and the build generator.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    CONTRACT_NAME: ClassVar[str] = ""
    """Stable contract identifier, e.g. ``"insights"``.  Immutable once published."""

    CONTRACT_VERSION: ClassVar[str] = "v1"
    """Slot version string, e.g. ``"v1"`` or ``"v2"``."""

    CONTRACT_DESCRIPTION: ClassVar[str] = ""
    """Human-readable purpose of this contract."""

    CONTRACT_COMMAND: ClassVar[str] = ""
    """Name of the CLI command that produces this output, e.g. ``"insights"``."""

    CONTRACT_DEPRECATED: ClassVar[bool] = False
    """Set to ``True`` when this version has been superseded by a newer slot."""

    @classmethod
    def contract_key(cls) -> str:
        """Return the canonical registry key ``"<name>@<version>"``."""
        return f"{cls.CONTRACT_NAME}@{cls.CONTRACT_VERSION}"

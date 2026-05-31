"""
sqlfy.contracts.common.metadata
================================
Build-time metadata attached to generated contract artifacts.
"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class BuildInfo:
    """Provenance metadata recorded in ``manifest.json`` at build time."""

    build_timestamp: str
    """ISO-8601 UTC timestamp of schema generation."""

    sqlfy_version: str
    """Version string from ``importlib.metadata`` for the ``sqlfy`` package."""

    python_version: str
    """``sys.version`` string of the interpreter that ran the build."""

    platform: str
    """``platform.platform()`` string of the build host."""

    contract_count: int
    """Number of contracts generated in this run."""

    contracts: list[str] = field(default_factory=list)
    """Registry keys of all generated contracts, e.g. ``["insights@v1", ...]``."""

    @classmethod
    def capture(cls, contract_keys: list[str]) -> "BuildInfo":
        """Capture build metadata from the current runtime environment."""
        try:
            from importlib.metadata import version as _version

            sqlfy_ver = _version("sqlfy")
        except Exception:
            sqlfy_ver = "unknown"

        return cls(
            build_timestamp=datetime.now(timezone.utc).isoformat(),
            sqlfy_version=sqlfy_ver,
            python_version=sys.version,
            platform=platform.platform(),
            contract_count=len(contract_keys),
            contracts=list(contract_keys),
        )

    def to_dict(self) -> dict:
        """Serialise to a plain dictionary suitable for ``json.dumps``."""
        return {
            "build_timestamp": self.build_timestamp,
            "sqlfy_version": self.sqlfy_version,
            "python_version": self.python_version,
            "platform": self.platform,
            "contract_count": self.contract_count,
            "contracts": self.contracts,
        }

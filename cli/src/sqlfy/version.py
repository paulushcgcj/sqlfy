"""Runtime package-version helpers."""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def get_version() -> str:
    """Return the installed SQLfy CLI version, or ``unknown`` in a source tree."""
    try:
        return version("sqlfy-cli")
    except PackageNotFoundError:
        return "unknown"

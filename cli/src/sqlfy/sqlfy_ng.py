"""Compatibility entry point for the deprecated ``sqlfy-ng`` command."""
from __future__ import annotations

import sys

from .main import main as _main


def main() -> None:
    """Forward ``sqlfy-ng`` invocations to the canonical ``sqlfy`` CLI."""
    print("Warning: 'sqlfy-ng' is deprecated; use 'sqlfy' instead.", file=sys.stderr)
    _main()

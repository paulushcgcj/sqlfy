"""
sqlfy.intelligence.chunker
==========================
Re-exports build_chunks from output.chunker.

The canonical implementation lives in sqlfy.output.chunker.
This module exposes it as part of the intelligence domain.
"""

from ..output.chunker import build_chunks

__all__ = ["build_chunks"]

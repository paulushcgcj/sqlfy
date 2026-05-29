"""
sqlfy.intelligence.chunk_cache
==============================
Re-exports from sqlfy.analysis.chunk_cache (canonical location).
"""

from ..analysis.chunk_cache import ChunkCache, compute_schema_fingerprint

__all__ = ["ChunkCache", "compute_schema_fingerprint"]

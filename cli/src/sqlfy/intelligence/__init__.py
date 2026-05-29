"""
sqlfy.intelligence
==================
Intelligence domain — RAG pipeline, chunk retrieval, and LLM querying.

Modules:
  - asker        Natural language → LLM query pipeline (Claude)
  - retriever    BM25/embedding chunk retrieval
  - chunk_cache  Schema fingerprint-based chunk caching
  - chunker      Vector chunk builder from SchemaGraph
"""

from .asker import Asker, AskResult
from .retriever import KeywordRetriever, make_retriever, RetrievedChunk
from .chunk_cache import ChunkCache, compute_schema_fingerprint

__all__ = [
    "Asker",
    "AskResult",
    "KeywordRetriever",
    "make_retriever",
    "RetrievedChunk",
    "ChunkCache",
    "compute_schema_fingerprint",
]

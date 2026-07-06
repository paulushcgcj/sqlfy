"""Backward-compat shim. Use sqlfy.intelligence.retriever directly."""
from __future__ import annotations

from ..intelligence.retriever import (
    EmbeddingRetriever,
    KeywordRetriever,
    RetrievedChunk,
    make_retriever,
)

__all__ = ["KeywordRetriever", "EmbeddingRetriever", "make_retriever", "RetrievedChunk"]

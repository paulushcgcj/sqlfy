"""Backward-compat shim. Use sqlfy.intelligence.retriever directly."""
from ..intelligence.retriever import (
    KeywordRetriever,
    EmbeddingRetriever,
    make_retriever,
    RetrievedChunk,
)
__all__ = ["KeywordRetriever", "EmbeddingRetriever", "make_retriever", "RetrievedChunk"]

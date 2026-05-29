"""
sqlfy.parsing.extractors.base
==============================
Abstract base for DDL operation extractors.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
import sqlglot.expressions as exp
from ...semantic.operations import AnyOperation, OperationProvenance


class BaseExtractor(ABC):
    """
    Transforms a sqlglot statement into zero or more typed ``AnyOperation`` instances.

    Subclasses handle a specific statement kind (CREATE TABLE, ALTER TABLE, DROP, …).
    """

    @abstractmethod
    def can_handle(self, stmt: exp.Expression) -> bool:
        """Return True if this extractor can process *stmt*."""

    @abstractmethod
    def extract(
        self, stmt: exp.Expression, provenance: OperationProvenance
    ) -> list[AnyOperation]:
        """Return semantic operations derived from *stmt*."""

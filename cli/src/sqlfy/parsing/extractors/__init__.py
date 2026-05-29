"""
sqlfy.parsing.extractors
========================
Registry of DDL operation extractors.

Usage::

    from sqlfy.parsing.extractors import get_extractor

    extractor = get_extractor(stmt)
    if extractor:
        ops = extractor.extract(stmt, provenance)
"""
from __future__ import annotations
from typing import TYPE_CHECKING

import sqlglot.expressions as exp

from .base import BaseExtractor
from .create_table import CreateTableExtractor
from .alter_table import AlterTableExtractor
from .drop import DropExtractor

if TYPE_CHECKING:
    from ...semantic.operations import AnyOperation, OperationProvenance

_EXTRACTORS: list[BaseExtractor] = [
    CreateTableExtractor(),
    AlterTableExtractor(),
    DropExtractor(),
]


def get_extractor(stmt: exp.Expression) -> BaseExtractor | None:
    """Return the first extractor that can handle *stmt*, or None."""
    for extractor in _EXTRACTORS:
        if extractor.can_handle(stmt):
            return extractor
    return None


__all__ = [
    "BaseExtractor",
    "CreateTableExtractor",
    "AlterTableExtractor",
    "DropExtractor",
    "get_extractor",
]

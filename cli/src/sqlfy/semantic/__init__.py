"""
sqlfy.semantic
==============
Semantic operations layer — typed, provenance-carrying DDL operation models.

Modules:
  - operations   Pydantic models for all DDL operation types
  - normalizer   AST → operation converter (Normalizer class)
"""
from __future__ import annotations

from .normalizer import Normalizer
from .operations import (
    AddColumnOperation,
    AddConstraintOperation,
    AnyOperation,
    CommentOperation,
    CreateIndexOperation,
    CreateSequenceOperation,
    CreateTableOperation,
    DropColumnOperation,
    DropConstraintOperation,
    DropIndexOperation,
    DropTableOperation,
    ModifyColumnOperation,
    OperationProvenance,
    RenameColumnOperation,
    UnknownOperation,
)

__all__ = [
    "AnyOperation",
    "OperationProvenance",
    "Normalizer",
    "CreateTableOperation",
    "DropTableOperation",
    "AddColumnOperation",
    "DropColumnOperation",
    "ModifyColumnOperation",
    "RenameColumnOperation",
    "AddConstraintOperation",
    "DropConstraintOperation",
    "CreateIndexOperation",
    "DropIndexOperation",
    "CreateSequenceOperation",
    "CommentOperation",
    "UnknownOperation",
]

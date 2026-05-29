"""
sqlfy.semantic
==============
Semantic operations layer — typed, provenance-carrying DDL operation models.

Modules:
  - operations   Pydantic models for all DDL operation types
  - normalizer   AST → operation converter (Normalizer class)
"""

from .operations import (
    AnyOperation,
    OperationProvenance,
    CreateTableOperation,
    DropTableOperation,
    AddColumnOperation,
    DropColumnOperation,
    ModifyColumnOperation,
    RenameColumnOperation,
    AddConstraintOperation,
    DropConstraintOperation,
    CreateIndexOperation,
    DropIndexOperation,
    CreateSequenceOperation,
    CommentOperation,
    UnknownOperation,
)
from .normalizer import Normalizer

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

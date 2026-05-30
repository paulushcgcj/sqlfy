"""
sqlfy.semantic.operations
=========================
Pydantic models for semantic DDL operations extracted from the AST pipeline.

Every operation carries an ``OperationProvenance`` with full traceability back to
the migration file, statement index, and original SQL. Operations are immutable
(frozen Pydantic models) and JSON-serialisable via model_dump_json(by_alias=True).

Union type ``AnyOperation`` is used wherever a list of heterogeneous operations
is needed.
"""

from __future__ import annotations

import hashlib
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────────────────────────────────────────
# Provenance
# ─────────────────────────────────────────────────────────────

class OperationProvenance(BaseModel):
    """Full traceability for a single extracted operation."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    source_file: str = Field(..., serialization_alias="sourceFile", description="Relative migration filename.")
    version: str = Field(..., description="Flyway version string.")
    statement_index: int = Field(..., serialization_alias="statementIndex", description="0-based index within the file.")
    content_hash: str = Field(..., serialization_alias="contentHash", description="SHA-256 of the statement text.")
    raw_sql: str | None = Field(None, serialization_alias="rawSql", description="Original SQL fragment.")

    @classmethod
    def of(cls, source_file: str, version: str, statement_index: int, raw_sql: str | None) -> "OperationProvenance":
        h = hashlib.sha256((raw_sql or "").encode()).hexdigest()
        return cls(
            source_file=source_file,
            version=version,
            statement_index=statement_index,
            content_hash=h,
            raw_sql=raw_sql,
        )


# ─────────────────────────────────────────────────────────────
# Supporting definitions
# ─────────────────────────────────────────────────────────────

class ColumnDefinition(BaseModel):
    """Column as defined inside a CREATE TABLE or ADD COLUMN operation."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    name: str = Field(..., description="Column name.")
    type: str = Field(..., description="Rendered data type e.g. VARCHAR2(100).")
    nullable: bool = Field(True, description="Accepts NULL.")
    default: str | None = Field(None, description="DEFAULT expression.")
    primary_key: bool = Field(False, serialization_alias="primaryKey", description="Declared inline as PRIMARY KEY.")
    unique: bool = Field(False, description="Declared inline as UNIQUE.")
    references: str | None = Field(None, description="Inline REFERENCES target.")


class ConstraintDefinition(BaseModel):
    """Constraint as defined inside CREATE TABLE or ADD CONSTRAINT."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    name: str | None = Field(None, description="Constraint name (null if anonymous).")
    type: str = Field(..., description="primary_key | unique | foreign_key | check.")
    columns: list[str] = Field(default_factory=list, description="Covered columns.")
    ref_table: str | None = Field(None, serialization_alias="refTable", description="FK referenced table.")
    ref_columns: list[str] = Field(default_factory=list, serialization_alias="refColumns", description="FK referenced columns.")
    on_delete: str | None = Field(None, serialization_alias="onDelete", description="ON DELETE action.")
    check_expr: str | None = Field(None, serialization_alias="checkExpr", description="CHECK expression.")


class ColumnChanges(BaseModel):
    """What changed on a column during an ALTER TABLE MODIFY."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    type: str | None = Field(None, description="New data type (null = unchanged).")
    nullable: bool | None = Field(None, description="New nullability (null = unchanged).")
    default: str | None = Field(None, description="New default (null = unchanged).")


# ─────────────────────────────────────────────────────────────
# Operation models
# ─────────────────────────────────────────────────────────────

class BaseOperation(BaseModel):
    """Abstract base for all DDL operations."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    provenance: OperationProvenance


# --- Table ---

class CreateTableOperation(BaseOperation):
    operation: Literal["CREATE_TABLE"] = "CREATE_TABLE"
    table: str = Field(..., description="Fully-qualified table name.")
    schema_: str | None = Field(None, serialization_alias="schema", description="Schema/owner.")
    columns: list[ColumnDefinition] = Field(default_factory=list)
    constraints: list[ConstraintDefinition] = Field(default_factory=list)


class DropTableOperation(BaseOperation):
    operation: Literal["DROP_TABLE"] = "DROP_TABLE"
    table: str
    if_exists: bool = Field(False, serialization_alias="ifExists")


class RenameTableOperation(BaseOperation):
    operation: Literal["RENAME_TABLE"] = "RENAME_TABLE"
    from_table: str = Field(..., serialization_alias="fromTable")
    to_table: str = Field(..., serialization_alias="toTable")


# --- Column ---

class AddColumnOperation(BaseOperation):
    operation: Literal["ADD_COLUMN"] = "ADD_COLUMN"
    table: str
    column: ColumnDefinition


class DropColumnOperation(BaseOperation):
    operation: Literal["DROP_COLUMN"] = "DROP_COLUMN"
    table: str
    column: str


class ModifyColumnOperation(BaseOperation):
    operation: Literal["MODIFY_COLUMN"] = "MODIFY_COLUMN"
    table: str
    column: str
    changes: ColumnChanges


class RenameColumnOperation(BaseOperation):
    operation: Literal["RENAME_COLUMN"] = "RENAME_COLUMN"
    table: str
    from_name: str = Field(..., serialization_alias="fromName")
    to_name: str = Field(..., serialization_alias="toName")


# --- Constraint ---

class AddConstraintOperation(BaseOperation):
    operation: Literal["ADD_CONSTRAINT"] = "ADD_CONSTRAINT"
    table: str
    constraint: ConstraintDefinition


class DropConstraintOperation(BaseOperation):
    operation: Literal["DROP_CONSTRAINT"] = "DROP_CONSTRAINT"
    table: str
    constraint_name: str = Field(..., serialization_alias="constraintName")
    constraint_type: str | None = Field(None, serialization_alias="constraintType")


# --- Index ---

class CreateIndexOperation(BaseOperation):
    operation: Literal["CREATE_INDEX"] = "CREATE_INDEX"
    table: str
    index_name: str = Field(..., serialization_alias="indexName")
    columns: list[str] = Field(default_factory=list)
    unique: bool = False


class DropIndexOperation(BaseOperation):
    operation: Literal["DROP_INDEX"] = "DROP_INDEX"
    index_name: str = Field(..., serialization_alias="indexName")
    table: str | None = None


# --- Sequence ---

class CreateSequenceOperation(BaseOperation):
    operation: Literal["CREATE_SEQUENCE"] = "CREATE_SEQUENCE"
    sequence: str
    schema_: str | None = Field(None, serialization_alias="schema")
    start_with: int = Field(1, serialization_alias="startWith")
    increment_by: int = Field(1, serialization_alias="incrementBy")


class DropSequenceOperation(BaseOperation):
    operation: Literal["DROP_SEQUENCE"] = "DROP_SEQUENCE"
    sequence: str


# --- Comment ---

class CommentOperation(BaseOperation):
    operation: Literal["COMMENT"] = "COMMENT"
    target: str = Field(..., description="TABLE or TABLE.COLUMN being commented.")
    comment: str


# --- Unknown fallback ---

class UnknownOperation(BaseOperation):
    operation: Literal["UNKNOWN"] = "UNKNOWN"
    statement_type: str = Field(..., serialization_alias="statementType")


# ─────────────────────────────────────────────────────────────
# Union type
# ─────────────────────────────────────────────────────────────

AnyOperation = Annotated[
    Union[
        CreateTableOperation,
        DropTableOperation,
        RenameTableOperation,
        AddColumnOperation,
        DropColumnOperation,
        ModifyColumnOperation,
        RenameColumnOperation,
        AddConstraintOperation,
        DropConstraintOperation,
        CreateIndexOperation,
        DropIndexOperation,
        CreateSequenceOperation,
        DropSequenceOperation,
        CommentOperation,
        UnknownOperation,
    ],
    Field(discriminator="operation"),
]

__all__ = [
    "OperationProvenance",
    "ColumnDefinition",
    "ConstraintDefinition",
    "ColumnChanges",
    "BaseOperation",
    "CreateTableOperation",
    "DropTableOperation",
    "RenameTableOperation",
    "AddColumnOperation",
    "DropColumnOperation",
    "ModifyColumnOperation",
    "RenameColumnOperation",
    "AddConstraintOperation",
    "DropConstraintOperation",
    "CreateIndexOperation",
    "DropIndexOperation",
    "CreateSequenceOperation",
    "DropSequenceOperation",
    "CommentOperation",
    "UnknownOperation",
    "AnyOperation",
]

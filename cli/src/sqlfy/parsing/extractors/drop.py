"""
sqlfy.parsing.extractors.drop
===============================
Extractor for DROP TABLE and DROP INDEX statements.
"""
from __future__ import annotations
import sqlglot.expressions as exp
from ...semantic.operations import (
    AnyOperation, OperationProvenance,
    DropTableOperation, DropIndexOperation,
)
from ...parsing.ast_helpers import _table_full
from .base import BaseExtractor


class DropExtractor(BaseExtractor):
    """Handles ``DROP TABLE`` and ``DROP INDEX`` statements."""

    def can_handle(self, stmt: exp.Expression) -> bool:
        if not isinstance(stmt, exp.Drop):
            return False
        kind = str(stmt.args.get("kind", "")).upper()
        return kind in ("TABLE", "INDEX")

    def extract(self, stmt: exp.Expression, provenance: OperationProvenance) -> list[AnyOperation]:
        assert isinstance(stmt, exp.Drop)
        kind = str(stmt.args.get("kind", "")).upper()
        this = stmt.this
        if kind == "TABLE":
            return [DropTableOperation(
                provenance=provenance,
                table=_table_full(this),
                if_exists=bool(stmt.args.get("exists")),
            )]
        if kind == "INDEX":
            name = this.name if hasattr(this, "name") else str(this)
            return [DropIndexOperation(provenance=provenance, index_name=name)]
        return []

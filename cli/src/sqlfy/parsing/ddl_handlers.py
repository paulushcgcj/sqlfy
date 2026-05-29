"""
sqlfy.parsing.ddl_handlers
============================
Statement-level DDL dispatch handlers.

Each handler processes one class of DDL statement and mutates the
running schema state (tables/seqs/all_actions dicts). These are called
from the Reconstructor state machine.

Handlers
--------
_handle_create_table          CREATE TABLE
_handle_drop_table            DROP TABLE
_handle_alter_table           ALTER TABLE (native sqlglot parse path)
_handle_alter_table_command   ALTER TABLE MODIFY (regex fallback path)
_handle_create_index_command  CREATE INDEX (regex fallback — sqlglot Command)
_handle_create_sequence       CREATE SEQUENCE
_handle_comment               COMMENT ON TABLE / COMMENT ON COLUMN
"""

from __future__ import annotations

import re
from typing import Optional

import sqlglot.expressions as exp

from ..domain.models import (
    Column,
    Constraint,
    Index,
    MigrationAction,
    Table,
    Sequence,
)
from ..domain.sqlglot_compat import SQLGLOT_HAS_MODIFY, parse_modify_native
from .ast_helpers import _table_full, _table_schema_name
from .column_parser import _parse_column_def
from .constraint_parser import _parse_table_constraint


# ─────────────────────────────────────────────
# CREATE TABLE
# ─────────────────────────────────────────────

def _handle_create_table(
    stmt: exp.Create,
    version: str,
    tables: dict[str, Table],
    all_actions: list[MigrationAction],
) -> None:
    """Process a CREATE TABLE statement."""
    schema_node = stmt.this  # exp.Schema
    table_node = schema_node.this  # exp.Table
    schema_str, name_str = _table_schema_name(table_node)
    full = f"{schema_str}.{name_str}" if schema_str else name_str

    columns: list[Column] = []
    constraints: list[Constraint] = []

    for node in schema_node.expressions:
        if isinstance(node, exp.ColumnDef):
            col = _parse_column_def(node)
            if col.primary_key:
                constraints.append(
                    Constraint(name=f"PK_{name_str}", type="primary_key", columns=[col.name])
                )
            if col.references:
                constraints.append(
                    Constraint(
                        name=None,
                        type="foreign_key",
                        columns=[col.name],
                        references={
                            "table": col.references["table"],
                            "columns": [col.references["column"]],
                            "on_delete": None,
                        },
                    )
                )
            columns.append(col)

        elif isinstance(node, exp.Constraint):
            c = _parse_table_constraint(node)
            if c:
                constraints.append(c)

    action = MigrationAction(
        action="CREATE", object_type="TABLE", object_name=full, version=version
    )
    all_actions.append(action)

    tables[full] = Table(
        id=full,
        schema=schema_str,
        name=name_str,
        full=full,
        columns=columns,
        constraints=constraints,
        created_in=version,
        actions=[action],
    )


# ─────────────────────────────────────────────
# DROP TABLE
# ─────────────────────────────────────────────

def _handle_drop_table(
    stmt: exp.Drop,
    version: str,
    tables: dict[str, Table],
    all_actions: list[MigrationAction],
) -> None:
    """Process a DROP TABLE statement."""
    table_node = stmt.this
    if not isinstance(table_node, exp.Table):
        return
    full = _table_full(table_node)
    action = MigrationAction(
        action="DROP", object_type="TABLE", object_name=full, version=version
    )
    all_actions.append(action)
    tables.pop(full, None)


# ─────────────────────────────────────────────
# ALTER TABLE (native sqlglot path)
# ─────────────────────────────────────────────

def _handle_alter_table(
    stmt: exp.Alter,
    version: str,
    tables: dict[str, Table],
    all_actions: list[MigrationAction],
) -> None:
    """Process an ALTER TABLE statement using the native sqlglot AST."""
    table_node = stmt.this
    if not isinstance(table_node, exp.Table):
        return
    full = _table_full(table_node)
    table = tables.get(full)

    def mark_modified() -> None:
        if table and version not in table.modified_in:
            table.modified_in.append(version)

    for action_node in stmt.args.get("actions", []):

        # ── ADD COLUMN(S) or ADD CONSTRAINT ──────────────────────────────
        if isinstance(action_node, exp.Schema):
            for node in action_node.expressions:
                if isinstance(node, exp.ColumnDef) and table:
                    col = _parse_column_def(node)
                    table.columns.append(col)
                    mark_modified()
                    act = MigrationAction(
                        action="ADD_COLUMN",
                        object_type="COLUMN",
                        object_name=f"{full}.{col.name}",
                        version=version,
                    )
                    all_actions.append(act)
                    table.actions.append(act)

        elif isinstance(action_node, exp.AddConstraint):
            for con_node in action_node.expressions:
                if isinstance(con_node, exp.Constraint) and table:
                    c = _parse_table_constraint(con_node)
                    if c:
                        table.constraints.append(c)
                        mark_modified()
                        act = MigrationAction(
                            action="ADD_CONSTRAINT",
                            object_type="CONSTRAINT",
                            object_name=f"{full}.{c.name or 'unnamed'}",
                            version=version,
                        )
                        all_actions.append(act)
                        table.actions.append(act)

        # ── DROP COLUMN ───────────────────────────────────────────────────
        elif isinstance(action_node, exp.Drop):
            if action_node.args.get("kind") == "COLUMN" and table:
                col_name = action_node.this.name.upper() if action_node.this else ""
                table.columns = [c for c in table.columns if c.name != col_name]
                mark_modified()
                act = MigrationAction(
                    action="DROP_COLUMN",
                    object_type="COLUMN",
                    object_name=f"{full}.{col_name}",
                    version=version,
                )
                all_actions.append(act)
                table.actions.append(act)

            elif action_node.args.get("kind") == "CONSTRAINT" and table:
                con_name = action_node.this.name.upper() if action_node.this else ""
                table.constraints = [
                    c for c in table.constraints if (c.name or "") != con_name
                ]
                mark_modified()
                act = MigrationAction(
                    action="DROP_CONSTRAINT",
                    object_type="CONSTRAINT",
                    object_name=f"{full}.{con_name}",
                    version=version,
                )
                all_actions.append(act)
                table.actions.append(act)


# ─────────────────────────────────────────────
# ALTER TABLE MODIFY (regex fallback)
# ─────────────────────────────────────────────

def _handle_alter_table_command(
    raw_sql: str,
    version: str,
    tables: dict[str, Table],
    all_actions: list[MigrationAction],
) -> None:
    """Fallback handler for ALTER TABLE MODIFY — sqlglot parses as Command.

    Uses the native sqlglot path when available (SQLGLOT_HAS_MODIFY),
    otherwise falls back to regex-based parsing.
    """
    # Try native sqlglot path first
    if SQLGLOT_HAS_MODIFY:
        try:
            table_name, modifications = parse_modify_native(raw_sql, dialect="oracle")
            table = tables.get(table_name)
            if not table:
                return

            for mod_info in modifications:
                col_name = mod_info.column_name
                for col in table.columns:
                    if col.name != col_name:
                        continue
                    if mod_info.data_type is not None:
                        col.type = mod_info.data_type
                    if mod_info.precision is not None:
                        col.precision = mod_info.precision
                    if mod_info.scale is not None:
                        col.scale = mod_info.scale
                    if mod_info.nullable is not None:
                        col.nullable = mod_info.nullable
                    if mod_info.default is not None:
                        col.default = mod_info.default
                    break

                if version not in table.modified_in:
                    table.modified_in.append(version)

                act = MigrationAction(
                    action="MODIFY_COLUMN",
                    object_type="COLUMN",
                    object_name=f"{table_name}.{col_name}",
                    version=version,
                )
                all_actions.append(act)
                table.actions.append(act)

            return
        except (ValueError, AttributeError):
            pass  # fall through to regex fallback

    # Regex fallback for older sqlglot versions
    m = re.match(
        r"^(?:ALTER\s+TABLE)\s+\"?(\w+(?:\.\w+)?)\"?\s+MODIFY\s*\((.+)\)\s*$",
        raw_sql.strip(),
        re.I | re.S,
    )
    if not m:
        m = re.match(
            r"^(?:ALTER\s+TABLE)\s+\"?(\w+(?:\.\w+)?)\"?\s+MODIFY\s+(.+?)\s*$",
            raw_sql.strip(),
            re.I | re.S,
        )
    if not m:
        return

    full = m.group(1).upper().replace('"', "")
    table = tables.get(full)
    if not table:
        return

    # Split comma-separated column modifications (respecting parens)
    body = m.group(2)
    depth, cur, defs = 0, [], []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            defs.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        defs.append("".join(cur).strip())

    for defn in defs:
        cm = re.match(r'"?(\w+)"?\s+(\w+(?:\s*\([^)]+\))?)(.*)', defn, re.I | re.S)
        if not cm:
            continue
        col_name = cm.group(1).upper()
        type_raw = cm.group(2).upper().strip()
        rest = cm.group(3).strip()

        for col in table.columns:
            if col.name == col_name:
                tm = re.match(
                    r"(\w[\w ]*?)(?:\(\s*(\d+)\s*(?:,\s*(\d+)\s*)?\))?$", type_raw
                )
                if tm:
                    col.type = tm.group(1).strip()
                    if tm.group(2):
                        col.precision = int(tm.group(2))
                        col.scale = int(tm.group(3)) if tm.group(3) else None
                if re.search(r"NOT\s+NULL", rest, re.I):
                    col.nullable = False
                elif re.search(r"\bNULL\b", rest, re.I):
                    col.nullable = True
                dm = re.search(
                    r"DEFAULT\s+(.+?)(?=\s+(?:NOT\s+NULL|NULL)|$)", rest, re.I
                )
                if dm:
                    col.default = dm.group(1).strip()
                break

        if version not in table.modified_in:
            table.modified_in.append(version)
        act = MigrationAction(
            action="MODIFY_COLUMN",
            object_type="COLUMN",
            object_name=f"{full}.{col_name}",
            version=version,
        )
        all_actions.append(act)
        table.actions.append(act)


# ─────────────────────────────────────────────
# CREATE INDEX (regex fallback)
# ─────────────────────────────────────────────

def _handle_create_index_command(
    raw_sql: str,
    version: str,
    tables: dict[str, Table],
    all_actions: list[MigrationAction],
) -> None:
    """Handle CREATE INDEX — sqlglot falls back to Command, so we use regex."""
    m = re.match(
        r"^(?:CREATE\s+)?(UNIQUE\s+)?INDEX\s+\"?(\w+(?:\.\w+)?)\"?\s+ON\s+\"?(\w+(?:\.\w+)?)\"?\s*\(([^)]+)\)",
        raw_sql.strip(),
        re.I,
    )
    if not m:
        return

    unique = bool(m.group(1))
    idx_raw = m.group(2).replace('"', "").upper()
    tbl_raw = m.group(3).replace('"', "").upper()
    cols_raw = m.group(4)

    idx_name = idx_raw.split(".")[-1]
    cols = [
        re.sub(r"\s+(ASC|DESC)$", "", c.strip(), flags=re.I).replace('"', "").upper()
        for c in cols_raw.split(",")
    ]

    table = tables.get(tbl_raw)
    if table:
        table.indexes.append(
            Index(name=idx_name, columns=cols, unique=unique, created_in=version)
        )
        act = MigrationAction(
            action="CREATE_INDEX",
            object_type="INDEX",
            object_name=f"{tbl_raw}.{idx_name}",
            version=version,
        )
        all_actions.append(act)
        table.actions.append(act)


# ─────────────────────────────────────────────
# CREATE SEQUENCE
# ─────────────────────────────────────────────

def _handle_create_sequence(
    stmt: exp.Create,
    version: str,
    seqs: dict[str, Sequence],
    all_actions: list[MigrationAction],
) -> None:
    """Process a CREATE SEQUENCE statement."""
    table_node = stmt.this
    schema_str, name_str = _table_schema_name(table_node)
    full = f"{schema_str}.{name_str}" if schema_str else name_str

    start_with = 1
    increment_by = 1

    props = stmt.args.get("properties")
    if props:
        for p in props.expressions:
            if isinstance(p, exp.SequenceProperties):
                if p.args.get("start"):
                    start_with = int(p.args["start"].name)
                if p.args.get("increment"):
                    increment_by = int(p.args["increment"].name)

    seqs[full] = Sequence(
        name=name_str,
        schema=schema_str,
        full=full,
        start_with=start_with,
        increment_by=increment_by,
        created_in=version,
    )
    all_actions.append(
        MigrationAction(
            action="CREATE_SEQUENCE",
            object_type="SEQUENCE",
            object_name=full,
            version=version,
        )
    )


# ─────────────────────────────────────────────
# COMMENT ON
# ─────────────────────────────────────────────

def _handle_comment(
    stmt: exp.Comment,
    tables: dict[str, Table],
) -> None:
    """Process a COMMENT ON TABLE / COMMENT ON COLUMN statement."""
    kind = stmt.args.get("kind", "").upper()
    if kind == "TABLE":
        table_node = stmt.this
        if isinstance(table_node, exp.Table):
            full = _table_full(table_node)
            t = tables.get(full)
            if t:
                t.comments["__table__"] = stmt.expression.name if stmt.expression else ""
    elif kind == "COLUMN":
        col_node = stmt.this
        if isinstance(col_node, exp.Column):
            col_name = col_node.name.upper()
            table_node = col_node.args.get("table")
            db_node = col_node.args.get("db")
            if table_node:
                tname = table_node.name.upper()
                full = f"{db_node.name.upper()}.{tname}" if db_node else tname
                t = tables.get(full)
                if t:
                    t.comments[col_name] = (
                        stmt.expression.name if stmt.expression else ""
                    )


__all__ = [
    "_handle_create_table",
    "_handle_drop_table",
    "_handle_alter_table",
    "_handle_alter_table_command",
    "_handle_create_index_command",
    "_handle_create_sequence",
    "_handle_comment",
]

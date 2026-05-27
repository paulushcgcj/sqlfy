"""
sqlfy.analysis.classifier
=========================
Migration semantic classification.

Classifies each migration file into semantic categories based on its SQL
operations:

- table_creation:         CREATE TABLE statements
- column_addition:        ALTER TABLE ... ADD COLUMN
- column_removal:         ALTER TABLE ... DROP COLUMN
- constraint_modification: ADD/DROP/MODIFY CONSTRAINT operations
- index_management:       CREATE/DROP INDEX
- data_migration:         INSERT / UPDATE / DELETE / TRUNCATE (DML)
- cleanup:                DROP TABLE / VIEW / PROCEDURE / SEQUENCE
- refactor:               RENAME COLUMN / RENAME TABLE
- view_trigger_procedure: CREATE VIEW / TRIGGER / PROCEDURE / FUNCTION
- mixed:                  multiple unresolvable categories

Risk levels
-----------
- high:   data_migration, cleanup, column_removal
- medium: constraint_modification, refactor, table_creation,
          view_trigger_procedure
- low:    column_addition, index_management
"""

from __future__ import annotations

import json
import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

import sqlglot
import sqlglot.expressions as exp

logging.getLogger("sqlglot").setLevel(logging.CRITICAL)

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# CATEGORY DEFINITIONS
# ─────────────────────────────────────────────

class MigrationCategory(Enum):
    """Semantic category for a migration file."""

    TABLE_CREATION = "table_creation"
    COLUMN_ADDITION = "column_addition"
    COLUMN_REMOVAL = "column_removal"
    CONSTRAINT_MODIFICATION = "constraint_modification"
    INDEX_MANAGEMENT = "index_management"
    DATA_MIGRATION = "data_migration"
    CLEANUP = "cleanup"
    REFACTOR = "refactor"
    VIEW_TRIGGER_PROCEDURE = "view_trigger_procedure"
    MIXED = "mixed"


# Risk level for each category (used when computing overall migration risk)
_CATEGORY_RISK: dict[MigrationCategory, str] = {
    MigrationCategory.DATA_MIGRATION: "high",
    MigrationCategory.CLEANUP: "high",
    MigrationCategory.COLUMN_REMOVAL: "high",
    MigrationCategory.CONSTRAINT_MODIFICATION: "medium",
    MigrationCategory.REFACTOR: "medium",
    MigrationCategory.TABLE_CREATION: "medium",
    MigrationCategory.VIEW_TRIGGER_PROCEDURE: "medium",
    MigrationCategory.COLUMN_ADDITION: "low",
    MigrationCategory.INDEX_MANAGEMENT: "low",
    MigrationCategory.MIXED: "medium",
}

# Priority order: first wins when selecting the primary category
_CATEGORY_PRIORITY: list[MigrationCategory] = [
    MigrationCategory.DATA_MIGRATION,
    MigrationCategory.CLEANUP,
    MigrationCategory.COLUMN_REMOVAL,
    MigrationCategory.TABLE_CREATION,
    MigrationCategory.CONSTRAINT_MODIFICATION,
    MigrationCategory.REFACTOR,
    MigrationCategory.VIEW_TRIGGER_PROCEDURE,
    MigrationCategory.COLUMN_ADDITION,
    MigrationCategory.INDEX_MANAGEMENT,
]

# Human-readable label for each category
_CAT_LABEL: dict[MigrationCategory, str] = {
    MigrationCategory.TABLE_CREATION: "table_creation",
    MigrationCategory.COLUMN_ADDITION: "column_addition",
    MigrationCategory.COLUMN_REMOVAL: "column_removal",
    MigrationCategory.CONSTRAINT_MODIFICATION: "constraint_modification",
    MigrationCategory.INDEX_MANAGEMENT: "index_management",
    MigrationCategory.DATA_MIGRATION: "data_migration",
    MigrationCategory.CLEANUP: "cleanup",
    MigrationCategory.REFACTOR: "refactor",
    MigrationCategory.VIEW_TRIGGER_PROCEDURE: "view_trigger_procedure",
    MigrationCategory.MIXED: "mixed",
}

_RISK_EMOJI: dict[str, str] = {"high": "🔴", "medium": "🟡", "low": "🟢"}


# ─────────────────────────────────────────────
# DATA MODEL
# ─────────────────────────────────────────────

@dataclass
class ClassifiedMigration:
    """Classification result for a single migration file."""

    filename: str
    primary_category: MigrationCategory
    secondary_categories: list[MigrationCategory] = field(default_factory=list)
    statement_counts: dict[str, int] = field(default_factory=dict)
    risk_level: Literal["low", "medium", "high"] = "medium"

    def to_dict(self) -> dict:
        """Serialize to a plain dictionary."""
        return {
            "filename": self.filename,
            "primary_category": self.primary_category.value,
            "secondary_categories": [c.value for c in self.secondary_categories],
            "all_categories": [self.primary_category.value]
            + [c.value for c in self.secondary_categories],
            "statement_counts": self.statement_counts,
            "risk_level": self.risk_level,
        }


# ─────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────

def _alter_categories(stmt: exp.Alter) -> set[MigrationCategory]:
    """Extract categories contributed by an ALTER TABLE statement."""
    cats: set[MigrationCategory] = set()
    for action in stmt.args.get("actions", []):
        if isinstance(action, exp.ColumnDef):
            # ALTER TABLE ... ADD col_name type (non-Oracle syntax)
            cats.add(MigrationCategory.COLUMN_ADDITION)
        elif isinstance(action, exp.Schema):
            # Oracle: ALTER TABLE ... ADD (col_name type, ...) — wrapped in Schema
            if any(isinstance(expr, exp.ColumnDef) for expr in action.expressions):
                cats.add(MigrationCategory.COLUMN_ADDITION)
        elif isinstance(action, exp.Drop):
            drop_kind = (action.args.get("kind") or "").upper()
            if drop_kind == "COLUMN":
                cats.add(MigrationCategory.COLUMN_REMOVAL)
            elif drop_kind in ("CONSTRAINT", "PRIMARY_KEY", "FOREIGN_KEY", "UNIQUE"):
                cats.add(MigrationCategory.CONSTRAINT_MODIFICATION)
            elif drop_kind == "INDEX":
                cats.add(MigrationCategory.INDEX_MANAGEMENT)
        elif isinstance(action, exp.AddConstraint):
            cats.add(MigrationCategory.CONSTRAINT_MODIFICATION)
        elif isinstance(action, exp.RenameColumn):
            cats.add(MigrationCategory.REFACTOR)
        elif isinstance(action, exp.AlterRename):
            cats.add(MigrationCategory.REFACTOR)
        elif isinstance(action, exp.AlterColumn):
            # ALTER TABLE ... MODIFY / SET DEFAULT / DROP DEFAULT
            cats.add(MigrationCategory.CONSTRAINT_MODIFICATION)
    return cats


def _command_categories(stmt: exp.Command, stmt_counts: dict[str, int]) -> set[MigrationCategory]:
    """
    Regex-based category detection for statements sqlglot emits as exp.Command
    (e.g. MODIFY, RENAME COLUMN, TRUNCATE, CREATE TRIGGER/PROCEDURE in Oracle).
    """
    cats: set[MigrationCategory] = set()
    raw = f"{stmt.this or ''} {stmt.expression or ''}".strip().upper()

    def inc(key: str) -> None:
        stmt_counts[key] = stmt_counts.get(key, 0) + 1

    # MODIFY (ALTER TABLE ... MODIFY column ...)
    if re.search(r"\bMODIFY\b", raw):
        cats.add(MigrationCategory.CONSTRAINT_MODIFICATION)
        inc("ALTER_MODIFY")
    # RENAME COLUMN / TABLE
    elif re.search(r"\bRENAME\b.*\b(COLUMN|TABLE)\b", raw):
        cats.add(MigrationCategory.REFACTOR)
        inc("RENAME")
    # TRUNCATE TABLE
    elif re.search(r"^\s*TRUNCATE\b", raw):
        cats.add(MigrationCategory.DATA_MIGRATION)
        inc("TRUNCATE")
    # CREATE OR REPLACE TRIGGER / CREATE TRIGGER
    elif re.search(r"\bCREATE\b.*\bTRIGGER\b", raw):
        cats.add(MigrationCategory.VIEW_TRIGGER_PROCEDURE)
        inc("CREATE_TRIGGER")
    # CREATE OR REPLACE PROCEDURE / FUNCTION / PACKAGE
    elif re.search(r"\bCREATE\b.*\b(PROCEDURE|FUNCTION|PACKAGE)\b", raw):
        cats.add(MigrationCategory.VIEW_TRIGGER_PROCEDURE)
        inc("CREATE_PROCEDURE")
    # CREATE OR REPLACE VIEW
    elif re.search(r"\bCREATE\b.*\bVIEW\b", raw):
        cats.add(MigrationCategory.VIEW_TRIGGER_PROCEDURE)
        inc("CREATE_VIEW")
    # DROP TRIGGER
    elif re.search(r"\bDROP\b.*\bTRIGGER\b", raw):
        cats.add(MigrationCategory.CLEANUP)
        inc("DROP_TRIGGER")
    # DROP PROCEDURE / FUNCTION / PACKAGE
    elif re.search(r"\bDROP\b.*\b(PROCEDURE|FUNCTION|PACKAGE)\b", raw):
        cats.add(MigrationCategory.CLEANUP)
        inc("DROP_PROCEDURE")

    return cats


# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

def classify_migration(
    filename: str,
    content: str,
    dialect: str = "oracle",
) -> ClassifiedMigration:
    """
    Classify a single migration by its SQL operations.

    Args:
        filename: Migration filename (e.g. ``V1__create_users.sql``).
        content:  Raw SQL content of the migration.
        dialect:  SQL dialect — ``oracle``, ``postgres``, ``mysql``, ``sqlite``.

    Returns:
        :class:`ClassifiedMigration` with primary category, secondary categories,
        statement counts, and overall risk level.
    """
    cats: set[MigrationCategory] = set()
    stmt_counts: dict[str, int] = {}

    def inc(key: str) -> None:
        stmt_counts[key] = stmt_counts.get(key, 0) + 1

    stmts = sqlglot.parse(content, dialect=dialect, error_level=sqlglot.ErrorLevel.WARN)

    for stmt in stmts:
        if stmt is None:
            continue

        # ── CREATE ───────────────────────────────────────────────
        if isinstance(stmt, exp.Create):
            kind = (stmt.args.get("kind") or "").upper()
            if kind == "TABLE":
                cats.add(MigrationCategory.TABLE_CREATION)
                inc("CREATE_TABLE")
            elif kind == "INDEX":
                cats.add(MigrationCategory.INDEX_MANAGEMENT)
                inc("CREATE_INDEX")
            elif kind == "VIEW":
                cats.add(MigrationCategory.VIEW_TRIGGER_PROCEDURE)
                inc("CREATE_VIEW")
            elif kind == "TRIGGER":
                cats.add(MigrationCategory.VIEW_TRIGGER_PROCEDURE)
                inc("CREATE_TRIGGER")
            elif kind in ("PROCEDURE", "FUNCTION"):
                cats.add(MigrationCategory.VIEW_TRIGGER_PROCEDURE)
                inc(f"CREATE_{kind}")
            # CREATE SEQUENCE → infrastructure; skip semantic classification

        # ── DROP ─────────────────────────────────────────────────
        elif isinstance(stmt, exp.Drop):
            kind = (stmt.args.get("kind") or "").upper()
            if kind == "TABLE":
                cats.add(MigrationCategory.CLEANUP)
                inc("DROP_TABLE")
            elif kind == "INDEX":
                cats.add(MigrationCategory.INDEX_MANAGEMENT)
                inc("DROP_INDEX")
            elif kind in ("VIEW", "MATERIALIZED_VIEW"):
                cats.add(MigrationCategory.CLEANUP)
                inc("DROP_VIEW")
            elif kind in ("PROCEDURE", "FUNCTION", "TRIGGER"):
                cats.add(MigrationCategory.CLEANUP)
                inc(f"DROP_{kind}")
            elif kind == "SEQUENCE":
                cats.add(MigrationCategory.CLEANUP)
                inc("DROP_SEQUENCE")

        # ── ALTER ─────────────────────────────────────────────────
        elif isinstance(stmt, exp.Alter):
            if (stmt.args.get("kind") or "").upper() == "TABLE":
                alter_cats = _alter_categories(stmt)
                cats.update(alter_cats)
                # Count each alter sub-type
                if MigrationCategory.COLUMN_ADDITION in alter_cats:
                    inc("ALTER_ADD_COLUMN")
                if MigrationCategory.COLUMN_REMOVAL in alter_cats:
                    inc("ALTER_DROP_COLUMN")
                if MigrationCategory.CONSTRAINT_MODIFICATION in alter_cats:
                    inc("ALTER_CONSTRAINT")
                if MigrationCategory.REFACTOR in alter_cats:
                    inc("ALTER_RENAME")
                if MigrationCategory.INDEX_MANAGEMENT in alter_cats:
                    inc("ALTER_DROP_INDEX")

        # ── DML ──────────────────────────────────────────────────
        elif isinstance(stmt, exp.Insert):
            cats.add(MigrationCategory.DATA_MIGRATION)
            inc("INSERT")

        elif isinstance(stmt, exp.Update):
            cats.add(MigrationCategory.DATA_MIGRATION)
            inc("UPDATE")

        elif isinstance(stmt, exp.Delete):
            cats.add(MigrationCategory.DATA_MIGRATION)
            inc("DELETE")

        # ── COMMAND FALLBACK (unsupported syntax as raw strings) ──
        elif isinstance(stmt, exp.Command):
            cmd_cats = _command_categories(stmt, stmt_counts)
            cats.update(cmd_cats)

    # ── Determine primary & secondary categories ──────────────────
    if cats:
        sorted_cats = [c for c in _CATEGORY_PRIORITY if c in cats]
        primary = sorted_cats[0] if sorted_cats else MigrationCategory.MIXED
        secondary = sorted_cats[1:]
    else:
        primary = MigrationCategory.MIXED
        secondary = []

    # ── Risk level (worst-case across all detected categories) ────
    risk_level: Literal["low", "medium", "high"] = "low"
    effective_cats = cats or {primary}
    for cat in effective_cats:
        cat_risk = _CATEGORY_RISK.get(cat, "medium")
        if cat_risk == "high":
            risk_level = "high"
            break
        if cat_risk == "medium":
            risk_level = "medium"

    return ClassifiedMigration(
        filename=filename,
        primary_category=primary,
        secondary_categories=secondary,
        statement_counts=stmt_counts,
        risk_level=risk_level,
    )


def classify_migrations(
    files: list[dict],
    dialect: str = "oracle",
) -> list[ClassifiedMigration]:
    """
    Classify all migrations from a loaded file list.

    Args:
        files:   List of ``{"filename": str, "sql": str}`` dicts as returned
                 by :func:`sqlfy.commands._utils.load_files`.
        dialect: SQL dialect (default ``oracle``).

    Returns:
        List of :class:`ClassifiedMigration` in file order.
    """
    return [
        classify_migration(f["filename"], f["sql"], dialect=dialect)
        for f in files
    ]


def group_by_category(
    classifications: list[ClassifiedMigration],
) -> dict[MigrationCategory, list[str]]:
    """Return a mapping of primary category → list of filenames."""
    groups: dict[MigrationCategory, list[str]] = {}
    for c in classifications:
        groups.setdefault(c.primary_category, []).append(c.filename)
    return groups


def group_by_risk(
    classifications: list[ClassifiedMigration],
) -> dict[str, list[str]]:
    """Return a mapping of risk level → list of filenames."""
    groups: dict[str, list[str]] = {}
    for c in classifications:
        groups.setdefault(c.risk_level, []).append(c.filename)
    return groups


# ─────────────────────────────────────────────
# FORMATTERS
# ─────────────────────────────────────────────

def format_text(
    classifications: list[ClassifiedMigration],
    *,
    group_by: bool = False,
) -> str:
    """Render classification results as a human-readable text report."""
    if not classifications:
        return "No migrations to classify."

    lines: list[str] = []

    if group_by:
        lines += ["Migrations by Category", "======================", ""]
        groups = group_by_category(classifications)
        ordered = [c for c in _CATEGORY_PRIORITY if c in groups]
        if MigrationCategory.MIXED in groups:
            ordered.append(MigrationCategory.MIXED)
        for cat in ordered:
            filenames = groups[cat]
            heading = _CAT_LABEL[cat].replace("_", " ").title()
            lines.append(f"{heading} ({len(filenames)})")
            for fname in filenames:
                cl = next(c for c in classifications if c.filename == fname)
                emoji = _RISK_EMOJI.get(cl.risk_level, "")
                lines.append(f"  {emoji} {fname}")
            lines.append("")
    else:
        lines += ["Migration Classifications", "========================", ""]
        max_len = max((len(c.filename) for c in classifications), default=0)
        for c in classifications:
            cat_label = _CAT_LABEL[c.primary_category]
            emoji = _RISK_EMOJI.get(c.risk_level, "")
            secondary_str = (
                f"  (+ {', '.join(_CAT_LABEL[s] for s in c.secondary_categories)})"
                if c.secondary_categories
                else ""
            )
            lines.append(
                f"  {c.filename.ljust(max_len)}  →  {cat_label:<30} {emoji}{secondary_str}"
            )
        lines.append("")

    # Summary by category
    lines += ["Summary", "-------"]
    groups = group_by_category(classifications)
    for cat in _CATEGORY_PRIORITY:
        if cat in groups:
            lines.append(f"  {_CAT_LABEL[cat]:<32} {len(groups[cat])}")
    if MigrationCategory.MIXED in groups:
        lines.append(f"  {'mixed':<32} {len(groups[MigrationCategory.MIXED])}")
    lines.append("")

    # Risk distribution
    lines += ["Risk Distribution", "-----------------"]
    risk_groups = group_by_risk(classifications)
    for level in ("high", "medium", "low"):
        if level in risk_groups:
            emoji = _RISK_EMOJI[level]
            count = len(risk_groups[level])
            lines.append(f"  {emoji} {level:<8}  {count} migration(s)")

    return "\n".join(lines)


def format_json(classifications: list[ClassifiedMigration]) -> str:
    """Render classification results as a JSON string."""
    groups = group_by_category(classifications)
    risk_groups = group_by_risk(classifications)

    return json.dumps(
        {
            "migrations": [c.to_dict() for c in classifications],
            "summary": {
                "total": len(classifications),
                "by_category": {
                    cat.value: len(filenames) for cat, filenames in groups.items()
                },
                "by_risk": {
                    level: len(filenames)
                    for level, filenames in risk_groups.items()
                },
            },
        },
        indent=2,
        ensure_ascii=False,
    )
